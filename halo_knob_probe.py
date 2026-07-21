#!/usr/bin/env python3
"""
halo_knob_probe.py - find out how the HALO TOUCH knob talks to macOS.

Two modes:
  list           dump every HID device macOS sees (find the HALO TOUCH here)
  watch VID PID  stream raw input reports from one device
                 (turn the knob / press it to see how rotation is encoded)

Setup:
  pip install hidapi

Permission (important on modern macOS):
  System Settings > Privacy & Security > Input Monitoring
  -> enable your terminal app (Terminal / iTerm), then fully quit & reopen it.
  Without this, reads return nothing.

Usage:
  python3 halo_knob_probe.py list
  python3 halo_knob_probe.py watch 0x303A 0x1001
"""

import sys
import time

try:
    import hid
except ImportError:
    sys.exit("Missing dependency. Run:  pip install hidapi")

# VIDs worth recognizing:
#   0x303A = Espressif -> the ESP32-S3's native USB (definitely readable over USB)
#   0x045E = Microsoft -> a Surface Dial identity (emulation; may be USB or BLE)
KNOWN = {
    0x303A: "Espressif (ESP32-S3 native USB)",
    0x045E: "Microsoft (Surface Dial identity)",
}


def list_devices():
    seen = set()
    for d in hid.enumerate():
        key = (d["vendor_id"], d["product_id"], d["usage_page"], d["usage"])
        if key in seen:
            continue
        seen.add(key)
        vid, pid = d["vendor_id"], d["product_id"]
        tag = f"   <-- {KNOWN[vid]}" if vid in KNOWN else ""
        man = d.get("manufacturer_string") or "?"
        prod = d.get("product_string") or "?"
        print(
            f"VID 0x{vid:04X}  PID 0x{pid:04X}  "
            f"usage_page 0x{d['usage_page']:04X} usage 0x{d['usage']:02X}  "
            f"| {man} - {prod}{tag}"
        )
    print("\nFind the knob above (Espressif/Microsoft tag, or the product name), then run:")
    print("  python3 halo_knob_probe.py watch 0xVID 0xPID")


def watch(vid, pid):
    h = hid.device()
    try:
        h.open(vid, pid)
    except Exception as e:
        sys.exit(
            f"Could not open device: {e}\n"
            "If it's keyboard-like, macOS may have seized it; if it's BLE-only, "
            "hidapi (USB) won't see it -- tell me and we'll go another route."
        )
    h.set_nonblocking(True)
    print(f"Opened VID 0x{vid:04X} PID 0x{pid:04X}.")
    print("Turn the knob clockwise, then counter-clockwise, then press it. Ctrl-C to stop.\n")
    try:
        while True:
            data = h.read(64)
            if data:
                print(" ".join(f"{b:02X}" for b in data))
            time.sleep(0.003)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        h.close()


def main():
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "list":
        list_devices()
    elif len(args) == 3 and args[0] == "watch":
        watch(int(args[1], 16), int(args[2], 16))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
