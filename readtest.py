#!/usr/bin/env python3
"""Decode the knob's report descriptor + a short live-read test (no knob-turn needed to check the pipe)."""
import hid, time

VID, PID = 0x303A, 0x4001

DESC = bytes.fromhex(
    "05 01 09 0E A1 01 85 01 05 0D 09 21 A1 00 05 09 09 01 95 01 75 01 "
    "15 00 25 01 81 02 05 01 09 37 95 01 75 0F 55 0F 65 14 36 F0 F1 46 "
    "10 0E 16 F0 F1 26 10 0E 81 06 C0 C0".replace(" ", "")
)

# minimal item walk to confirm report ID + total input bits
i, report_id, input_bits = 0, None, 0
size = count = 0
while i < len(DESC):
    b = DESC[i]; tag = b & 0xFC; n = b & 0x03; n = 4 if n == 3 else n
    data = int.from_bytes(DESC[i+1:i+1+n], "little") if n else 0
    if tag == 0x84: report_id = data
    elif tag == 0x74: size = data
    elif tag == 0x94: count = data
    elif tag == 0x80: input_bits += size * count   # Input item
    i += 1 + n
print(f"report_id={report_id}  total input payload bits={input_bits} "
      f"({input_bits//8}+{input_bits%8} bits) -> report length w/ ID = {1 + (input_bits+7)//8} bytes")

# live read attempt
h = hid.device()
try:
    h.open(VID, PID)
except Exception as e:
    raise SystemExit(f"open failed: {e}")
h.set_nonblocking(True)
print("Reading for 2s (I can't turn the knob; this only checks for errors / permission)...")
t0 = time.time(); got = 0
while time.time() - t0 < 2.0:
    d = h.read(8)
    if d:
        got += 1
        print("  report:", " ".join(f"{x:02X}" for x in d))
    time.sleep(0.003)
print(f"done. reports seen while idle: {got}")
h.close()
