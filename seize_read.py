#!/usr/bin/env python3
"""Read the knob by SEIZING it via IOKit (kIOHIDOptionsTypeSeizeDevice), taking
exclusive control so macOS's own HID driver can't swallow the interrupt reports.

This is what stock hidapi 0.15 cannot do (it opens shared). Matching is restricted
to our VID/PID, so ONLY the knob is seized — the keyboard/mouse are untouched.

Usage: seize_read.py [seconds] [noseize]
"""
import ctypes, ctypes.util, sys, time

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
SEIZE = "noseize" not in sys.argv[2:]
VID, PID = 0x303A, 0x4001

cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
io = ctypes.CDLL(ctypes.util.find_library("IOKit"))

CFIndex = ctypes.c_long
kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3
kIOHIDOptionsTypeSeizeDevice = 1

# --- CF prototypes ---
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
cf.CFNumberCreate.restype = ctypes.c_void_p
cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
cf.CFDictionaryCreateMutable.restype = ctypes.c_void_p
cf.CFDictionaryCreateMutable.argtypes = [ctypes.c_void_p, CFIndex, ctypes.c_void_p, ctypes.c_void_p]
cf.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
cf.CFRunLoopRunInMode.restype = ctypes.c_int32
cf.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]

kCFAllocatorDefault = None
key_cb = ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
val_cb = ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryValueCallBacks")
default_mode = ctypes.c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")


def cfstr(s):
    return cf.CFStringCreateWithCString(kCFAllocatorDefault, s.encode(), kCFStringEncodingUTF8)


def cfnum(n):
    v = ctypes.c_int32(n)
    return cf.CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, ctypes.byref(v))


# --- IOKit prototypes ---
io.IOHIDManagerCreate.restype = ctypes.c_void_p
io.IOHIDManagerCreate.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
io.IOHIDManagerSetDeviceMatching.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
io.IOHIDManagerScheduleWithRunLoop.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
io.IOHIDManagerOpen.restype = ctypes.c_int32
io.IOHIDManagerOpen.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
io.IOHIDManagerRegisterDeviceMatchingCallback.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
io.IOHIDDeviceRegisterInputReportCallback.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, CFIndex, ctypes.c_void_p, ctypes.c_void_p]

REPORT_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p,
                             ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint8), CFIndex)
MATCH_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)

events = []
_bufs = []          # keep report buffers alive
_cbs = []           # keep callbacks alive


def on_report(context, result, sender, rtype, report_id, report, length):
    data = [report[i] for i in range(length)]
    # decode surface-dial: report_id then 16-bit (button bit0, dial 15-bit signed)
    if len(data) >= 2:
        raw16 = data[0] | (data[1] << 8)
        btn = raw16 & 1
        dial = raw16 >> 1
        if dial & 0x4000:
            dial -= 0x8000
    else:
        btn = dial = 0
    events.append((time.time(), btn, dial, data))
    print(f"  REPORT id={report_id} len={length} btn={btn} dial={dial:+d} raw={[f'{b:02X}' for b in data]}",
          flush=True)


def on_match(context, result, sender, device):
    buf = (ctypes.c_uint8 * 64)()
    _bufs.append(buf)
    cb = REPORT_CB(on_report)
    _cbs.append(cb)
    io.IOHIDDeviceRegisterInputReportCallback(
        device, ctypes.cast(buf, ctypes.c_char_p), 64, ctypes.cast(cb, ctypes.c_void_p), None)
    print(f"  matched device {device:#x} -> registered input-report callback", flush=True)


def main():
    mgr = io.IOHIDManagerCreate(kCFAllocatorDefault, 0)
    match = cf.CFDictionaryCreateMutable(kCFAllocatorDefault, 0,
                                         ctypes.byref(key_cb), ctypes.byref(val_cb))
    cf.CFDictionarySetValue(match, cfstr("VendorID"), cfnum(VID))
    cf.CFDictionarySetValue(match, cfstr("ProductID"), cfnum(PID))
    io.IOHIDManagerSetDeviceMatching(mgr, match)

    mcb = MATCH_CB(on_match)
    _cbs.append(mcb)
    io.IOHIDManagerRegisterDeviceMatchingCallback(mgr, ctypes.cast(mcb, ctypes.c_void_p), None)
    io.IOHIDManagerScheduleWithRunLoop(mgr, cf.CFRunLoopGetCurrent(), default_mode)

    opt = kIOHIDOptionsTypeSeizeDevice if SEIZE else 0
    r = io.IOHIDManagerOpen(mgr, opt)
    print(f">>> IOHIDManagerOpen(seize={SEIZE}) returned {r:#010x} "
          f"({'OK' if r == 0 else 'ERROR'})")
    print(f">>> Reading {SECONDS:.0f}s — TURN THE KNOB back and forth + press.\n", flush=True)

    t0 = time.time()
    while time.time() - t0 < SECONDS:
        cf.CFRunLoopRunInMode(default_mode, 0.2, True)

    print("\n" + "=" * 56)
    if not events:
        print(f"VERDICT: still 0 reports even with seize={SEIZE}. Reports aren't")
        print("reaching any userspace client -> device likely isn't emitting on this")
        print("interface (may need host-side Surface Dial config, or wrong collection).")
    else:
        rots = [e for e in events if e[2] != 0]
        print(f"VERDICT: ✅ {len(events)} reports via seize={SEIZE}! rotations={len(rots)}")
        if rots:
            mags = sorted({abs(e[2]) for e in rots})
            print(f"  step magnitudes: {mags}  (smallest {mags[0]} = {mags[0]/10:.1f}°)")
            print(f"  first rotation sign: {'+' if rots[0][2] > 0 else '-'}")


if __name__ == "__main__":
    main()
