#!/usr/bin/env python3
"""Fast-feedback knob monitor. Prints each report instantly, exits early on a
good sample, and ends with a one-line verdict on whether the read path is live.

Usage: monitor.py [seconds]   (default 60)
"""
import hid, time, sys

VID, PID = 0x303A, 0x4001
WINDOW = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0


def parse(r):
    if not r or r[0] != 0x01 or len(r) < 3:
        return None
    raw16 = r[1] | (r[2] << 8)
    dial = raw16 >> 1
    if dial & 0x4000:
        dial -= 0x8000
    return raw16 & 0x1, dial


def main():
    h = hid.device()
    try:
        h.open(VID, PID)
    except Exception as e:
        print(f"open failed: {e}")
        sys.exit(1)
    h.set_nonblocking(True)
    print(f">>> MONITOR LIVE ({WINDOW:.0f}s) — TURN THE KNOB NOW (CW, then CCW, then press) <<<\n",
          flush=True)

    events = []
    t0 = time.time(); last = t0; last_beat = t0
    pos = neg = False
    while True:
        now = time.time()
        if now - t0 > WINDOW:
            break
        d = h.read(8)
        if d:
            p = parse(d)
            if p is None:
                continue
            btn, dial = p
            events.append((now - t0, btn, dial))
            print(f"  {now - t0:5.2f}s  btn={btn}  dial={dial:+5d}", flush=True)
            last = now
            if dial > 0: pos = True
            elif dial < 0: neg = True
        else:
            rot = sum(1 for e in events if e[2] != 0)
            if pos and neg and rot >= 6 and now - last > 2.5 and now - t0 > 3:
                break
            if now - last_beat >= 5.0:
                print(f"  ...listening ({now - t0:.0f}s elapsed, {len(events)} reports so far) "
                      f"— keep turning", flush=True)
                last_beat = now
            time.sleep(0.003)
    h.close()

    print("\n" + "=" * 56)
    if not events:
        print("VERDICT: ❌ STILL BLOCKED — no reports. Input Monitoring is not")
        print("         active for kitty (net.kovidgoyal.kitty) for THIS process.")
        return
    print(f"VERDICT: ✅ READ PATH LIVE — {len(events)} reports captured.")
    rots = [e for e in events if e[2] != 0]
    if rots:
        mags = sorted({abs(e[2]) for e in rots})
        print(f"  smallest step: {mags[0]} units = {mags[0]/10:.1f}° | magnitudes seen: {mags}")
        first = "positive(+)" if rots[0][2] > 0 else "negative(-)"
        print(f"  first rotation was {first}  (you turned CW first -> CW = {first})")
    tp = [e for e in events if e[1] == 1 and e[2] != 0]
    print(f"  press-and-turn reports: {len(tp)}  ->",
          "USABLE" if tp else "none seen (button may be press-only / not tried)")
    presses = [e for e in events if e[1] == 1]
    print(f"  button-down reports: {len(presses)}  ->",
          "PRESS WORKS" if presses else "no press detected")


if __name__ == "__main__":
    main()
