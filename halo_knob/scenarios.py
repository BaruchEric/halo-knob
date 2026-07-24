"""Scenarios: curated, one-click configurations for different ways of working.

Applying a scenario simply rewrites ~/.config/halo-knob/config.toml — which the
running agent live-reloads — so switching contexts is instant. Each scenario is a
plain Python structure; render_toml() serialises it to the TOML the agent reads.
"""
from dataclasses import dataclass, field

from . import config

BASE_SETTINGS = {
    "invert_direction": False,
    "invert_scroll": False,    # decouple scroll from volume/zoom (rarely needed)
    "scroll_lines": 3,
    "steps_per_action": 1,
    "double_click_ms": 350,
    "long_press_ms": 550,
    "show_menubar": True,
}


@dataclass
class Scenario:
    id: str
    name: str
    icon: str
    tagline: str
    settings: dict = field(default_factory=dict)
    profiles: dict = field(default_factory=dict)

    def full_settings(self):
        return {**BASE_SETTINGS, **self.settings}


SCENARIOS = [
    Scenario(
        "balanced", "Balanced", "◍", "Sensible defaults for everyday use",
        profiles={
            "default": dict(rotate="scroll", held_rotate="volume", click="playpause",
                            double_click="cycle_mode", long_press="mute",
                            modes=["scroll", "volume", "zoom"]),
            "com.google.Chrome": dict(rotate="zoom", held_rotate="scroll", click="click",
                                      long_press="mission_control", modes=["zoom", "scroll", "tabs"]),
            "com.apple.Safari": dict(rotate="zoom", held_rotate="scroll",
                                     modes=["zoom", "scroll", "tabs"]),
            "com.microsoft.VSCode": dict(rotate="scroll", held_rotate="zoom",
                                         click="keystroke:cmd+p", modes=["scroll", "zoom"]),
            "com.apple.Music": dict(rotate="volume", held_rotate="media_seek", click="playpause",
                                    long_press="mute", modes=["volume", "scroll"]),
            "com.apple.finder": dict(rotate="scroll", held_rotate="zoom", click="click",
                                     modes=["scroll", "zoom"]),
        },
    ),
    Scenario(
        "reader", "Reader", "📖", "Long docs & articles — scroll first, space to page",
        settings={"scroll_lines": 5},
        profiles={
            "default": dict(rotate="scroll", held_rotate="hscroll", click="keystroke:space",
                            double_click="cycle_mode", long_press="keystroke:cmd+up",
                            modes=["scroll", "zoom"]),
            "com.apple.Preview": dict(rotate="scroll", held_rotate="zoom",
                                      click="keystroke:space", modes=["scroll", "zoom"]),
            "com.apple.Safari": dict(rotate="scroll", held_rotate="zoom",
                                     click="keystroke:space", modes=["scroll", "zoom"]),
        },
    ),
    Scenario(
        "presenter", "Presenter", "🎤", "Slides — rotate to advance, click to black",
        profiles={
            "default": dict(rotate="arrows_h", held_rotate="scroll", click="keystroke:b",
                            double_click="keystroke:escape", long_press="none",
                            modes=["arrows_h", "scroll"]),
            "com.apple.iWork.Keynote": dict(rotate="arrows_h", click="keystroke:b",
                                            modes=["arrows_h", "scroll"]),
            "com.microsoft.Powerpoint": dict(rotate="arrows_h", click="keystroke:b",
                                             modes=["arrows_h", "scroll"]),
            "com.google.Chrome": dict(rotate="arrows_h", held_rotate="scroll",
                                      modes=["arrows_h", "scroll"]),
        },
    ),
    Scenario(
        "editor", "Editor", "💻", "Code — scroll, zoom font, quick-open, undo dial",
        profiles={
            "default": dict(rotate="scroll", held_rotate="zoom", click="keystroke:cmd+p",
                            double_click="cycle_mode", long_press="keystroke:cmd+shift+p",
                            modes=["scroll", "zoom", "undo"]),
            "com.microsoft.VSCode": dict(rotate="scroll", held_rotate="zoom",
                                         click="keystroke:cmd+p", double_click="cycle_mode",
                                         long_press="keystroke:cmd+shift+p",
                                         modes=["scroll", "zoom", "undo"]),
            "com.apple.dt.Xcode": dict(rotate="scroll", held_rotate="zoom",
                                       modes=["scroll", "zoom", "undo"]),
        },
    ),
    Scenario(
        "browser", "Browser Power", "🌐", "Zoom, flick tabs, scroll when held",
        profiles={
            "default": dict(rotate="scroll", held_rotate="zoom", click="click",
                            modes=["scroll", "zoom"]),
            "com.google.Chrome": dict(rotate="zoom", held_rotate="scroll", click="click",
                                      double_click="cycle_mode", long_press="mission_control",
                                      modes=["zoom", "scroll", "tabs"]),
            "com.apple.Safari": dict(rotate="zoom", held_rotate="scroll", click="click",
                                     double_click="cycle_mode", modes=["zoom", "scroll", "tabs"]),
            "com.brave.Browser": dict(rotate="zoom", held_rotate="scroll",
                                      modes=["zoom", "scroll", "tabs"]),
        },
    ),
    Scenario(
        "media", "Media / DJ", "🎧", "Volume dial, seek when held, click to play",
        profiles={
            "default": dict(rotate="volume", held_rotate="media_seek", click="playpause",
                            double_click="mute", long_press="mute", modes=["volume", "scroll"]),
            "com.apple.Music": dict(rotate="volume", held_rotate="media_seek", click="playpause",
                                    double_click="cycle_mode", long_press="mute",
                                    modes=["volume", "media_seek", "scroll"]),
            "com.spotify.client": dict(rotate="volume", held_rotate="media_seek",
                                       click="playpause", modes=["volume", "media_seek"]),
        },
    ),
    Scenario(
        "creative", "Creative", "🎨", "Design apps — zoom canvas, scroll when held",
        profiles={
            "default": dict(rotate="scroll", held_rotate="zoom", click="click",
                            modes=["scroll", "zoom"]),
            "com.figma.Desktop": dict(rotate="zoom", held_rotate="scroll", click="click",
                                      long_press="keystroke:cmd+z", modes=["zoom", "scroll"]),
            "com.adobe.Photoshop": dict(rotate="zoom", held_rotate="scroll",
                                        long_press="keystroke:cmd+z", modes=["zoom", "scroll"]),
        },
    ),
    Scenario(
        "zoombright", "Zoom & Brightness", "🔆", "Accessibility — magnify & dim the screen",
        profiles={
            "default": dict(rotate="zoom", held_rotate="brightness", click="mission_control",
                            double_click="cycle_mode", long_press="mute",
                            modes=["zoom", "brightness", "scroll"]),
        },
    ),
]

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}


# ---- TOML rendering -------------------------------------------------------
def _val(x):
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(_val(i) for i in x) + "]"
    raise TypeError(f"cannot serialise {x!r}")


def dump_toml(settings: dict, profiles: dict, header: list = None) -> str:
    """Serialise a settings dict + profiles dict to the TOML the agent reads."""
    out = list(header or [])
    if out:
        out.append("")
    out.append("[settings]")
    for k, v in settings.items():
        out.append(f"{k} = {_val(v)}")
    out.append("")
    order = ["default"] + [k for k in profiles if k != "default"]
    for key in order:
        prof = profiles.get(key)
        if not prof:
            continue
        out.append("[profiles.default]" if key == "default" else f'[profiles."{key}"]')
        for k, v in prof.items():
            out.append(f"{k} = {_val(v)}")
        out.append("")
    return "\n".join(out) + "\n"


def render_toml(scenario: Scenario) -> str:
    header = [f"# halo-knob — scenario: {scenario.name}  ({scenario.tagline})",
              "# Applied from the web control panel. Edit freely; changes auto-reload."]
    return dump_toml(scenario.full_settings(), scenario.profiles, header)


ACTIVE_MARKER = config.CONFIG_DIR / "active_scenario"


def active_id():
    try:
        return ACTIVE_MARKER.read_text().strip() or None
    except OSError:
        return None


def clear_active():
    try:
        ACTIVE_MARKER.unlink()
    except OSError:
        pass


def apply(scenario_id: str) -> bool:
    scenario = SCENARIOS_BY_ID.get(scenario_id)
    if not scenario:
        return False
    settings = scenario.full_settings()
    # Preserve the user's direction calibration across scenario switches — scenarios
    # change what the dial *does*, not which way it spins.
    import tomllib
    try:
        with open(config.CONFIG_PATH, "rb") as f:
            cur = tomllib.load(f).get("settings", {})
        for k in ("invert_direction", "invert_scroll"):
            if k in cur:
                settings[k] = bool(cur[k])
    except (OSError, ValueError):
        pass
    header = [f"# halo-knob — scenario: {scenario.name}  ({scenario.tagline})",
              "# Applied from the web control panel. Edit freely; changes auto-reload."]
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(dump_toml(settings, scenario.profiles, header))
    ACTIVE_MARKER.write_text(scenario_id)
    return True
