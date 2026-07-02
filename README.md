# Logbook

A lightweight personal command deck: a **backlog**, a place for **higher-level ideas**, and a
**daily log** that builds itself from your Claude Code agent sessions.

No dependencies, no build step. Just Python 3 (already on your Mac) and one HTML file.

## Run it

```bash
cd task-tracker
python3 server.py
```

Then open **http://localhost:8787**.

To stop, press `Ctrl+C` in the terminal.

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
- `data/logs/YYYY-MM-DD.md` — **optional** narrative for a given day. If a file exists for the date
  you're viewing, its contents render at the top of that day's log (supports `#` headings,
  `-` bullets, and `**bold**`). This is the hook for a written "what I actually did" summary.

## Where the sessions come from

By default the server reads `~/.claude/projects/**/*.jsonl`. If yours live elsewhere:

```bash
CLAUDE_PROJECTS_DIR=/path/to/projects python3 server.py
```

Nothing leaves your machine — the server binds to `127.0.0.1` only and makes no outbound calls.

## Optional: auto-write a narrative summary each day

The ledger is generated live from raw sessions, so it works with zero setup. If you also want a
written summary (a real "here's what I shipped today" paragraph), have Claude Code write one on a
schedule. For example, a cron entry that asks Claude Code to summarize the day into the log folder:

```cron
# 9pm daily — write today's narrative into the logbook
0 21 * * *  cd ~/dev/logbook && claude -p "Summarize what I worked on today from my Claude Code sessions. Write 3-5 bullets to data/logs/$(date +\%F).md" >> ~/logbook-cron.log 2>&1
```

Then that day's log shows your narrative on top and the raw session ledger beneath it.

## Notes

- Change the port with `PORT=9000 python3 server.py`.
- Claude Code's transcript format can shift between versions; the parser is defensive and skips
  anything it doesn't recognize, so a format change degrades gracefully rather than breaking.
