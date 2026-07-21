#!/usr/bin/env python3
"""Diagnose why read() sees nothing: is it Input Monitoring, or device I/O?

get_input_report() uses a control-transfer GET_REPORT, which is NOT gated by
macOS Input Monitoring. read() uses the interrupt-in pipe, which IS gated.
If get_input_report works but read() is silent -> confirmed permission gate.
"""
import hid, time

VID, PID = 0x303A, 0x4001

print("hidapi version:", hid.version_str() if hasattr(hid, "version_str") else "?")
devs = hid.enumerate(VID, PID)
print(f"device present: {len(devs)} interface(s)")
for d in devs:
    print(f"  usage_page={d['usage_page']:#06x} usage={d['usage']:#04x} "
          f"iface={d.get('interface_number')} path={d['path']!r}")

h = hid.device()
h.open(VID, PID)
print("opened OK. product:", h.get_product_string())

print("\n--- control-transfer read (get_input_report), 5 samples, device IDLE ---")
for i in range(5):
    try:
        r = h.get_input_report(1, 3)      # report id 1, up to 3 bytes
        print(f"  sample {i}: {[f'{b:02X}' for b in r]}")
    except Exception as e:
        print(f"  sample {i}: get_input_report FAILED: {e}")
    time.sleep(0.1)

print("\n--- interrupt read() nonblocking, 1.5s, device IDLE (expect 0 while idle) ---")
h.set_nonblocking(True)
t0 = time.time(); n = 0
while time.time() - t0 < 1.5:
    d = h.read(8)
    if d:
        n += 1
        print("  read():", [f"{b:02X}" for b in d])
    time.sleep(0.003)
print(f"  read() reports while idle: {n}")
h.close()
print("\nInterpretation:")
print("  * get_input_report returns bytes  -> device I/O + our open target are CORRECT.")
print("  * that path is permission-independent, so it works even without Input Monitoring.")
print("  * the mapper needs the interrupt read() path, which DOES need Input Monitoring.")
