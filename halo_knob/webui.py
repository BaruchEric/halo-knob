"""Local web control panel for halo-knob (htmx + Jinja templates).

  python -m halo_knob.webui        # then open http://127.0.0.1:8842

Reads live agent state from status.json, and writes config.toml (which the running
agent live-reloads) to apply scenarios / tweak settings / edit per-app profiles.
It does not need to be running for the agent to work — it's a configurator + monitor.
"""
import json
import tomllib

from flask import Flask, abort, render_template, request

from . import config, scenarios
from .config import CLICK_ACTIONS, ROTATE_ACTIONS

HOST, PORT = "127.0.0.1", 8842

ICONS = {
    "scroll": "📜", "volume": "🔊", "zoom": "🔍", "hscroll": "↔️", "brightness": "☀️",
    "tabs": "🗂️", "media_seek": "⏭️", "arrows_v": "↕️", "arrows_h": "⬅️➡️",
    "undo": "↩️", "none": "○",
}

app = Flask(__name__, template_folder="templates", static_folder="static")


def read_status():
    try:
        return json.loads((config.CONFIG_DIR / "status.json").read_text())
    except (OSError, ValueError):
        return None


def read_raw():
    try:
        with open(config.CONFIG_PATH, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, ValueError):
        raw = {}
    return raw.get("settings", {}), raw.get("profiles", {})


def write_raw(settings, profiles):
    config.CONFIG_PATH.write_text(scenarios.dump_toml(settings, profiles))


def ctx():
    settings, profiles = read_raw()
    try:
        raw_text = config.CONFIG_PATH.read_text()
    except OSError:
        raw_text = ""
    return dict(scenarios=scenarios.SCENARIOS, active=scenarios.active_id(),
                status=read_status(), settings=settings, profiles=profiles,
                rotate_actions=sorted(ROTATE_ACTIONS), click_actions=sorted(CLICK_ACTIONS),
                icons=ICONS, text=raw_text, ok=None, msg="")


@app.route("/")
def index():
    config.ensure_config()
    return render_template("index.html", **ctx())


@app.route("/status")
def status():
    return render_template("_status.html", status=read_status(), icons=ICONS)


@app.route("/scenario/<sid>", methods=["POST"])
def apply_scenario(sid):
    if not scenarios.apply(sid):
        abort(404)
    return render_template("_scenarios.html", scenarios=scenarios.SCENARIOS, active=sid)


@app.route("/toggle-invert", methods=["POST"])
def toggle_invert():
    settings, profiles = read_raw()
    settings["invert_direction"] = not settings.get("invert_direction", False)
    write_raw(settings, profiles)
    return render_template("_settings.html", settings=settings)


@app.route("/setting", methods=["POST"])
def set_setting():
    key = request.form["key"]
    val = int(request.form["value"])
    settings, profiles = read_raw()
    settings[key] = val
    write_raw(settings, profiles)
    return render_template("_settings.html", settings=settings)


@app.route("/profile/<bundle>", methods=["POST"])
def update_profile(bundle):
    field, value = request.form["field"], request.form["value"]
    settings, profiles = read_raw()
    profiles.setdefault(bundle, {})[field] = value
    write_raw(settings, profiles)
    return ("", 204)


@app.route("/raw", methods=["GET", "POST"])
def raw_config():
    if request.method == "POST":
        text = request.form.get("toml", "")
        try:
            tomllib.loads(text)  # validate before saving
        except tomllib.TOMLDecodeError as e:
            return render_template("_raw_result.html", ok=False, msg=str(e), text=text)
        config.CONFIG_PATH.write_text(text)
        scenarios.clear_active()
        return render_template("_raw_result.html", ok=True, msg="saved — agent will reload", text=text)
    return render_template("_raw_result.html", ok=None, msg="", text=config.CONFIG_PATH.read_text())


def main():
    config.ensure_config()
    print(f"halo-knob control panel → http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
