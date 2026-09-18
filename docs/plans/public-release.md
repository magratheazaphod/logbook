# Making Logbook installable and forkable

Status: agreed 2026-09-17. Target audience is **Claude Code users on macOS**
(Linux works minus Cowork and launchd). Sync, multiple users and hosting are
explicitly out of scope. An HTML rendering of this plan lives beside it in
`public-release.html`.

## Where we are

Already in place: the repo is public, runtime data (board, handoffs, caches,
backups) is gitignored, README screenshots use synthetic data, zero
dependencies, and the app icon is generated from source. The architecture does
not need to change; the remaining work is de-personalizing, packaging, trust
signals and docs.

## What blocks a stranger today

- No LICENSE file, so nobody may legally use or fork it.
- Personal settings are hardcoded: the GitHub issue-match repos
  (`server.py`, `ISSUE_MATCH_OWNERS` / `ISSUE_MATCH_REPOS`), a skip-list of
  early Cowork session IDs, and the `com.jesse.logbook` launchd label in
  `restart.sh` and `CLAUDE.md`.
- `.claude/skills/logbook/SKILL.md` is the owner's personal context, not
  project docs.
- The launchd plist exists only in `~/Library/LaunchAgents`, not the repo. Its
  `PATH` must include the directory holding `claude`, or day summaries fail
  with "Not logged in" - a stranger cannot reproduce this.
- Prerequisites are undocumented as required vs optional: Claude Code
  transcripts (required), a logged-in `claude` CLI (summaries), `gh`
  (issue match), macOS paths (Cowork).
- No tests, no CI. The transcript parser depends on an undocumented format and
  is the most likely thing to break for someone else.
- No tags, changelog, or stated compatibility for `board.json` across upgrades.

## Plan - one PR per step

1. **License and scope.** MIT LICENSE. README gains "Who this is for" and
   "Not goals" sections.
2. **Config instead of hardcoding.** A gitignored `config.json` (with a
   committed `config.example.json`) or env vars for the issue-match repos,
   the Cowork skip-list and the launchd label. Defaults: issue match off,
   skip-list empty. A startup banner lists which optional features are
   active (summaries, issue match, Cowork).
3. **Installer.** `./install.sh` renders a committed plist template with the
   current shell's `PATH`, loads it and health-checks
   `http://localhost:8787`; `./uninstall.sh` reverses it. `restart.sh` reads
   the label from config.
4. **Tests and CI.** Stdlib `unittest` with synthetic `.jsonl` fixtures
   (worktree session, Cowork sidecar, malformed lines), the `rev` 409 guard,
   handoff path safety and daily backups. GitHub Actions on macOS and Linux.
   Do this before 2 and 3 if feature work continues in parallel - it also
   protects the live board.
5. **Split personal from project.** Move the logbook skill to
   `~/.claude/skills`; genericize `CLAUDE.md`, keeping the branch-and-PR rule
   for contributors.
6. **README as a product page.** What it is, screenshots, features, a
   2-minute install, configuration, privacy ("binds to localhost; no network
   calls except `claude`/`gh` calls you enable"), upgrading. Add
   `CHANGELOG.md`, tag `v1.0.0`, set the GitHub description and topics.
7. **Portfolio hook.** A short case study on jesse-day.com linking the repo.
   No hosted demo: the app reads local transcripts, so a demo would be a
   facade. A short GIF or the existing screenshots carry it better.

## Before step 1

Scan the full commit history once for anything personal that predates the
`.gitignore` - the repo has been public throughout. A quick grep found
nothing.

## Deferred, only on demand

- pip or Homebrew packaging.
- A Linux systemd unit.
- Windows support.
