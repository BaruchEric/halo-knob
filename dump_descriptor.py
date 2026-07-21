#!/usr/bin/env python3
"""Dump HID report descriptor(s) for the HALO knob (VID 0x303A PID 0x4001)."""
import hid

VID, PID = 0x303A, 0x4001

paths = [d for d in hid.enumerate(VID, PID)]
print(f"Found {len(paths)} interface(s) for {VID:#06x}/{PID:#06x}\n")

for i, d in enumerate(paths):
    print(f"=== interface {i}: usage_page {d['usage_page']:#06x} usage {d['usage']:#04x} "
          f"iface {d.get('interface_number')} path={d['path']!r}")
    h = hid.device()
    try:
        h.open_path(d["path"])
    except Exception as e:
        print(f"  open_path failed: {e}")
        try:
            h.open(VID, PID)
        except Exception as e2:
            print(f"  open(vid,pid) failed too: {e2}")
            continue
    try:
        desc = h.get_report_descriptor()
        print(f"  report descriptor ({len(desc)} bytes):")
        print("  " + " ".join(f"{b:02X}" for b in desc))
    except Exception as e:
        print(f"  get_report_descriptor failed: {e}")
    finally:
        h.close()
    print()
