"""Menu-bar app: wires reader -> mapper, tracks the frontmost app, and live-reloads config.

Everything that touches AppKit UI runs on the main thread (rumps timers). The reader
runs on its own thread and only mutates plain State fields, which the timers read.
"""
import json
import os
import subprocess
import time

import rumps
from AppKit import NSWorkspace

from . import actions, config
from .mapper import Mapper, State
from .reader import KnobReader

ICONS = {
    "scroll": "📜", "volume": "🔊", "zoom": "🔍", "hscroll": "↔️",
    "brightness": "☀️", "tabs": "🗂️", "media_seek": "⏭️",
    "arrows_v": "↕️", "arrows_h": "⬅️➡️", "undo": "↩️", "none": "○",
}
ACCESSIBILITY_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
INPUT_MON_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"


class HaloKnobApp(rumps.App):
    def __init__(self):
        super().__init__("halo-knob", title="◍", quit_button="Quit halo-knob")
        self.state = State(config.load())
        self.reader_status = "starting…"
        self._cfg_mtime = config.mtime()

        # menu
        self.status_item = rumps.MenuItem("—")                 # live app · mode line
        self.reader_item = rumps.MenuItem("—")                 # connection status
        self.pause_item = rumps.MenuItem("Pause", callback=self.toggle_pause)
        self.invert_item = rumps.MenuItem("Reverse direction", callback=self.toggle_invert)
        self.accessibility_item = rumps.MenuItem("Accessibility…", callback=self.open_accessibility)
        self.menu = [
            self.status_item, self.reader_item, None,
            self.pause_item, self.invert_item, None,
            rumps.MenuItem("Reload config", callback=self.reload_cfg),
            rumps.MenuItem("Open config file…", callback=self.open_cfg),
            self.accessibility_item, None,
        ]

        # reader
        self.reader = KnobReader(on_event=self._on_event, on_status=self._on_status)
        self.mapper = Mapper(self.state)
        self.reader.start()

        # timers (main thread)
        rumps.Timer(self._tick_frontmost, 0.2).start()
        rumps.Timer(self._tick_config, 1.0).start()
        rumps.Timer(self._tick_ui, 0.25).start()

    # ---- reader-thread callbacks (no UI here) ----
    def _on_event(self, button, dial):
        self.mapper.handle(button, dial)
        log = os.environ.get("HALO_LOG")
        if log:
            st = self.state
            with open(log, "a") as f:
                f.write(f"{time.time():.3f} evt(btn={button},dial={dial:+d}) "
                        f"app={st.current_bundle} profile={st.active_profile_name} "
                        f"rotate={st.active_rotate} -> {st.last_action}\n")

    def _on_status(self, msg):
        self.reader_status = msg

    # ---- timers (main thread) ----
    def _tick_frontmost(self, _):
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        self.state.current_bundle = app.bundleIdentifier() if app else None

    def _tick_config(self, _):
        m = config.mtime()
        if m != self._cfg_mtime:
            self._cfg_mtime = m
            try:
                self.state.reload(config.load())
                self.reader_status = "config reloaded"
            except Exception as e:
                self.reader_status = f"config error: {e}"

    def _tick_ui(self, _):
        st = self.state
        if not self.reader.opened:
            self.title = "⚠︎"
        elif st.paused:
            self.title = "⏸"
        else:
            self.title = ICONS.get(st.active_rotate, "◍")
        name = st.active_profile_name
        self.status_item.title = f"{name}  ·  ↻ {st.active_rotate}"
        self.reader_item.title = self.reader_status
        self.pause_item.title = "Resume" if st.paused else "Pause"
        self.invert_item.state = 1 if st.invert else 0
        self.accessibility_item.title = (
            "Accessibility: granted ✓" if actions.accessibility_trusted()
            else "⚠ Grant Accessibility (keystrokes/zoom)")
        self._write_status()

    def _write_status(self):
        st = self.state
        payload = {
            "connected": bool(self.reader.opened),
            "paused": bool(st.paused),
            "current_bundle": st.current_bundle,
            "active_profile": st.active_profile_name,
            "active_rotate": st.active_rotate,
            "icon": ICONS.get(st.active_rotate, "◍"),
            "last_action": st.last_action,
            "invert": bool(st.invert),
            "accessibility": actions.accessibility_trusted(),
            "reader_status": self.reader_status,
            "ts": time.time(),
        }
        try:
            tmp = config.CONFIG_DIR / "status.json.tmp"
            config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload))
            tmp.replace(config.CONFIG_DIR / "status.json")
        except OSError:
            pass

    # ---- menu actions ----
    def toggle_pause(self, _):
        self.state.paused = not self.state.paused

    def toggle_invert(self, _):
        with self.state.lock:
            self.state.invert = not self.state.invert

    def reload_cfg(self, _):
        try:
            self.state.reload(config.load())
            self.reader_status = "config reloaded"
        except Exception as e:
            self.reader_status = f"config error: {e}"

    def open_cfg(self, _):
        config.ensure_config()
        subprocess.Popen(["open", str(config.CONFIG_PATH)])

    def open_accessibility(self, _):
        subprocess.Popen(["open", ACCESSIBILITY_PANE])


def main():
    config.ensure_config()
    HaloKnobApp().run()


if __name__ == "__main__":
    main()
