#!/usr/bin/env bash
# Remove the halo-knob LaunchAgent.
set -euo pipefail
LABEL="com.beric.halo-knob"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ removed $PLIST (the knob returns to its default macOS behavior)."
