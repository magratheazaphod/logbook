# Logbook — project context

A lightweight personal command deck: a **backlog**, a place for **higher-level ideas**, a **content** list (article,
podcast and video topics), and a
**daily log** that builds itself from Claude Code agent sessions. No dependencies, no build step —
Python 3 standard library only.

## Run it

The server runs as a launchd LaunchAgent (`~/Library/LaunchAgents/<label>.plist`, with
the label set as `launchdLabel` in `config.json`): `RunAtLoad` + `KeepAlive` means it comes up on login/reboot and
relaunches itself if it ever crashes, at `http://localhost:8787`.

From the repo root:

```bash
./restart.sh                       # relaunch cleanly after editing server.py
launchctl print gui/$(id -u)/<label>   # check it's loaded/running
```

`restart.sh` prefers `launchctl kickstart -k` when the agent is loaded (kill-then-start through
launchd, so `KeepAlive` can't race a manual relaunch and start a second copy on the port); it
falls back to a manual `nohup python3 server.py` only if the launchd job isn't loaded at all.

Env overrides: `PORT=9000`, `CLAUDE_PROJECTS_DIR=/path/to/projects`, `COWORK_SESSIONS_DIR`,
`LOGBOOK_DATA_DIR` (default `data/`), `LOGBOOK_CONFIG` (default `config.json`) (set via the plist's
`EnvironmentVariables` for the launchd path, or exported before `./restart.sh`'s fallback path).

`index.html` (and the rest of the front end) is read fresh per request, so UI changes only
need a browser reload. Only **`server.py`** edits require a restart. The plist's `PATH` mirrors
the interactive shell's (including `~/.local/bin` for `claude`) — `server.py` resolves
`shutil.which("claude")` once at import, and launchd's bare default `PATH` doesn't have it,
which would silently break headless day-summary generation ("Not logged in" is the symptom of
this env gap specifically).

The plist must set `ProcessType` to `Interactive`. With no `ProcessType`, launchd applies
"light resource limits" that throttle CPU and I/O: the cold transcript scan used 3.5s of CPU
but took about 124s of wall time, and every request that parsed transcripts crawled.

### Installing the LaunchAgent

`./install.sh` renders `launchd/logbook.plist.template` (label from `LOGBOOK_LABEL`, else
`config.json` `launchdLabel`, else `local.logbook`; the invoking shell's `PATH`; `ProcessType`
`Interactive`; `RunAtLoad` + `KeepAlive`; `WorkingDirectory` = the repo) into
`~/Library/LaunchAgents/<label>.plist`, loads it with `launchctl bootstrap`, and health-checks
`/api/board`. Re-running boots out the old job first, but if the installed plist serves a
different `PORT` both scripts refuse unless `LOGBOOK_REPLACE=1` (a PORT-only override must not
hijack the live agent). `restart.sh` honours `LOGBOOK_LABEL` too. It refuses when another process listens on
`PORT`. `./uninstall.sh` boots it out and deletes the plist; data is untouched. `--dry-run`
prints the plist (works on Linux; CI checks it). To test installer changes, use a scratch copy,
a spare `PORT` and a throwaway `LOGBOOK_LABEL`, never the live label.

## Layout

```
logbook/
  server.py        # stdlib HTTP server: serves UI, persists board, parses sessions
  index.html       # single-page UI (vanilla JS). Must sit beside server.py.
  install.sh       # installs the LaunchAgent (uninstall.sh reverses it)
  launchd/logbook.plist.template  # rendered by install.sh
  README.md        # human-facing setup notes
  CLAUDE.md        # this file
  tests/           # stdlib unittest suite + synthetic .jsonl fixtures
  .github/workflows/test.yml   # CI: macOS + Linux, system python3 and a newer one
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
  (`backlog|doing|done`); `ideas[]` and `content[]` have `id`, `title`. Rows cross freely between all three lists. Content
  items carry an optional `postDate`: they aren't copied into
  `dayPlans` but are derived into the Focus panel's "Content" block under Ideas on that date. Dropping a card on any day's Content block dates it for that day; once its date arrives it leaves the Content list and lives only in that day's Focus (dragging it back clears the date). If the day passes and it isn't done, it returns to the Content list flagged red as overdue. The UI autosaves via `POST /api/board`.
  An agent or cron job can append items to this file directly (preserve the `rev` field).
- **Write protection**: the board carries a `rev` counter. `POST /api/board` must echo the
  current `rev` or it's rejected with 409 + the fresh board (the UI then reloads instead of
  clobbering newer saves from another tab or an agent).
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
  Content cards also get a **"+ draft"** button: it creates a `kind:"draft"` handoff with no
  file behind it (the snapshot is the only copy) and opens it in the overlay as a textarea
  editor with a preview toggle. Edits autosave (debounced, plus on close/Cmd-S) via
  `POST /api/handoff/draft`, which refuses anything that isn't a draft, so dropped docs that
  track real files on disk are never written to.
  The current day's Focus rows take drops too; since a day plan stores whole *copies* of an
  item, an attach/detach on either copy is written to both (`syncHandoffs`). Past days render
  read-only and are excluded.
- **Daily log**: `GET /api/log?date=YYYY-MM-DD` reads `~/.claude/projects/**/*.jsonl`, groups that
  day's sessions, and returns start/end times, project, git branch, prompt counts, and a title
  (Claude Code's own session summary, falling back to the first user prompt). Rendered as a ledger.
  Short LLM session summaries and past days' one-sentence summaries are generated in a
  background pool, never on the request path: the response says `pending: true` while any are
  outstanding and the UI re-polls. Session summaries persist only once the session is quiet.
- **Theme**: light and dark palettes are `:root` tokens in `index.html`; dark follows the OS
  unless the header pill pins light or dark (`data-theme` on `<html>`, saved in localStorage
  and applied by an inline script before first paint). New colours must be tokens with a value
  in both the `prefers-color-scheme` block and the `[data-theme="dark"]` block.
- **App icon**: a log seen end-on, bespectacled, reading a book. `icons/make-icons.py` holds
  the art as one string and emits four variants — a rounded tile (manifest), full-bleed (the
  Dock/iOS tile, whose corners the OS masks itself, so transparency would go black), a maskable
  version inset to Android's safe circle, and a simplified drawing for 16–48px where the tree
  rings would turn to mud. Re-run `python3 icons/make-icons.py` after editing the art; needs
  `rsvg-convert` (the `.ico` is assembled in pure Python). Served from `/icons/`, with
  `/favicon.ico` and a `/manifest.webmanifest` that makes Chrome's "Install as app" produce a
  real Dock icon and a chromeless window.
- **Linked issues**: any card can carry a `linkedIssue` (`{url, repo, number}`, older ones also a
  `title`), shown as a `repo#number` pill. There is currently no way to add one: automatic
  matching (gh search + LLM judgment) never found a real match, and the manual `+ISSUE`
  button, paste and drag paths that replaced it were removed as unwanted. Existing links still
  render and can be removed; removal is synced to the Focus copy like handoffs.
- Server binds `127.0.0.1` **and** `::1` (never a public interface), so every `localhost`
  connection reaches Logbook even if something else grabs the port's wildcard; it exits with a
  clear message if the port is already taken on either loopback, and falls back to IPv4 with a
  warning on hosts without IPv6. No outbound calls. Parser is defensive and skips transcript
  lines it doesn't recognize, so a Claude Code format change degrades gracefully.

## Tests

```bash
python3 -m unittest discover tests
```

Covers transcript parsing (normal CLI, worktree, Cowork sidecar, malformed lines, the
sub-1000-token filter, timezones), the board `rev` 409 guard and daily backups, handoff path
safety (ids can't escape, only drafts are writable), strict log dates (malformed ones get a 400,
future days are never frozen) and `config.json` loading. `tests/support.py`
imports a fresh `server.py` per test with every path (`LOGBOOK_DATA_DIR`, `LOGBOOK_CONFIG`,
`CLAUDE_PROJECTS_DIR`, `COWORK_SESSIONS_DIR`) in a temp dir and an empty `PATH`, and asserts
that before any test runs - so tests can never touch the live board or trigger a billable
`claude -p` call. Keep it that way: add new paths to that assertion list. Must pass on the
macOS system `/usr/bin/python3` (3.9), so no 3.10+ syntax in `server.py` or the tests.

## Contributing

Work on a branch and merge it, never commit straight to `main`. Even for a one-line fix:
branch, commit, open a PR (`gh pr create`), merge it.

Merge with `--no-ff` so each fix stays a reviewable unit rather than dissolving into `main`'s
commit stream.
