# HALO TOUCH knob — HID report format

**Status:** ✅ **FULLY CONFIRMED with live capture** (261 reports, 2026-07-20). Layout was
derived from the HID **report descriptor** and every empirical constant is now verified
against real knob input. See "Confirmed constants" at the bottom.

> ## ⚠️ CRITICAL READ REQUIREMENT — the device must be SEIZED
> macOS binds its own HID driver to this Surface-Dial-class device and **swallows every
> interrupt report** from any *shared* reader. Stock `hidapi` (and the `hid` Python package)
> open shared → they get **zero reports**, even with Input Monitoring granted. The knob only
> reads when opened with **`kIOHIDOptionsTypeSeizeDevice`** via IOKit's `IOHIDManager`
> (exclusive access, matched to *only* VID `0x303A`/PID `0x4001` so nothing else is seized).
> This is why the reference `mac-dial` project ships a patched hidapi. **The mapper reads via
> the IOKit seize path** (see `seize_read.py`), not via stock hidapi.
>
> Two things are both required: (1) Input Monitoring TCC grant for the reading process
> (verify with `IOHIDCheckAccess(kIOHIDRequestTypeListenEvent)` == 0), and (2) seizing.
> Diagnosing these took a while — `access_check.py` and `seize_read.py` capture the method.

## Device identity

| | |
|---|---|
| VID | `0x303A` (Espressif — ESP32-S3 native USB) |
| PID | `0x4001` |
| Manufacturer / Product | `N7 Workshop` / `ESP USB DEVICE` |
| Transport | **USB HID** (native ESP32-S3 USB — directly readable, not BLE) |
| Top-level usage | Generic Desktop → **System Multi-Axis Controller** (`0x01`/`0x0E`) |
| Child collection | Digitizer → **Puck** (`0x0D`/`0x21`) |

This is a **Microsoft Surface Dial (RadialController) emulation** — i.e. the dock is on
firmware **1.3.0+**, not the 1.2.3 plain-volume mode. macOS has no RadialController driver,
so the OS enumerates it but does nothing with it — exactly why a userspace reader works.
Because it's a multi-axis controller (not a keyboard/mouse), macOS does **not** seize it, so
`hidapi` opens it fine (confirmed: we read its report descriptor and opened it without error).

## Raw report descriptor (56 bytes)

```
05 01 09 0E A1 01 85 01 05 0D 09 21 A1 00 05 09 09 01 95 01 75 01
15 00 25 01 81 02 05 01 09 37 95 01 75 0F 55 0F 65 14 36 F0 F1 46
10 0E 16 F0 F1 26 10 0E 81 06 C0 C0
```

Decoded:

```
Usage Page (Generic Desktop)
Usage (System Multi-Axis Controller)      ; 0x0E
Collection (Application)
  Report ID (1)                           ; 0x85 0x01  -> every report starts with 0x01
  Usage Page (Digitizer)
  Usage (Puck)                            ; 0x21
  Collection (Physical)
    Usage Page (Button)
    Usage (Button 1)
    Report Count (1) / Report Size (1)    ; 1 bit
    Logical Min 0 / Max 1
    Input (Data,Var,Abs)                  ; <-- BUTTON: 1 bit, absolute (1=down)
    Usage Page (Generic Desktop)
    Usage (Dial)                          ; 0x37
    Report Count (1) / Report Size (15)   ; 15 bits
    Unit Exponent (-1) / Unit (English Rotation = degrees)
    Physical/Logical Min -3600 / Max 3600
    Input (Data,Var,Rel)                  ; <-- ROTATION: 15 bits, RELATIVE
  End Collection
End Collection
```

## Report layout — **3 bytes**, Report ID 1

`hidapi`'s `read()` on macOS returns the report ID as the first byte, so each report is:

```
byte[0] = 0x01              report ID (constant)
byte[1] = R R R R R R R B   B = button bit (bit0); R = low 7 bits of dial
byte[2] = R R R R R R R R    high 8 bits of dial
```

Bit packing is LSB-first (standard HID): treat `byte[1] | (byte[2] << 8)` as one
little-endian 16-bit word `raw16`:

- **Button:** `raw16 & 0x1`  → `1` = pressed, `0` = released.
- **Rotation:** `raw16 >> 1` → a **15-bit signed** value; sign-extend from bit 14:
  `dial = raw16 >> 1; if dial & 0x4000: dial -= 0x8000`.

`dial` is a **relative** angular delta in **tenths of a degree** (logical ±3600 = ±360.0°).
It is nonzero only on rotation reports; button-only reports carry `dial = 0`.

### Reference decoder

```python
def parse(report):                 # report = bytes from hid.read(8)
    if not report or report[0] != 0x01:
        return None
    raw16  = report[1] | (report[2] << 8)
    button = raw16 & 0x1
    dial   = raw16 >> 1
    if dial & 0x4000:              # sign-extend 15-bit
        dial -= 0x8000
    return button, dial            # dial in 0.1° units; +/- = CW/CCW (sign TBD live)
```

## Confirmed constants (live capture, 261 reports via seized IOKit read)

Distinct payloads observed and their decode (payload = `data[1]`, `data[2]`; `data[0]`=report id):

| raw (id b1 b2) | button | dial | meaning |
|---|---|---|---|
| `01 C8 00` | 0 | `+100` = +10.0° | one detent, one direction |
| `01 38 FF` | 0 | `-100` = −10.0° | one detent, other direction |
| `01 01 00` | 1 | 0 | button pressed down |
| `01 00 00` | 0 | 0 | button released / neutral |

1. **Per-detent magnitude: exactly ±100 units (±10.0°)** — the firmware emits **one report
   per physical detent click**, always ±100, never partial or accumulating. So each rotation
   report = one tick; map 1 report → 1 action step (no accumulation threshold needed, though a
   configurable steps-per-action divisor is still useful for fine control).
2. **Direction = sign of `dial`.** `+100` and `-100` are the two directions. Per HID Dial
   convention CW = positive; expose an `invert_direction` config flag so the user flips it if
   it feels backwards (physical CW/CCW wasn't pinned down during the back-and-forth capture).
3. **Button works.** `raw16 & 1`: `01 01 00` = down, `01 00 00` = up. dial is 0 during a pure
   press. (Press-and-turn — button held *while* rotating — was not exercised in this capture;
   detect at runtime: a report with `button==1 && dial!=0`.)

### Canonical decoder (as used against the IOKit seize callback)

```python
def parse(buf):                    # buf = report bytes from the IOHIDDevice input callback
    if not buf or buf[0] != 0x01 or len(buf) < 3:
        return None
    raw16  = buf[1] | (buf[2] << 8)    # NOTE: buf[0] is the report id; payload starts at buf[1]
    button = raw16 & 0x1               # 1 = pressed
    dial   = raw16 >> 1
    if dial & 0x4000:                  # sign-extend 15-bit
        dial -= 0x8000
    return button, dial                # dial in 0.1° units; +/-100 per detent
```
