#!/usr/bin/env bash
# restart.sh — stop any running Logbook server and relaunch it cleanly.
#
# Run this after editing server.py. (index.html and the rest of the front end
# are read fresh on every request, so UI changes only need a browser reload —
# no restart.) Run it from your normal shell so the relaunched server inherits
# your environment and `claude` auth resolves; a sanitized env yields the
# "Not logged in" failures that break day-summary generation.
set -euo pipefail

cd "$(dirname "$0")"
PORT="${PORT:-8787}"
LOG="${LOGBOOK_LOG:-$HOME/logbook-server.log}"
URL="http://localhost:$PORT/api/board"
LABEL=com.jesse.logbook
TARGET="gui/$(id -u)/$LABEL"

# --- if launchd owns the server, restart through it --------------------------
# The server now runs as a launchd LaunchAgent (RunAtLoad + KeepAlive), so it
# survives reboots and crashes. If we killed it by hand here, KeepAlive would
# race to relaunch the old code before our own nohup got a chance to bind the
# port. `kickstart -k` kills-then-starts through launchd instead, so there's
# only ever one relaunch path. Falls through to the manual nohup below only if
# the job was never loaded (e.g. plist missing) - see
# job-search/tracker/scripts/restart-server.sh for the pattern this mirrors.
if launchctl print "$TARGET" >/dev/null 2>&1; then
  echo "Restarting via launchd ($LABEL)"
  launchctl kickstart -k "$TARGET" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then
      pid=$(launchctl print "$TARGET" 2>/dev/null | awk -F'= *' '/^[[:space:]]*pid =/ {print $2; exit}')
      echo "Logbook running at http://localhost:$PORT  (pid ${pid:-unknown})"
      echo "Health: HTTP 200"
      exit 0
    fi
    sleep 0.3
  done
  echo "launchd restart did not become healthy — check $LOG" >&2
  tail -n 5 "$LOG" >&2 || true
  exit 1
fi

# --- fallback: launchd job not loaded, manage the process by hand -----------
# --- stop whatever is listening on the port ---------------------------------
pids=$(lsof -ti "tcp:$PORT" 2>/dev/null || true)
if [ -n "$pids" ]; then
  echo "Stopping old server (pid $(echo "$pids" | tr '\n' ' '))"
  kill $pids 2>/dev/null || true
  for _ in $(seq 1 10); do                    # wait up to ~5s for a clean exit
    lsof -ti "tcp:$PORT" >/dev/null 2>&1 || break
    sleep 0.5
  done
  if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
    echo "  (didn't exit — forcing)"
    kill -9 $(lsof -ti "tcp:$PORT") 2>/dev/null || true
  fi
fi

# --- relaunch, inheriting this shell's environment --------------------------
PORT="$PORT" nohup python3 server.py > "$LOG" 2>&1 &
newpid=$!

# --- wait for it to answer --------------------------------------------------
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    echo "Logbook running at http://localhost:$PORT  (pid $newpid)"
    echo "Health: HTTP 200"
    exit 0
  fi
  sleep 0.3
done

echo "Server did not become healthy — check $LOG" >&2
tail -n 5 "$LOG" >&2 || true
exit 1
