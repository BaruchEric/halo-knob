#!/usr/bin/env python3
"""
Live capture + auto-analysis of the HALO knob (VID 0x303A / PID 0x4001).

Waits for you to interact, decodes every report inline, and prints the three
constants REPORT_FORMAT.md left open (sign, per-detent step, press-and-turn).

Termination: wraps up ~4s after activity stops once it has seen rotation in
both directions + a button press, or after a hard 120s cap.
"""
import hid, time, sys

VID, PID = 0x303A, 0x4001
LOG = "capture.log"


def parse(r):
    if not r or r[0] != 0x01 or len(r) < 3:
        return None
    raw16 = r[1] | (r[2] << 8)
    button = raw16 & 0x1
    dial = raw16 >> 1
    if dial & 0x4000:
        dial -= 0x8000
    return button, dial


def main():
    h = hid.device()
    try:
        h.open(VID, PID)
    except Exception as e:
        sys.exit(f"open failed: {e}")
    h.set_nonblocking(True)

    print(f"Opened {VID:#06x}/{PID:#06x}. ROTATION FIRST (press optional):")
    print("  1) turn CW a good amount     2) turn CCW a good amount")
    print("  3) (optional) press+release  4) (optional) press-and-hold + turn\n", flush=True)

    events = []           # (t, button, dial, rawhex)
    logf = open(LOG, "w")
    t0 = time.time()
    last_activity = t0
    pos = neg = press = False

    while True:
        now = time.time()
        if now - t0 > 120:
            print("\n[hard 120s cap reached]")
            break
        d = h.read(8)
        if d:
            p = parse(d)
            if p is None:
                continue
            button, dial = p
            rawhex = " ".join(f"{b:02X}" for b in d)
            events.append((now - t0, button, dial, rawhex))
            logf.write(f"{now - t0:7.3f}  btn={button}  dial={dial:+5d}  | {rawhex}\n")
            logf.flush()
            print(f"  {now - t0:6.2f}s  btn={button}  dial={dial:+5d}   {rawhex}", flush=True)
            last_activity = now
            if dial > 0:
                pos = True
            elif dial < 0:
                neg = True
            if button:
                press = True
        else:
            # quiet-exit once rotation is captured and things have settled (press optional)
            rot_count = sum(1 for e in events if e[2] != 0)
            if pos and neg and rot_count >= 6 and (now - last_activity > 4.0) and now - t0 > 5:
                print("\n[rotation captured both directions — wrapping up]")
                break
            time.sleep(0.003)

    h.close()
    logf.close()
    analyze(events)


def analyze(events):
    print("\n" + "=" * 60)
    rots = [e for e in events if e[2] != 0]
    presses = [e for e in events if e[1] == 1]
    print(f"reports captured: {len(events)}   rotation reports: {len(rots)}   "
          f"button-down reports: {len(presses)}")
    if not events:
        print("\nNOTHING CAPTURED. If you did turn the knob, this is the macOS")
        print("Input Monitoring permission gate (not a decode problem): the app")
        print("hosting this process lacks Input Monitoring, or wasn't relaunched")
        print("after granting. Fix: grant Input Monitoring to your terminal app,")
        print("fully quit + reopen it, then rerun. See README.")
        return

    if rots:
        deltas = sorted({e[2] for e in rots})
        mags = sorted({abs(e[2]) for e in rots})
        print(f"\ndistinct dial deltas seen: {deltas}")
        print(f"distinct magnitudes (0.1deg units): {mags}")
        print(f"  -> smallest nonzero step ~= {mags[0]} units = {mags[0] / 10:.1f} deg per detent")
        cw = [e for e in rots if e[2] > 0]
        ccw = [e for e in rots if e[2] < 0]
        print(f"  positive(+) deltas: {len(cw)}   negative(-) deltas: {len(ccw)}")
        print("  (you turned CW first, then CCW -> the sign of the FIRST cluster = CW)")
        if rots:
            first_sign = "positive" if rots[0][2] > 0 else "negative"
            print(f"  first rotation delta was {first_sign} -> CW = {first_sign}")

    turn_while_pressed = [e for e in events if e[1] == 1 and e[2] != 0]
    print(f"\npress-and-turn reports (btn=1 AND dial!=0): {len(turn_while_pressed)}")
    print("  -> press-and-turn IS usable" if turn_while_pressed
          else "  -> no rotation seen while pressed (firmware may suppress it, or you didn't try it)")


if __name__ == "__main__":
    main()
