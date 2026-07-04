---
name: logbook
description: Long-term context for the user's homebrew "Logbook" project (~/projects/logbook) — a personal command deck combining a backlog, an ideas list, and a daily log auto-built from Claude Code session transcripts. Load this before making changes to that project: it captures why the tool exists, the design principles behind it, the history/rationale of features already built, and standing behavioral preferences the user has stated over time (what to avoid, what's been confirmed as correct). This is a knowledge/context doc, not a task runner — CLAUDE.md in the repo has the mechanical "how it works."
user-invocable: true
---

# Logbook — project intent and history

## What it is and why

A personal, stdlib-only command deck the user built for themselves: a **backlog**, a place
for **higher-level ideas**, and a **daily log** that reconstructs itself from Claude Code
agent session transcripts (`~/.claude/projects/**/*.jsonl`). The point is a single low-friction
page that shows "what am I supposed to be doing" and "what did I actually do today" without
hand-maintaining either. It is explicitly a small, personal-scale tool — not a product, not
multi-user, not meant to scale past one person's task list. See the repo's own `CLAUDE.md` for
the mechanical layout, run instructions, and file responsibilities.

## Design principles (stated or demonstrated repeatedly)

- **Stdlib-only, no build step.** Python 3 standard library + vanilla JS, one `index.html`.
  Don't introduce a dependency, framework, or build tool to solve a problem — solve it with
  what's already there.
- **Local-only, private by default.** Server binds `127.0.0.1` only. `data/board.json` and
  other generated data files are gitignored — they're the user's real personal task data, not
  sample data, and must never end up in the public GitHub repo
  (`https://github.com/magratheazaphod/logbook`, created **public** at the user's choice).
- **Degrade gracefully, don't crash.** The transcript parser skips lines/records it doesn't
  recognize rather than erroring, so a future Claude Code log-format change doesn't break the
  whole daily log.
- **Cheap by default for any LLM calls.** Headless `claude -p` calls (session summaries, day
  summaries, GitHub-issue keyword extraction) use `claude-haiku-4-5` — the cheapest available
  model — confirmed deliberately, not by accident.
- **Cache aggressively, but only what's actually stable.** Past days' logs, session summaries,
  and day-summaries are memoized to disk once their period is over; **today is never cached**
  (it's still being written). A manual edit to a day-summary is flagged and permanently wins
  over regeneration.
- **Don't over-engineer for a one-person tool.** After a multi-round debugging session to get
  GitHub issue-search matching working (see below), the user's own assessment was: *"This might
  have been overkill for this small project. It's ok if it doesn't work."* Read this as a
  standing calibration signal — favor the simple version first, and don't keep polishing a
  heuristic/feature past the point the user has signaled satisfaction, even if it's not 100%
  precise. This applies generally, not just to issue-matching.

## Feature history and rationale (why things are the way they are)

- **Rose/brick color theme** (`--paper:#F1E6E4`, `--accent:#B23A2E`) — explicit aesthetic
  preference, not a default.
- **Daily log grouped by agent/project session, collapsible, with token counts, filtering out
  sub-1000-token "drive-by" sessions** — keeps the log readable; threshold was tuned down from
  5000 to 1000 tokens per explicit feedback (5000 hid too much real work).
- **Per-file session-parse cache** (not one global cache) — a global mtime-hash cache forced a
  full re-parse of all transcripts on every request because any one active session changing
  invalidated everything. Fixed by keying the cache per file.
- **Session summaries memoized by session ID only, never invalidated** — a session spanning
  multiple days must show the *same name* every day it appears; mtime-based invalidation both
  wasted LLM calls and caused inconsistent naming.
- **One-sentence editable day-summary at the top of each day** — generated from that day's
  session summaries, skipped entirely for the in-progress/today day, permanently remembers
  manual edits. Prompt was explicitly tuned to **prioritize naming a standout
  win/hard-fought resolution over a generic thematic average** — the user caught a first-draft
  summary that averaged everything into vague theme-speak and missed the one thing that
  actually mattered that day (getting a scheduled report emailed out after a real struggle).
  A later fix: **a failed headless `claude -p` call must never be cached as if it were a
  real summary.** Originally a transient LLM failure fell back to `_naive_summary()` (session
  summaries joined with `; ` and hard-truncated with a `…`) and that garbage got frozen —
  worse, the UI's day-summary field POSTed on *any* blur, flipping the fallback to
  `edited:true` so it could never regenerate. Now `_generate_summary`/`_generate_day_summary`
  return `None` on failure, callers show the naive text transiently but **don't persist it**
  (so it self-heals on a later load), and the UI only saves a genuine edit.
- **Backlog and Ideas are drag-and-drop rankable**, and **Today's Focus** lets the user drag
  tasks/ideas onto the current day to work from; anything not marked done rolls back to the top
  of Backlog/Ideas at end of day. Adding *new* items to a day's focus is only possible for
  the **current** day — past and future days render read-only.
- **GitHub issue auto-matching**: adding a backlog task or idea searches a fixed set of repos
  (`jvc56/MAGPIE`, `magratheazaphod/scrabble-ai`, all of `domino14`, all of `woogles-io`) for an
  existing open issue that matches, and attaches a removable pill (✕ to unlink) if found. Repo
  list grew twice: first to include the user's own `scrabble-ai` repo pre-emptively ("just in
  case we have issues there in future"), then to add the `woogles-io` org after discovering the
  real Woogles codebase lives there, not under `domino14`. GitHub's issue search turned out to
  behave like near-exact/AND-of-tokens matching with **no stemming** (e.g. "annotator" won't
  match an issue titled with "annotation") — required LLM-based keyword extraction with a
  3-tier progressively-shorter query fallback (6 words → 2 → 1) to get real hits. A one-time
  backfill was run against all 31 pre-existing backlog/idea items and found 3 genuine matches;
  the other 28 had no real match (not a search failure).

## Standing behavioral preferences

- **Never trigger a client-side save from stale/test state.** The browser client holds the
  whole board in memory and autosaves via debounce on any mutation. The user edits their real
  board concurrently in their own tab; testing in an automated browser tab must never write
  back stale data over live edits — reload to resync before doing anything that could `save()`.
- **Ask before expanding scope, especially for repo lists / external searches** — e.g. surfaced
  the `woogles-io` org discovery via a question rather than silently widening the search.
- **When the user signals "good enough," stop tuning.** Don't keep iterating on a
  heuristic/feature once they've said it's fine as-is, even if you can see room to improve it.
- **A light day earns a short summary — never pad.** Day-summaries (and session
  summaries) should match the actual weight of the day. If little of substance happened,
  a few words is the correct output; don't stretch it with filler to make the day look
  busier. This is encoded in the day-summary prompt, but holds as a general preference.
- **Confirm before git pushes / public repo creation** — this was asked explicitly
  (`gh repo create --public`) rather than assumed.
- Mobile viewability was discussed as a **"tell me what it'd take, don't implement"**
  informational question — a pattern worth recognizing: not every "can we..." question is a
  request to build it.

## Known open items (context, not a todo list)

- The public GitHub repo may lag behind local `server.py`/`index.html` changes at any given
  time — check with `git status`/`git log` before assuming parity; don't push without being
  asked.
- The "Auto-write the daily narrative on a schedule" cron idea in `CLAUDE.md` is designed but
  not wired up.
