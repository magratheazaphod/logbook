# Logbook — project context

A lightweight personal command deck: a **backlog**, a place for **higher-level ideas**, and a
**daily log** that builds itself from Claude Code agent sessions. No dependencies, no build step —
Python 3 standard library only.

## Run it

The server runs as a launchd LaunchAgent (`~/Library/LaunchAgents/com.jesse.logbook.plist`,
label `com.jesse.logbook`): `RunAtLoad` + `KeepAlive` means it comes up on login/reboot and
relaunches itself if it ever crashes, at `http://localhost:8787`.

```bash
cd ~/projects/logbook
./restart.sh                       # relaunch cleanly after editing server.py
launchctl print gui/$(id -u)/com.jesse.logbook   # check it's loaded/running
```

`restart.sh` prefers `launchctl kickstart -k` when the agent is loaded (kill-then-start through
launchd, so `KeepAlive` can't race a manual relaunch and start a second copy on the port); it
falls back to a manual `nohup python3 server.py` only if the launchd job isn't loaded at all.

Env overrides: `PORT=9000`, `CLAUDE_PROJECTS_DIR=/path/to/projects` (set via the plist's
`EnvironmentVariables` for the launchd path, or exported before `./restart.sh`'s fallback path).

`index.html` (and the rest of the front end) is read fresh per request, so UI changes only
need a browser reload. Only **`server.py`** edits require a restart. The plist's `PATH` mirrors
the interactive shell's (including `~/.local/bin` for `claude`) — `server.py` resolves
`shutil.which("claude")` once at import, and launchd's bare default `PATH` doesn't have it,
which would silently break headless day-summary generation ("Not logged in" is the symptom of
this env gap specifically).

## Layout

```
logbook/
  server.py        # stdlib HTTP server: serves UI, persists board, parses sessions
  index.html       # single-page UI (vanilla JS). Must sit beside server.py.
  README.md        # human-facing setup notes
  CLAUDE.md        # this file
  icons/
    make-icons.py  # holds the app-icon art; regenerates every SVG/PNG/ICO below
    *.svg *.png    # generated — edit make-icons.py, never these
    favicon.ico
  data/
    board.json     # backlog + ideas (plain JSON — safe for an agent/cron to edit)
    handoffs/      # snapshots of docs attached to a card, + index.json (path map)
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
- **Handoff docs**: drag a `.md` (or any text file) from Finder/an editor onto a Backlog or
  Ideas card and it attaches as a removable pill; clicking it opens the doc in an overlay,
  rendered by a small hand-rolled Markdown subset in Logbook's own styling. `POST /api/handoff`
  snapshots the text to `data/handoffs/<id>.md` and records the file's real path (taken from the
  drag's `text/uri-list`) in `data/handoffs/index.json`; `GET /api/handoff?id=` re-reads the live
  file so later edits show through, falling back to the snapshot once the original moves or is
  deleted. The board stores only the id, so the endpoint can't be pointed at an arbitrary file.
  Images (PNG/JPEG/GIF/WebP/SVG) attach the same way but travel as base64 on the same POST
  (`kind:"image"`), snapshot as bytes to `data/handoffs/<id>.<ext>`, and are served by
  `GET /api/handoff/image?id=` - `GET /api/handoff` returns only their caption metadata.
  Clicking such a pill shows the picture in the overlay instead of rendered Markdown.
  The current day's Focus rows take drops too; since a day plan stores whole *copies* of an
  item, an attach/detach on either copy is written to both (`syncHandoffs`). Past days render
  read-only and are excluded.
- **Daily log**: `GET /api/log?date=YYYY-MM-DD` reads `~/.claude/projects/**/*.jsonl`, groups that
  day's sessions, and returns start/end times, project, git branch, prompt counts, and a title
  (Claude Code's own session summary, falling back to the first user prompt). Rendered as a ledger.
- **App icon**: a log seen end-on, bespectacled, reading a book. `icons/make-icons.py` holds
  the art as one string and emits four variants — a rounded tile (manifest), full-bleed (the
  Dock/iOS tile, whose corners the OS masks itself, so transparency would go black), a maskable
  version inset to Android's safe circle, and a simplified drawing for 16–48px where the tree
  rings would turn to mud. Re-run `python3 icons/make-icons.py` after editing the art; needs
  `rsvg-convert` (the `.ico` is assembled in pure Python). Served from `/icons/`, with
  `/favicon.ico` and a `/manifest.webmanifest` that makes Chrome's "Install as app" produce a
  real Dock icon and a chromeless window.
- Server binds to `127.0.0.1` only; no outbound calls. Parser is defensive and skips transcript
  lines it doesn't recognize, so a Claude Code format change degrades gracefully.
