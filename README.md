<p align="center">
  <img src="icons/icon-192.png" alt="" width="128">
</p>

# Logbook

**One page for "what should I be doing" and "what did I actually do".** A local command deck for
Claude Code users: a backlog, an ideas list and a content list on the left, and on the right a
daily log that writes itself from your Claude Code sessions.

No dependencies, no build step, no account. Python 3 (already on your Mac) and one HTML file,
running on your own machine.

![The Logbook UI: a backlog and ideas list on the left, and the day's Claude Code sessions on the
right](docs/screenshots/1-deck.png)

Everything on one screen: the lists on the left, today's focus and the session ledger on the
right. Each ledger line is a real Claude Code session with its own one-line summary; sessions run
in Claude Desktop's Cowork mode are marked as such.

![The same UI showing a previous day, with that day's finished work and session
ledger](docs/screenshots/2-archive.png)

Step back to any earlier date and you get that day's summary, its ledger, and whatever you
finished that day. Unfinished items don't linger on a past day - they roll back to the top of the
backlog, so the archive only ever shows what actually got done.

## Features

- **Backlog, Ideas and Content lists.** Tasks cycle `todo -> doing -> done` from their status dot;
  Ideas is a parking lot for bigger bets that aren't tasks yet; Content holds article, podcast and
  video topics with an optional post date. Drag cards freely between the three, search them, jump
  one to the top, and undo a delete within a few seconds.
- **Today's focus.** Drag cards into the day's focus list. Content scheduled for a date shows up
  under that day's Ideas (today's also lists overdue pieces). Once the day ends, unfinished focus items
  return to the top of their list; finished ones stay with the day as a record.
- **Daily log.** Pick a date and Logbook reads that day's Claude Code transcripts into a ledger:
  start-end time, project, git branch, prompt count and title. Claude Desktop Cowork sessions are
  included too.
- **Summaries.** Every session gets a one-sentence "what actually happened here", and each past
  day a one-line summary of the whole day, written by your own `claude` CLI in the background and
  cached so you pay for each once. Edit one in place and it stays edited, or regenerate it.
- **Handoff docs and drafts.** Drop a Markdown or text file (or an image) from Finder or your
  editor onto a card and it attaches as a pill; click it to read the doc rendered in-app. It
  tracks the live file and falls back to a snapshot if the file moves. Content cards also get a
  **+ draft** button: an in-app Markdown editor with preview and autosave.
- **GitHub issue links.** Paste an issue or PR URL into a card title, drag the link onto the card,
  or use the hover `+ISSUE` button. Links are manual - Logbook never calls GitHub.
- **Dark mode.** Follows your OS, or pin light or dark from the header.
- **Install as app.** A real icon and a chromeless window via Chrome's "Install as app" or iOS's
  "Add to Home Screen".
- **Safe with agents.** `data/board.json` is plain JSON that an agent or cron job can append to.
  A revision counter stops a stale browser tab from clobbering newer saves, and the server keeps
  a daily backup of the board for 60 days.

## Install (about 2 minutes)

Requirements: macOS or Linux, Python 3, and Claude Code (whose transcripts the log reads).
Optional: a logged-in `claude` CLI on `PATH` for summaries, and Claude Desktop for Cowork
sessions.

```bash
git clone https://github.com/magratheazaphod/logbook.git
cd logbook
./install.sh
```

Then open **http://localhost:8787**.

`install.sh` (macOS) renders `launchd/logbook.plist.template` into a LaunchAgent, loads it and
health-checks the server, so Logbook starts at login and restarts itself if it crashes. Run it
from your normal terminal: the agent copies that shell's `PATH` so `claude` resolves for
summaries. Re-running replaces the install cleanly, and `./uninstall.sh` removes it (your data
stays).

Both scripts take `PORT=8790` and `LOGBOOK_LABEL=my.logbook` overrides (pass the same ones to
`./restart.sh`). If an agent under that label already serves a different port they refuse rather
than move it, unless you add `LOGBOOK_REPLACE=1`. `./install.sh --dry-run` prints the plist
without changing anything. If another process already holds the port, the installer stops and
names it. The log goes to `~/logbook-server.log` (`LOGBOOK_LOG` to change).

Without the installer, or on Linux, run it in the foreground (or under your own supervisor):

```bash
python3 server.py
```

### Install it as an app

In Chrome, use **Install as app** (the install button in the address bar, or the menu's Cast,
Save and Share -> Install page as app). Logbook gets a real Dock icon and its own window. On iOS,
**Add to Home Screen** does the same.

## Configuration

Optional personal settings go in `config.json` beside `server.py` (gitignored). Copy
`config.example.json` to start one; every key is optional.

| Key | Default | What it does |
| --- | --- | --- |
| `coworkSkipSessions` | `[]` | Cowork session IDs to leave out of the log. |
| `launchdLabel` | `local.logbook` | The LaunchAgent label `install.sh`, `uninstall.sh` and `restart.sh` use. |

Environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `PORT` | `8787` | Port to listen on. |
| `CLAUDE_PROJECTS_DIR` | `~/.claude/projects` | Where Claude Code transcripts live. |
| `COWORK_SESSIONS_DIR` | Claude Desktop's session folder | Where Cowork sessions live. |
| `LOGBOOK_DATA_DIR` | `data/` | Where the board, handoffs, caches and backups live. |
| `LOGBOOK_CONFIG` | `config.json` | Read settings from another file. |
| `LOGBOOK_MIN_TOKENS` | `1000` | Sessions smaller than this are treated as drive-bys and hidden. |

On startup the server prints which optional features are on.

## Privacy

Logbook is local-first. The server binds to the loopback addresses only (`127.0.0.1` and `::1`),
has no accounts or telemetry, and makes no network calls of its own. The only traffic that
leaves your machine is the headless `claude` calls that write summaries, made through your own
Claude Code login - and only if `claude` is on the server's `PATH`. Without it, everything else
works and summaries are simply skipped.

Your data stays in `data/` (gitignored):

- `board.json` - your lists and day plans.
- `handoffs/` - snapshots of attached docs and images, and drafts.
- `day_summaries.json`, `session_summaries.json` - cached summaries.
- `backups/` - one board snapshot per day, kept 60 days.

A note on the port: on macOS, a server started later on all addresses (a plain
`python3 -m http.server PORT`) can still start beside Logbook, but `localhost`, `127.0.0.1` and
`::1` keep reaching Logbook; that server only gets traffic from other interfaces.

## Upgrading

```bash
cd logbook
git pull
./restart.sh
```

The front end is read fresh per request, so a browser reload picks up UI changes; only
`server.py` changes need the restart.

**Compatibility promise:** `board.json` is forward-compatible within 1.x. A 1.x release never
requires migrating your board, and fields it doesn't recognize - on the board, a card or a day
plan - are preserved on save rather than dropped, so a newer version, an agent or your own script
can add fields safely. See [CHANGELOG.md](CHANGELOG.md) for what changed in each release.

## Running the tests

Standard library only, like the server:

```bash
python3 -m unittest discover tests
```

The suite runs against synthetic transcripts in `tests/fixtures/` and never touches your real
board, config or transcripts: each test imports its own copy of `server.py` with
`LOGBOOK_DATA_DIR`, `LOGBOOK_CONFIG`, `CLAUDE_PROJECTS_DIR` and `COWORK_SESSIONS_DIR` pointed at a
temp dir, and with no `claude` on `PATH`, so it makes no LLM or network calls. CI runs it on macOS
and Linux (`.github/workflows/test.yml`).

## Who this is for

Claude Code users on macOS who want one page for planning and for looking back. Linux works too,
minus Cowork sessions and launchd.

## Not goals

Logbook is a one-person, one-machine tool. Sync across devices, multiple users, hosting, and
Windows are out of scope.

## Notes for contributors

- Claude Code's transcript format can shift between versions; the parser is defensive and skips
  anything it doesn't recognize, so a format change degrades gracefully rather than breaking.
- The app icon is drawn in `icons/make-icons.py`; the `.svg`, `.png` and `.ico` files beside it
  are generated. Edit the script and run `python3 icons/make-icons.py` (needs `rsvg-convert`,
  `brew install librsvg`). The rendered files are committed, so running Logbook needs nothing
  extra.

## License

MIT - see [LICENSE](LICENSE).
