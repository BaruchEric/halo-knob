"""The mapper: turns raw (button, dial) reports into actions using the active profile.

Input model
-----------
* rotate (no button)        -> profile's active rotate action (cycled by modes)
* rotate while button held  -> profile's held_rotate action (a secondary axis)
* short press + release      -> click  (deferred to disambiguate from double-click)
* two quick presses          -> double_click
* press held past threshold  -> long_press (fires immediately, no release needed)

Button state is latched from button-only reports (dial == 0) so it survives
rotation reports regardless of what bit0 carries mid-turn.
"""
import threading
import time

from . import actions
from .config import Config


class State:
    """Shared between reader thread, mapper, and the menu bar (main thread)."""

    def __init__(self, config: Config):
        self.lock = threading.RLock()
        self.config = config
        self.current_bundle = None
        self.paused = False
        self.invert = config.settings.invert_direction
        self.mode_index = {}          # profile_name -> int
        # live display info (read by the menu bar)
        self.active_profile_name = "default"
        self.active_rotate = config.default.rotate
        self.last_action = ""

    def reload(self, config: Config):
        with self.lock:
            self.config = config
            self.invert = config.settings.invert_direction
            self.mode_index.clear()


_ROTATE_MEDIA = {"up": actions.MK_SOUND_UP, "down": actions.MK_SOUND_DOWN}
_BRIGHT_MEDIA = {"up": actions.MK_BRIGHT_UP, "down": actions.MK_BRIGHT_DOWN}

# Discrete navigation actions rate-limited so one flick of the wrist == one step
# (otherwise a single turn skips many tracks / thrashes through tabs).
_DEBOUNCE = {"media_seek": 0.45, "tabs": 0.30, "arrows_h": 0.22}


class Mapper:
    def __init__(self, state: State, on_change=None):
        self.state = state
        self._on_change = on_change or (lambda: None)  # notify menu to refresh
        self._accum = 0
        self._held = False
        self._rotated_while_held = False
        self._press_ts = 0.0
        self._long_fired = False
        self._long_timer = None
        self._single_timer = None
        self._last_discrete = {}   # action -> last fire time (for debounce)

    # ---- entry point (called on the reader thread) ----
    def handle(self, button, dial):
        if dial != 0:
            self._on_rotate(dial)
        else:
            self._on_button(button)

    # ---- rotation ----
    def _on_rotate(self, dial):
        st = self.state
        with st.lock:
            if st.paused:
                return
            settings = st.config.settings
            raw_dir = 1 if dial > 0 else -1
            eff = raw_dir * (-1 if st.invert else 1)
            self._accum += eff
            if abs(self._accum) < settings.steps_per_action:
                return
            direction = "up" if self._accum > 0 else "down"
            self._accum -= settings.steps_per_action * (1 if self._accum > 0 else -1)

            name, profile = st.config.profile_for(st.current_bundle)
            if self._held and profile.held_rotate != "none":
                self._rotated_while_held = True
                action = profile.held_rotate
            else:
                action = self._active_rotate(name, profile)
            st.active_profile_name, st.active_rotate = name, self._active_rotate(name, profile)
        self._do_rotate(action, direction, profile)
        self._on_change()

    def _active_rotate(self, name, profile):
        modes = profile.modes or [profile.rotate]
        idx = self.state.mode_index.get(name, 0) % len(modes)
        return modes[idx]

    def _do_rotate(self, action, direction, profile):
        up = direction == "up"
        settings = self.state.config.settings
        if action in ("scroll", "hscroll") and settings.invert_scroll:
            up = not up   # scroll decoupled from volume/zoom (e.g. CW = up volume, down scroll)
        lines = settings.scroll_lines
        deb = _DEBOUNCE.get(action)
        if deb is not None:
            now = time.monotonic()
            if now - self._last_discrete.get(action, 0.0) < deb:
                return
            self._last_discrete[action] = now
        try:
            if action == "scroll":
                actions.scroll(lines if up else -lines)
            elif action == "hscroll":
                actions.hscroll(lines if up else -lines)
            elif action == "volume":
                actions.media_key(_ROTATE_MEDIA[direction])
            elif action == "brightness":
                actions.media_key(_BRIGHT_MEDIA[direction])
            elif action == "zoom":
                actions.combo("cmd+=" if up else "cmd+-")
            elif action == "tabs":
                actions.combo("cmd+shift+]" if up else "cmd+shift+[")
            elif action == "media_seek":
                actions.media_key(actions.MK_NEXT if up else actions.MK_PREV)
            elif action == "arrows_v":
                actions.combo("up" if up else "down")
            elif action == "arrows_h":
                actions.combo("right" if up else "left")
            elif action == "undo":
                actions.combo("cmd+shift+z" if up else "cmd+z")
            self.state.last_action = f"{action} {'up' if up else 'down'}"
        except Exception:
            pass

    # ---- button ----
    def _on_button(self, button):
        if button == 1:
            self._press_down()
        else:
            self._press_up()

    def _press_down(self):
        st = self.state
        with st.lock:
            if st.paused:
                return
            self._held = True
            self._rotated_while_held = False
            self._long_fired = False
            self._press_ts = time.monotonic()
            long_ms = st.config.settings.long_press_ms
        self._cancel(self._long_timer)
        self._long_timer = threading.Timer(long_ms / 1000.0, self._on_long_press)
        self._long_timer.daemon = True
        self._long_timer.start()

    def _press_up(self):
        st = self.state
        self._held = False
        self._cancel(self._long_timer)
        if self._rotated_while_held or self._long_fired:
            return  # press-and-turn or long-press already consumed it
        with st.lock:
            if st.paused:
                return
            name, profile = st.config.profile_for(st.current_bundle)
            dbl = profile.double_click
        if dbl == "none":
            self._fire_click(profile.click)  # no double to wait for
            return
        if self._single_timer is not None:   # a click is already pending -> this is a double
            self._cancel(self._single_timer)
            self._single_timer = None
            self._fire_click(dbl)
        else:
            gap = st.config.settings.double_click_ms / 1000.0
            self._single_timer = threading.Timer(gap, self._fire_single, args=(profile.click,))
            self._single_timer.daemon = True
            self._single_timer.start()

    def _fire_single(self, click_action):
        self._single_timer = None
        self._fire_click(click_action)

    def _on_long_press(self):
        st = self.state
        with st.lock:
            if not self._held or self._rotated_while_held or st.paused:
                return
            self._long_fired = True
            name, profile = st.config.profile_for(st.current_bundle)
            action = profile.long_press
        self._fire_click(action)

    def _fire_click(self, action):
        if not action or action == "none":
            return
        try:
            if action.startswith("keystroke:"):
                actions.combo(action.split(":", 1)[1])
            elif action == "playpause":
                actions.media_key(actions.MK_PLAY)
            elif action == "mute":
                actions.media_key(actions.MK_MUTE)
            elif action == "click":
                actions.mouse_click()
            elif action == "mission_control":
                actions.combo("ctrl+up")
            elif action == "cycle_mode":
                self._cycle_mode()
            self.state.last_action = action
        except Exception:
            pass
        self._on_change()

    def _cycle_mode(self):
        st = self.state
        with st.lock:
            name, profile = st.config.profile_for(st.current_bundle)
            modes = profile.modes or [profile.rotate]
            st.mode_index[name] = (st.mode_index.get(name, 0) + 1) % len(modes)
            st.active_rotate = modes[st.mode_index[name]]
            st.active_profile_name = name

    @staticmethod
    def _cancel(timer):
        if timer is not None:
            timer.cancel()
