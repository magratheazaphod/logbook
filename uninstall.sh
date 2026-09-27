#!/usr/bin/env bash
# uninstall.sh - stop the Logbook LaunchAgent and remove its plist. Your data
# (data/, config.json) and the log file are left alone.
#
# Overrides: PORT (default 8787, used only to confirm the port is free),
# LOGBOOK_LABEL (default: config.json launchdLabel, else local.logbook).
set -euo pipefail

cd "$(dirname "$0")"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Nothing to uninstall: install.sh only sets up a macOS LaunchAgent." >&2
  exit 1
fi

PORT="${PORT:-8787}"
LABEL="${LOGBOOK_LABEL:-$(python3 -c 'import json; print(json.load(open("config.json")).get("launchdLabel") or "local.logbook")' 2>/dev/null || echo local.logbook)}"
TARGET="gui/$(id -u)/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

found=0
if launchctl print "$TARGET" >/dev/null 2>&1; then
  launchctl bootout "$TARGET" 2>/dev/null || true
  for _ in $(seq 1 25); do
    launchctl print "$TARGET" >/dev/null 2>&1 || break
    sleep 0.2
  done
  echo "Stopped LaunchAgent $LABEL"
  found=1
fi
if [ -f "$PLIST" ]; then
  rm -f "$PLIST"
  echo "Removed $PLIST"
  found=1
fi
if [ "$found" = 0 ]; then
  echo "No LaunchAgent labelled $LABEL is installed (set LOGBOOK_LABEL if you used another)."
  exit 0
fi

for _ in $(seq 1 25); do
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || exit 0
  sleep 0.2
done
echo "Note: something is still listening on port $PORT (not this LaunchAgent)." >&2
