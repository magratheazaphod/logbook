# Logbook — project context

A lightweight personal command deck: a **backlog**, a place for **higher-level ideas**, and a
**daily log** that builds itself from Claude Code agent sessions. No dependencies, no build step —
Python 3 standard library only.

## Run it

```bash
cd ~/projects/logbook
python3 server.py          # serves http://localhost:8787
```

Env overrides: `PORT=9000`, `CLAUDE_PROJECTS_DIR=/path/to/projects`.

## Layout

```
logbook/
  server.py        # stdlib HTTP server: serves UI, persists board, parses sessions
  index.html       # single-page UI (vanilla JS). Must sit beside server.py.
  README.md        # human-facing setup notes
  CLAUDE.md        # this file
  data/
    board.json     # backlog + ideas (plain JSON — safe for an agent/cron to edit)
    logs/          # optional data/logs/YYYY-MM-DD.md narrative per day
```

## How it works

- **Board** (`data/board.json`): `tasks[]` each have `id`, `title`, `status`
  (`backlog|doing|done`); `ideas[]` have `id`, `title`. The UI autosaves via `POST /api/board`.
  An agent or cron job can append items to this file directly (preserve the `rev` field).
- **Write protection**: the board carries a `rev` counter. `POST /api/board` must echo the
  current `rev` or it's rejected with 409 + the fresh board (the UI then reloads instead of
  clobbering newer saves — this once lost days of task history to a long-lived stale tab).
  The UI also resyncs whenever its tab regains focus. Server bumps `rev` on every write.
- **Backups**: before the first board write of each day, the server snapshots the previous
  state to `data/backups/board-YYYY-MM-DD.json` (kept 60 days, gitignored).
- **Daily log**: `GET /api/log?date=YYYY-MM-DD` reads `~/.claude/projects/**/*.jsonl`, groups that
  day's sessions, and returns start/end times, project, git branch, prompt counts, and a title
  (Claude Code's own session summary, falling back to the first user prompt). Rendered as a ledger.
- **Narrative override**: if `data/logs/<date>.md` exists, it renders above that day's ledger
  (supports `#` headings, `-` bullets, `**bold**`).
- Server binds to `127.0.0.1` only; no outbound calls. Parser is defensive and skips transcript
  lines it doesn't recognize, so a Claude Code format change degrades gracefully.

## Open next step

Auto-write the daily narrative on a schedule. Cleanest approach pipes the server's own JSON into
Claude Code headless mode and redirects stdout to the log file (needs the server running):

```bash
0 21 * * *  cd ~/projects/logbook && curl -s "http://localhost:8787/api/log?date=$(date +\%F)" \
  | $(which claude) -p "Summarize these Claude Code sessions as 3-5 markdown bullets of what I worked on. Output only the bullets." \
  > "data/logs/$(date +\%F).md" 2>> ~/logbook-cron.log
```

Cron gotchas: use the absolute path to `claude` (`which claude`); escape `%` as `\%`; cron may not
inherit your `claude login` auth (set `ANTHROPIC_API_KEY` if it fails); grant `cron` Full Disk
Access on macOS. Test the command by hand before scheduling. A `daily-summary.sh` wrapper would make
this a single clean crontab line — not built yet.
