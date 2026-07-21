"""IOKit HID reader for the knob.

macOS binds its own HID driver to this Surface-Dial-class device and swallows the
interrupt reports from any *shared* reader (stock hidapi sees nothing). The only
way to receive them is to open the device with kIOHIDOptionsTypeSeizeDevice —
exclusive access, matched to *only* our VID/PID so nothing else is affected.

The reader runs its own CFRunLoop on a dedicated daemon thread and invokes
`on_event(button: int, dial: int)` for every report:
  * dial != 0  -> a rotation detent (+/-100 per click; sign = direction)
  * dial == 0  -> a button state report (button 1 = down, 0 = up)
"""
import ctypes
import ctypes.util
import threading

from . import VENDOR_ID, PRODUCT_ID

_cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
_io = ctypes.CDLL(ctypes.util.find_library("IOKit"))

CFIndex = ctypes.c_long
_kCFStringEncodingUTF8 = 0x08000100
_kCFNumberSInt32Type = 3
kIOHIDOptionsTypeSeizeDevice = 1

# --- CoreFoundation prototypes ---
_cf.CFStringCreateWithCString.restype = ctypes.c_void_p
_cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_cf.CFNumberCreate.restype = ctypes.c_void_p
_cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_cf.CFDictionaryCreateMutable.restype = ctypes.c_void_p
_cf.CFDictionaryCreateMutable.argtypes = [ctypes.c_void_p, CFIndex, ctypes.c_void_p, ctypes.c_void_p]
_cf.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
_cf.CFRunLoopRun.argtypes = []

_key_cb = ctypes.c_void_p.in_dll(_cf, "kCFTypeDictionaryKeyCallBacks")
_val_cb = ctypes.c_void_p.in_dll(_cf, "kCFTypeDictionaryValueCallBacks")
_default_mode = ctypes.c_void_p.in_dll(_cf, "kCFRunLoopDefaultMode")

# --- IOKit prototypes ---
_io.IOHIDManagerCreate.restype = ctypes.c_void_p
_io.IOHIDManagerCreate.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_io.IOHIDManagerSetDeviceMatching.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_io.IOHIDManagerScheduleWithRunLoop.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_io.IOHIDManagerOpen.restype = ctypes.c_int32
_io.IOHIDManagerOpen.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_io.IOHIDManagerRegisterDeviceMatchingCallback.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_io.IOHIDDeviceRegisterInputReportCallback.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, CFIndex, ctypes.c_void_p, ctypes.c_void_p]

_REPORT_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p,
                              ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint8), CFIndex)
_MATCH_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)


def _cfstr(s):
    return _cf.CFStringCreateWithCString(None, s.encode(), _kCFStringEncodingUTF8)


def _cfnum(n):
    v = ctypes.c_int32(n)
    return _cf.CFNumberCreate(None, _kCFNumberSInt32Type, ctypes.byref(v))


def decode(buf):
    """Decode a raw report buffer (report-id at buf[0]) -> (button, dial) or None.

    dial is in 0.1-degree units; +/-100 per detent. Sign is rotation direction.
    """
    if not buf or len(buf) < 3 or buf[0] != 0x01:
        return None
    raw16 = buf[1] | (buf[2] << 8)
    button = raw16 & 0x1
    dial = raw16 >> 1
    if dial & 0x4000:  # sign-extend the 15-bit field
        dial -= 0x8000
    return button, dial


class KnobReader:
    def __init__(self, on_event, on_status=None):
        """on_event(button, dial) fires per report. on_status(str) reports lifecycle."""
        self._on_event = on_event
        self._on_status = on_status or (lambda _s: None)
        self._thread = None
        self._keepalive = []  # keep ctypes callbacks / buffers alive
        self.opened = False

    def start(self):
        self._thread = threading.Thread(target=self._run, name="knob-reader", daemon=True)
        self._thread.start()

    def _run(self):
        mgr = _io.IOHIDManagerCreate(None, 0)
        match = _cf.CFDictionaryCreateMutable(None, 0, ctypes.byref(_key_cb), ctypes.byref(_val_cb))
        _cf.CFDictionarySetValue(match, _cfstr("VendorID"), _cfnum(VENDOR_ID))
        _cf.CFDictionarySetValue(match, _cfstr("ProductID"), _cfnum(PRODUCT_ID))
        _io.IOHIDManagerSetDeviceMatching(mgr, match)

        def _on_match(context, result, sender, device):
            buf = (ctypes.c_uint8 * 64)()
            self._keepalive.append(buf)
            io_cb = _REPORT_CB(self._make_report_cb())
            self._keepalive.append(io_cb)
            _io.IOHIDDeviceRegisterInputReportCallback(
                device, ctypes.cast(buf, ctypes.c_char_p), 64,
                ctypes.cast(io_cb, ctypes.c_void_p), None)
            self._on_status("knob connected")

        match_cb = _MATCH_CB(_on_match)
        self._keepalive.append(match_cb)
        _io.IOHIDManagerRegisterDeviceMatchingCallback(mgr, ctypes.cast(match_cb, ctypes.c_void_p), None)
        _io.IOHIDManagerScheduleWithRunLoop(mgr, _cf.CFRunLoopGetCurrent(), _default_mode)

        r = _io.IOHIDManagerOpen(mgr, kIOHIDOptionsTypeSeizeDevice)
        self.opened = (r == 0)
        if r != 0:
            self._on_status(f"seize failed (0x{r & 0xffffffff:08x}) — is another reader open?")
            return
        self._on_status("seized device; listening")
        _cf.CFRunLoopRun()  # blocks this thread

    def _make_report_cb(self):
        on_event = self._on_event

        def _cb(context, result, sender, rtype, report_id, report, length):
            try:
                data = bytes(report[i] for i in range(length))
                decoded = decode(data)
                if decoded is not None:
                    on_event(decoded[0], decoded[1])
            except Exception as e:  # never let a callback exception kill the run loop
                self._on_status(f"reader error: {e}")

        return _cb
