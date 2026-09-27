#!/usr/bin/env bash
# uninstall.sh - stop the Logbook LaunchAgent and remove its plist. Your data
# (data/, config.json) and the log file are left alone.
#
# Overrides: PORT (default 8787), LOGBOOK_LABEL (default: config.json
# launchdLabel, else local.logbook). If PORT is set and the installed agent
# serves a different port, nothing is removed unless LOGBOOK_REPLACE=1.
set -euo pipefail

cd "$(dirname "$0")"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Nothing to uninstall: install.sh only sets up a macOS LaunchAgent."
  exit 0
fi

PORT_GIVEN="${PORT:-}"
PORT="${PORT:-8787}"
LABEL="${LOGBOOK_LABEL:-$(python3 -c 'import json; print(json.load(open("config.json")).get("launchdLabel") or "local.logbook")' 2>/dev/null || echo local.logbook)}"
TARGET="gui/$(id -u)/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

old_port="$(python3 -c '
import plistlib, sys
try:
    print(plistlib.load(open(sys.argv[1], "rb")).get("EnvironmentVariables", {}).get("PORT", ""))
except Exception:
    pass
' "$PLIST" 2>/dev/null || true)"
if [ -n "$PORT_GIVEN" ] && [ -n "$old_port" ] && [ "$old_port" != "$PORT_GIVEN" ] \
   && [ "${LOGBOOK_REPLACE:-0}" != 1 ]; then
  echo "The LaunchAgent labelled $LABEL serves port $old_port, not $PORT_GIVEN; nothing removed." >&2
  echo "Set LOGBOOK_LABEL to the agent you meant, or LOGBOOK_REPLACE=1 to remove $LABEL anyway." >&2
  exit 1
fi
[ -n "$old_port" ] && PORT="$old_port"

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
