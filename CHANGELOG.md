# Changelog

All notable changes to Logbook are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Within 1.x, `data/board.json` stays
forward-compatible: no migration is required and unknown fields are preserved on save.

## [Unreleased]

## [1.1.0] - 2026-09-28

### Changed

- A content card whose post date is today lives only in today's Focus. Once its day has passed,
  a done card stays in that day's Focus as a record, and an unfinished one goes back to the
  Content list with the red overdue flag instead of piling up in today's Focus.
- Post dates can no longer be set in the past, and a past day's Content block is read-only.

### Fixed

- The post-date field let only two digits of the year be typed before committing.
- Typing a year into the daily log's date field jumped the log to year 0002 and blanked the
  field. The server now answers malformed dates with a 400 instead of today's log.

## [1.0.1] - 2026-09-27

### Removed

- Adding GitHub issue links to cards (the `+ISSUE` button, pasting an issue URL into a title, and
  dragging an issue link onto a card). Links already on a board still show, and can still be
  removed.

## [1.0.0] - 2026-09-27

First public release. Logbook had been in daily use since July 2026; this entry summarizes
everything up to the release.

### Added

- Backlog, Ideas and Content lists with free dragging between them, search, a TOP button, new
  items added at the top, and a short undo window after a delete.
- Today's focus: drag cards into a day plan; unfinished items roll back to their list once the day
  ends, finished ones stay as that day's record. Content items carry an optional post date and
  appear under that day's Ideas.
- Daily log built from Claude Code transcripts (`~/.claude/projects`): start-end time, project
  (labelled by repo root), git branch, prompt counts and title, with Claude Desktop Cowork
  sessions included and small drive-by sessions hidden.
- Per-session and per-day summaries written by the `claude` CLI in a background pool, cached,
  editable in place and regenerable; the log never waits on the LLM.
- Handoff docs: drop a Markdown/text file or an image onto a card to attach it, rendered in-app
  from the live file with a snapshot fallback. Content cards get in-app drafts with preview and
  autosave.
- Manual GitHub issue and PR links on cards (paste, drag or `+ISSUE`).
- Dark mode following the OS, with a light/dark pin in the header.
- App icon, favicon and web manifest for Chrome's "Install as app".
- Board write protection: a `rev` counter rejects stale saves with 409, plus daily board backups
  kept for 60 days.
- `config.json` for personal settings (`coworkSkipSessions`, `launchdLabel`) and a startup banner
  listing the optional features in use.
- `install.sh` / `uninstall.sh` with a committed LaunchAgent template, and `restart.sh`.
- Stdlib `unittest` suite with synthetic transcript fixtures, run in CI on macOS and Linux.
- MIT license.

### Changed

- The server binds to both loopback addresses (`127.0.0.1` and `::1`) only.
- Automatic GitHub issue matching was replaced by manual links, so Logbook makes no GitHub calls.
- Unknown fields in `board.json` (top level, cards and day plans) are preserved on save.

### Fixed

- The daily log used the UTC date instead of the local date.
- Failed LLM summaries were frozen instead of retried.
- The day log could render, and bill for summaries, twice on first load.

[Unreleased]: https://github.com/magratheazaphod/logbook/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/magratheazaphod/logbook/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/magratheazaphod/logbook/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/magratheazaphod/logbook/releases/tag/v1.0.0
