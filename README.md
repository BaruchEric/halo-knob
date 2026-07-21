# halo-knob

A background macOS utility that turns the **HALO TOUCH dock's rotary knob** into a
real Mac input device — scroll, zoom, system volume, media keys, and arbitrary
keyboard shortcuts, with **per-app profiles**. Mac-side only; the device firmware is
never touched.

The dock's knob presents as a **Microsoft Surface Dial** (a "System Multi-Axis
Controller", VID `0x303A` / PID `0x4001`). macOS has no Surface Dial driver, so the
knob normally does nothing — this agent reads its raw HID reports and translates them
into `CGEvent`/`NSEvent` actions.

## How it works (and the one non-obvious catch)

macOS binds its own HID driver to this device and **swallows the interrupt reports**
from any *shared* reader — stock `hidapi` sees literally nothing. The only way to
receive them is to open the device with **`kIOHIDOptionsTypeSeizeDevice`** (exclusive
access, matched to just this VID/PID so nothing else is affected). That's what this
agent does, via IOKit directly. See `REPORT_FORMAT.md` for the full HID decode.

Report = 3 bytes, ID `0x01`: one report per detent, `±100` = `±10°`; button in bit 0.

## Requirements

- macOS, Python 3.11+ (uses stdlib `tomllib`), [`uv`](https://docs.astral.sh/uv/).
- **Input Monitoring** permission (required — to read the seized device).
- **Accessibility** permission (only for keystroke/zoom actions; scroll & volume
  work without it).

## Setup

```sh
cd dev-tools/halo-knob
uv venv --python 3.13
uv pip install rumps pyobjc-framework-Quartz pyobjc-framework-Cocoa hidapi flask
```

Run it in the foreground to try it (grant **Input Monitoring** to your terminal app
first, then relaunch the terminal):

```sh
.venv/bin/python -m halo_knob
```

A `◍` (or the active-mode icon) appears in the menu bar. Turn the knob.

### Install as a login agent (Stage 3)

```sh
./install.sh      # writes ~/Library/LaunchAgents/com.beric.halo-knob.plist, loads it
```

Because launchd runs the agent, the permission grant now attaches to the **python
binary** (not your terminal). `install.sh` opens both permission panes; enable
**Python** in each, then:

```sh
launchctl kickstart -k gui/$(id -u)/com.beric.halo-knob
```

Uninstall: `./uninstall.sh`.

## The input model

| Gesture | Does |
|---|---|
| **Rotate** | the profile's active *rotate* action (CW = up) |
| **Press + rotate** | the profile's *held_rotate* action — a second axis |
| **Click** | the profile's *click* action (default: play/pause) |
| **Double-click** | *double_click* action (default: **cycle mode** — changes what rotate does) |
| **Long-press** | *long_press* action (default: mute) |

Clockwise is "up" everywhere: volume up, zoom in, scroll up. Counter-clockwise is
down (so CCW scrolls the page down). Flip with the menu's **Reverse direction** or
`invert_direction` in config.

## Configuration

Editable TOML at **`~/.config/halo-knob/config.toml`** — saved changes reload
instantly (no restart). See `config.example.toml` for the annotated default.

- **Rotate actions:** `scroll`, `hscroll`, `volume`, `zoom`, `brightness`, `tabs`,
  `media_seek`, `none`.
- **Button actions:** `playpause`, `mute`, `click`, `mission_control`, `cycle_mode`,
  `none`, or `keystroke:<combo>` (e.g. `keystroke:cmd+shift+p`).
- **Profiles** are keyed by bundle id (`com.google.Chrome`, `com.apple.Music`, …).
  Unlisted apps use `[profiles.default]`; listed apps inherit unset fields from it.
- **`modes`** is the list `cycle_mode` (double-click) rotates the active rotate action
  through — one knob, many jobs, shown as an icon in the menu bar.

Find an app's bundle id with: `osascript -e 'id of app "AppName"'`.

## Web control panel & scenarios

A local htmx control panel makes configuring the knob a pleasure — no TOML required:

```sh
.venv/bin/python -m halo_knob.webui     # → http://127.0.0.1:8842
```

- **Live status** — connection, front app, active rotate-mode, last action (polled).
- **Scenarios** — one-click curated presets that reconfigure everything for a context:
  **Balanced · Reader · Presenter · Editor · Browser Power · Media/DJ · Creative ·
  Zoom & Brightness**. Applying one just rewrites `config.toml`, which the agent
  live-reloads — so switching contexts is instant.
- **Settings** — reverse direction, scroll-lines, sensitivity (sliders).
- **Per-app profiles** — edit what the dial does in each app via dropdowns; edits save
  instantly. Plus a validated raw-TOML editor for power users.

The panel reads the agent's live state from `~/.config/halo-knob/status.json` and writes
`config.toml`; it doesn't need to run for the agent to work — it's a configurator + monitor.

## Menu bar

Active-mode icon (🔊/📜/🔍…), the current app · mode, connection status, **Pause**,
**Reverse direction**, **Reload / Open config**, an **Accessibility** shortcut, and
**Quit**.

## Troubleshooting

- **Nothing happens / `⚠︎` in the menu bar** → Input Monitoring isn't active for this
  process. Grant it, then **relaunch** the host (terminal, or `kickstart` the agent) —
  the grant only takes effect on a fresh process.
- **Scroll/volume work but zoom/keystrokes don't** → grant **Accessibility**.
- **"seize failed"** → another reader has the knob (a probe script, or a second copy
  of the agent). Only one owner at a time. Quit the other.
- **Direction reversed** → menu **Reverse direction**, or `invert_direction = true`.

## Files

- `halo_knob/` — the agent (`reader` seize/IOKit, `actions`, `config`, `mapper`, `app`) plus
  the web panel (`webui`, `scenarios`, `templates/`, `static/htmx.min.js`).
- `REPORT_FORMAT.md` — the reverse-engineered HID format + the seize discovery.
- `halo_knob_probe.py`, `seize_read.py`, `access_check.py`, … — discovery/diagnostic tools.

## Roadmap / notes

Python is fast to iterate and de-risks the hard part (seizing). The durable hardening
path is a signed Swift app bundle (IOHIDManager + AppKit): a stable bundle-id holds
its TCC grants across interpreter/venv changes, where the python binary's grant can be
invalidated by a venv rebuild. The architecture here (seize reader → action engine →
per-app profiles) ports directly.
