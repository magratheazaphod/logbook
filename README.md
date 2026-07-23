<p align="center">
  <img src="icons/icon-192.png" alt="" width="128">
</p>

# Logbook

A lightweight personal command deck: a **backlog**, a place for **higher-level ideas**, and a
**daily log** that builds itself from your Claude Code agent sessions.

No dependencies, no build step. Just Python 3 (already on your Mac) and one HTML file.

![The Logbook UI: a backlog and ideas list on the left, and the day's Claude Code sessions on the
right](docs/screenshots/1-deck.png)

Everything on one screen: the backlog and ideas on the left, today's focus and the session ledger
on the right. The ledger builds itself — each line is a real Claude Code session with its own
one-line summary, and sessions run in Claude Desktop's Cowork mode are marked as such.

![The same UI showing a previous day, with that day's finished work and session
ledger](docs/screenshots/2-archive.png)

Step back to any earlier date and you get that day's summary, its ledger, and whatever you'd
finished that day. Unfinished items don't linger on a past day — they roll back to the top of the
backlog, so the archive only ever shows what actually got done.

## Run it

```bash
cd logbook
python3 server.py
```

Then open **http://localhost:8787**.

To stop, press `Ctrl+C` in the terminal. After editing `server.py`, `./restart.sh` stops the old
process and relaunches cleanly — the front end is read fresh per request, so UI edits only need a
browser reload.

## Install it as an app

In Chrome, use **Install as app** (the install button in the address bar, or ⋮ → Cast, Save and
Share → Install page as app). Logbook then gets a real Dock icon and its own window with no
browser chrome. On iOS, **Add to Home Screen** does the same.

The icon — a log seen end-on, bespectacled, reading a book — is drawn in `icons/make-icons.py`,
which renders every size the tab, the Dock, and a home-screen tile need. The `.svg` and `.png`
files beside it are generated output: edit the script and re-run it, or your changes get
overwritten.

```bash
python3 icons/make-icons.py    # needs rsvg-convert (brew install librsvg)
```

That's the one tool the project needs beyond Python, and only for redrawing the icon — the
rendered files are committed, so running Logbook itself still requires nothing.

## The three panes

**Backlog** — add tasks, click the status dot to cycle `todo → doing → done`, click a title to
edit it, hover to delete. Sorted so in-progress work floats to the top.

**Ideas** — the same idea, one level up: a parking lot for bigger bets that aren't tasks yet.

**Daily Log** — pick a date (‹ › to step, **Today** to jump back) and the app reads your Claude
Code transcripts for that day and lays them out as a session ledger: start–end time, the project
and git branch, prompt counts, and a title (pulled from Claude Code's own session summary, falling
back to your first prompt).

## Where your data lives

- `data/board.json` — your backlog + ideas. Plain JSON, so a Claude Code agent or a cron job can
  append tasks to it directly. The UI autosaves here whenever you make a change.
- `data/day_summaries.json` — the one-line "what I did today" for each day, written for you from
  that day's sessions. Edit one in the UI and it stays edited; hit regenerate to redo it.
- `data/session_summaries.json` — the per-session one-liners in the ledger, cached so a repeat
  page load is instant.

## Where the sessions come from

By default the server reads `~/.claude/projects/**/*.jsonl`. If yours live elsewhere:

```bash
CLAUDE_PROJECTS_DIR=/path/to/projects python3 server.py
```

Nothing leaves your machine — the server binds to `127.0.0.1` only and makes no outbound calls.

## Summaries

Every line in the ledger gets a one-sentence "what actually happened here," and each past day
gets a one-line summary of the whole day. Both are written by Claude Code from your own
transcripts, on demand as you view a day, and cached so you only pay for them once. There's
nothing to schedule and nothing to set up.

Don't like a day's summary? Edit it in place and it stays edited, or hit regenerate for a fresh
one.

## Notes

- Change the port with `PORT=9000 python3 server.py`.
- Claude Code's transcript format can shift between versions; the parser is defensive and skips
  anything it doesn't recognize, so a format change degrades gracefully rather than breaking.
