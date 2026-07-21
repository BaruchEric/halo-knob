#!/usr/bin/env bash
# Install halo-knob as a login LaunchAgent (starts at login, stays resident).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/.venv/bin/python"
LABEL="com.beric.halo-knob"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -x "$PY" ]; then
    echo "!! venv python not found at $PY"
    echo "   Create it first:"
    echo "     cd $DIR && uv venv --python 3.13 && \\"
    echo "       uv pip install rumps pyobjc-framework-Quartz pyobjc-framework-Cocoa hidapi"
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s#__PYTHON__#$PY#g" -e "s#__DIR__#$DIR#g" \
    "$DIR/$LABEL.plist" > "$PLIST"

# Stop any foreground/terminal copy first. The knob is opened with an EXCLUSIVE
# seize, so a lingering second instance would make the agent fail to open and
# look broken. (Also don't keep `python -m halo_knob` running in a terminal.)
pkill -f 'halo_knob' 2>/dev/null || true
sleep 0.5

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "✓ LaunchAgent loaded: $PLIST"
echo "  logs: $DIR/halo-knob.log"
echo

cat <<'EOF'
────────────────────────────────────────────────────────────────────────
ONE-TIME PERMISSIONS (required — the agent can't read the knob without them)

The agent now runs under launchd, so the grant attaches to the *python
binary*, not your terminal. Two toggles:

  1. Input Monitoring  — REQUIRED to read the knob (we seize the device).
  2. Accessibility     — needed for keystroke/zoom actions (scroll & volume
                         work without it).

Opening both panes now. In each, find "Python" (or the .venv/bin/python
path) and switch it ON, then run ./install.sh again (or reboot) so the
freshly-granted agent restarts.
────────────────────────────────────────────────────────────────────────
EOF

open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent" || true
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" || true

# nudge macOS into registering the binary in the Input Monitoring list
"$PY" - <<'PYEOF' 2>/dev/null || true
import ctypes
io = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
io.IOHIDRequestAccess.restype = ctypes.c_bool
io.IOHIDRequestAccess.argtypes = [ctypes.c_uint32]
io.IOHIDRequestAccess(1)  # kIOHIDRequestTypeListenEvent — triggers the prompt/registration
PYEOF

echo
echo "After enabling the toggles, run:  launchctl kickstart -k gui/$(id -u)/$LABEL"
