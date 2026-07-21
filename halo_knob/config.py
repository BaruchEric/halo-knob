"""Config: editable TOML at ~/.config/halo-knob/config.toml, auto-reloaded on save.

App profiles inherit any unset field from [profiles.default], so an app entry only
needs to list what it changes.
"""
import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

CONFIG_DIR = Path(os.path.expanduser("~/.config/halo-knob"))
CONFIG_PATH = CONFIG_DIR / "config.toml"

# Rotate actions understood by the mapper (see actions.py for the effect of each):
ROTATE_ACTIONS = {"scroll", "hscroll", "volume", "zoom", "brightness", "tabs", "media_seek",
                  "arrows_v", "arrows_h", "undo", "none"}
# Button actions:
CLICK_ACTIONS = {"playpause", "mute", "click", "mission_control", "cycle_mode", "none"}

DEFAULT_TOML = '''\
# halo-knob configuration — edit and save; changes auto-reload (no restart).
#
# Direction convention: CLOCKWISE = "up"  (volume up / zoom in / scroll up).
# If clockwise goes the wrong way on your unit, set invert_direction = true
# (or use the menu-bar "Reverse direction" toggle).

[settings]
invert_direction = false   # flip if clockwise feels backwards
scroll_lines     = 3       # lines scrolled per detent
steps_per_action = 1       # detents per action tick (raise to desensitize)
double_click_ms  = 350     # max gap to count as a double-click
long_press_ms    = 550     # hold time to trigger a long-press
show_menubar     = true

# ---- Profiles -------------------------------------------------------------
# rotate / held_rotate : scroll | hscroll | volume | zoom | brightness | tabs | media_seek | none
# click / double_click / long_press : playpause | mute | click | mission_control | cycle_mode
#                                     | none | "keystroke:<combo>"  (e.g. "keystroke:cmd+shift+p")
# modes : the list that double-click's "cycle_mode" rotates the active rotate-action through.
#
# App keys are bundle identifiers. Anything not listed uses [profiles.default].

[profiles.default]
rotate       = "scroll"
held_rotate  = "volume"
click        = "playpause"
double_click = "cycle_mode"
long_press   = "mute"
modes        = ["scroll", "volume", "zoom"]

[profiles."com.google.Chrome"]
rotate       = "zoom"
held_rotate  = "scroll"
click        = "click"
long_press   = "mission_control"
modes        = ["zoom", "scroll", "tabs"]

[profiles."com.apple.Safari"]
rotate       = "zoom"
held_rotate  = "scroll"
modes        = ["zoom", "scroll", "tabs"]

[profiles."com.microsoft.VSCode"]
rotate       = "scroll"
held_rotate  = "zoom"
click        = "keystroke:cmd+p"
modes        = ["scroll", "zoom"]

[profiles."com.apple.Music"]
rotate       = "volume"
held_rotate  = "media_seek"
click        = "playpause"
long_press   = "mute"
modes        = ["volume", "scroll"]

[profiles."com.apple.finder"]
rotate       = "scroll"
held_rotate  = "zoom"
click        = "click"
modes        = ["scroll", "zoom"]
'''


@dataclass
class Settings:
    invert_direction: bool = False
    scroll_lines: int = 3
    steps_per_action: int = 1
    double_click_ms: int = 350
    long_press_ms: int = 550
    show_menubar: bool = True


@dataclass
class Profile:
    rotate: str = "scroll"
    held_rotate: str = "none"
    click: str = "none"
    double_click: str = "none"
    long_press: str = "none"
    modes: list = field(default_factory=lambda: ["scroll"])


@dataclass
class Config:
    settings: Settings
    profiles: dict           # bundle_id -> Profile
    default: Profile

    def profile_for(self, bundle_id):
        """(display_name, Profile) for the given frontmost bundle id."""
        if bundle_id and bundle_id in self.profiles:
            return bundle_id, self.profiles[bundle_id]
        return "default", self.default


def ensure_config():
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(DEFAULT_TOML)
    return CONFIG_PATH


def load() -> Config:
    ensure_config()
    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    s = raw.get("settings", {})
    settings = Settings(
        invert_direction=bool(s.get("invert_direction", False)),
        scroll_lines=int(s.get("scroll_lines", 3)),
        steps_per_action=max(1, int(s.get("steps_per_action", 1))),
        double_click_ms=int(s.get("double_click_ms", 350)),
        long_press_ms=int(s.get("long_press_ms", 550)),
        show_menubar=bool(s.get("show_menubar", True)),
    )

    profs = raw.get("profiles", {})
    default = _profile_from(profs.get("default", {}), base=Profile())
    profiles = {}
    for key, val in profs.items():
        if key == "default":
            continue
        profiles[key] = _profile_from(val, base=default)  # inherit unset fields from default
    return Config(settings=settings, profiles=profiles, default=default)


def _profile_from(d: dict, base: Profile) -> Profile:
    return replace(
        base,
        rotate=d.get("rotate", base.rotate),
        held_rotate=d.get("held_rotate", base.held_rotate),
        click=d.get("click", base.click),
        double_click=d.get("double_click", base.double_click),
        long_press=d.get("long_press", base.long_press),
        modes=list(d.get("modes", base.modes)),
    )


def mtime() -> float:
    try:
        return CONFIG_PATH.stat().st_mtime
    except OSError:
        return 0.0
