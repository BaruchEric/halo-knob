"""HALO SPIN — a knob-controlled game that fully exercises the dial.

Seizes the knob directly (so STOP the resident agent first — only one seizer at a
time) and streams rotation/press events to the browser over Server-Sent Events.
The browser renders the game + the circular "knob screen" HUD.

  # stop the agent, then:
  python -m halo_knob.game        # → http://127.0.0.1:8843
"""
import json
import queue
import threading

from flask import Flask, Response, render_template

from . import reader

HOST, PORT = "127.0.0.1", 8843
app = Flask(__name__, template_folder="templates", static_folder="static")

_subs = set()
_lock = threading.Lock()
_status = {"msg": "starting…", "connected": False}


def _broadcast(evt):
    with _lock:
        for q in list(_subs):
            try:
                q.put_nowait(evt)
            except queue.Full:
                pass


def _on_event(button, dial):
    _broadcast({"t": "rot", "dial": dial} if dial != 0 else {"t": "press", "down": button})


def _on_status(msg):
    _status["msg"] = msg
    _status["connected"] = "listening" in msg or "connected" in msg
    _broadcast({"t": "status", "msg": msg, "connected": _status["connected"]})


_knob = reader.KnobReader(on_event=_on_event, on_status=_on_status)


@app.route("/")
def index():
    return render_template("game.html")


@app.route("/events")
def events():
    q = queue.Queue(maxsize=200)
    with _lock:
        _subs.add(q)

    def stream():
        try:
            yield "retry: 1000\n\n"
            yield f"data: {json.dumps({'t': 'status', **_status})}\n\n"
            while True:
                try:
                    yield f"data: {json.dumps(q.get(timeout=15))}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _lock:
                _subs.discard(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                             "Connection": "keep-alive"})


def main():
    _knob.start()
    print(f"HALO SPIN → http://{HOST}:{PORT}  (stop the resident agent first)")
    app.run(host=HOST, port=PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
