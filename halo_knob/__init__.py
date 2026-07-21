"""halo-knob — a macOS userspace driver for the HALO TOUCH dock's rotary knob.

Reads the knob's HID reports (via an exclusive IOKit *seize*, the only way macOS
lets us see them) and maps rotation / press into scroll, zoom, volume, media and
arbitrary keystrokes, with per-app profiles.
"""

__version__ = "1.0.0"

VENDOR_ID = 0x303A
PRODUCT_ID = 0x4001
