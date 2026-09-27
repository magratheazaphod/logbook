#!/usr/bin/env bash
# install.sh - run Logbook as a macOS LaunchAgent (starts at login, restarts
# if it crashes). Safe to re-run: an existing install under the same label is
# replaced cleanly. Undo with ./uninstall.sh.
#
# Run it from your normal shell: the agent gets this shell's PATH, so
# `claude` resolves for day summaries.
#
#   ./install.sh               install and health-check
#   ./install.sh --dry-run     print the rendered plist, change nothing
#
# Overrides: PORT (default 8787), LOGBOOK_LABEL (default: config.json
# launchdLabel, else local.logbook), LOGBOOK_LOG (default ~/logbook-server.log).
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd -P)"

DRY_RUN=0
case "${1:-}" in
  "") ;;
  --dry-run|-n) DRY_RUN=1 ;;
  -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

PORT="${PORT:-8787}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "PORT must be a number from 1 to 65535 (got '$PORT')." >&2
  exit 2
fi
LOG="${LOGBOOK_LOG:-$HOME/logbook-server.log}"
LABEL="${LOGBOOK_LABEL:-$(python3 -c 'import json; print(json.load(open("config.json")).get("launchdLabel") or "local.logbook")' 2>/dev/null || echo local.logbook)}"
if ! [[ "$LABEL" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Label '$LABEL' may only contain letters, digits, '.', '_' and '-'." >&2
  exit 2
fi
PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "python3 not found on PATH." >&2
  exit 1
fi
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

render() {
  L_LABEL="$LABEL" L_PYTHON="$PYTHON" L_WORKDIR="$ROOT" L_HOME="$HOME" \
  L_PATH="$PATH" L_PORT="$PORT" L_LOG="$LOG" \
  python3 -c '
import os, sys
from xml.sax.saxutils import escape
text = open(sys.argv[1]).read()
for key in ("LABEL", "PYTHON", "WORKDIR", "HOME", "PATH", "PORT", "LOG"):
    text = text.replace("@" + key + "@", escape(os.environ["L_" + key]))
sys.stdout.write(text)
' "$ROOT/launchd/logbook.plist.template"
}

if [ "$DRY_RUN" = 1 ]; then
  render
  exit 0
fi

if [ "$(uname -s)" != "Darwin" ]; then
  cat >&2 <<MSG
install.sh sets up a macOS LaunchAgent, and this is $(uname -s).
On Linux, run the server directly instead:

  cd $ROOT
  python3 server.py            # then open http://localhost:$PORT

To keep it running, wrap that command in your own systemd user unit,
tmux session or similar.
MSG
  exit 1
fi

UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"
TARGET="$DOMAIN/$LABEL"
URL="http://localhost:$PORT/api/board"

# --- replace an earlier install under this label ----------------------------
if launchctl print "$TARGET" >/dev/null 2>&1; then
  echo "Replacing existing LaunchAgent $LABEL"
  launchctl bootout "$TARGET" 2>/dev/null || true
  for _ in $(seq 1 25); do          # bootout is asynchronous; wait for it
    launchctl print "$TARGET" >/dev/null 2>&1 || break
    sleep 0.2
  done
  for _ in $(seq 1 25); do          # and for its server to release the port
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.2
  done
fi

# --- refuse if something else holds the port --------------------------------
if holder=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null) && [ -n "$holder" ]; then
  echo "Port $PORT is already in use, so Logbook would fail to start:" >&2
  echo "$holder" | sed 's/^/  /' >&2
  echo >&2
  echo "Stop that process (it may be a hand-started 'python3 server.py', or" >&2
  echo "another Logbook LaunchAgent under a different label), or pick another" >&2
  echo "port:  PORT=8788 ./install.sh" >&2
  exit 1
fi

# --- write and load the plist -----------------------------------------------
mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
tmp="$(mktemp "$PLIST.XXXXXX")"
render > "$tmp"
if ! plutil -lint -s "$tmp"; then
  rm -f "$tmp"
  echo "Rendered plist failed validation; nothing installed." >&2
  exit 1
fi
mv "$tmp" "$PLIST"
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed $PLIST"

# --- health check -----------------------------------------------------------
for _ in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null || true)
  if [ "$code" = "200" ]; then
    echo "Logbook running at http://localhost:$PORT  (label $LABEL, log $LOG)"
    [ "$PORT" = 8787 ] || echo "Note: ./restart.sh needs PORT=$PORT too."
    exit 0
  fi
  sleep 0.5
done
echo "Installed, but http://localhost:$PORT did not answer within 20s." >&2
echo "Last lines of $LOG:" >&2
tail -n 10 "$LOG" >&2 || true
exit 1
