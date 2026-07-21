#!/usr/bin/env python3
"""Directly query macOS Input Monitoring (ListenEvent) TCC status for THIS process
via IOKit's IOHIDCheckAccess — no device I/O, no knob-turning needed.

Returns the ground truth: is kitty (our responsible app) granted, denied, or unknown?
"""
import ctypes

iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
iokit.IOHIDCheckAccess.restype = ctypes.c_int
iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]

kIOHIDRequestTypeListenEvent = 1     # Input Monitoring
NAMES = {0: "GRANTED", 1: "DENIED", 2: "UNKNOWN (never decided / not in list)"}

status = iokit.IOHIDCheckAccess(kIOHIDRequestTypeListenEvent)
print(f"IOHIDCheckAccess(ListenEvent) = {status}  -> {NAMES.get(status, status)}")
print()
if status == 0:
    print("Input Monitoring IS granted for this process. If reads still fail, the")
    print("problem is NOT permission — we'd look at device seizing / driver claim.")
elif status == 1:
    print("Explicitly DENIED. kitty is in the Input Monitoring list but toggled OFF,")
    print("or the grant isn't persisting. Toggle kitty ON (or we grant a different")
    print("process). A DENIED state will NOT prompt on its own.")
else:
    print("UNKNOWN — kitty has never been granted. We can trigger the system prompt")
    print("with IOHIDRequestAccess so you get a one-click Allow dialog.")
