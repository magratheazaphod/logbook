"""Transcript parsing and the daily log, against the synthetic fixtures."""

import json
import shutil
from datetime import date

from support import FIXTURE_DAY, SandboxedServerTest, set_tz


def by_id(sessions):
    return {s["id"]: s for s in sessions}


class TranscriptParsingTest(SandboxedServerTest):
    copy_fixtures = True
    config = {"coworkSkipSessions": ["cw-skip"]}

    def test_normal_cli_session(self):
        s = by_id(self.srv.collect_sessions())["sess-normal"]
        self.assertEqual(s["source"], "cli")
        self.assertEqual(s["project"], "/nonexistent-logbook-test/alpha")
        self.assertEqual(s["project_short"], "alpha")
        self.assertEqual(s["branches"], ["feat/export", "main"])
        # Claude Code's own summary line wins over the first prompt.
        self.assertEqual(s["title"], "CSV export for the report page")
        self.assertEqual(s["synopsis"], "Add a CSV export to the report page")
        # The slash-command echo is noise, not a prompt.
        self.assertEqual(s["user_prompts"],
                         ["Add a CSV export to the report page", "Also add a test for it"])
        self.assertEqual(s["last_assistant"], "Test added and passing.")
        self.assertEqual(len(s["events"]), 5)
        self.assertEqual(sum(t for _, _, t in s["events"]), 2300)

    def test_title_falls_back_to_first_prompt(self):
        s = by_id(self.srv.collect_sessions())["sess-worktree"]
        self.assertEqual(s["title"], "Refactor the importer in a worktree")

    def test_worktree_session_folds_onto_parent_repo(self):
        s = by_id(self.srv.collect_sessions())["sess-worktree"]
        self.assertEqual(s["project"], "/nonexistent-logbook-test/beta")
        self.assertEqual(s["project_short"], "beta")

    def test_subdirectory_folds_onto_git_root(self):
        repo = self.tmp / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "sub" / "deeper").mkdir(parents=True)
        self.assertEqual(self.srv.canonical_project(str(repo / "sub" / "deeper")), str(repo))
        self.assertEqual(self.srv.canonical_project(str(repo)), str(repo))
        # A worktree marker wins even when no repo exists on disk.
        self.assertEqual(self.srv.canonical_project("/x/y/.claude/worktrees/w/sub"), "/x/y")

    def test_cowork_session_uses_sidecar(self):
        s = by_id(self.srv.collect_sessions())["cw-main"]
        self.assertEqual(s["source"], "cowork")
        self.assertEqual(s["project"], "Gamma")
        self.assertEqual(s["title"], "Draft the newsletter")

    def test_cowork_without_folders_is_labelled_cowork(self):
        sidecar = next(self.cowork_dir.rglob("local_abc.json"))
        sidecar.write_text(json.dumps({"title": "Chat"}), encoding="utf-8")
        s = by_id(self.srv.collect_sessions())["cw-main"]
        self.assertEqual(s["project"], "Cowork")

    def test_cowork_skip_list_and_subagents_excluded(self):
        ids = set(by_id(self.srv.collect_sessions()))
        self.assertNotIn("cw-skip", ids)
        self.assertNotIn("agent-1", ids)   # CLI subagent transcript
        self.assertNotIn("agent-2", ids)   # Cowork subagent transcript

    def test_own_summary_calls_are_skipped(self):
        self.assertNotIn("sess-internal", by_id(self.srv.collect_sessions()))

    def test_malformed_and_unknown_lines_are_skipped(self):
        s = by_id(self.srv.collect_sessions())["sess-malformed"]
        self.assertEqual(s["synopsis"], "Tidy up the parser")
        self.assertEqual(s["last_assistant"], "Parser tidied.")
        # user@12:00:00, three assistants; the bad-timestamp and truncated
        # lines add no events.
        self.assertEqual(len(s["events"]), 4)
        # Non-numeric usage values count as zero instead of sinking the file.
        self.assertEqual(sum(t for _, _, t in s["events"]), 2034)

    def test_unreadable_or_empty_files_yield_nothing(self):
        d = self.projects_dir / "-junk"
        d.mkdir()
        (d / "garbage.jsonl").write_text("}{\n[]\n\n", encoding="utf-8")
        (d / "empty.jsonl").write_text("", encoding="utf-8")
        (d / "binary.jsonl").write_bytes(b"\xff\xfe\x00\x81garbage\n")
        (d / "no-timestamps.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n",
            encoding="utf-8")
        ids = {s["file"] for s in self.srv.collect_sessions()}
        self.assertFalse(any("-junk" in f for f in ids))

    def test_missing_transcript_dirs_are_fine(self):
        shutil.rmtree(self.projects_dir)
        shutil.rmtree(self.cowork_dir)
        self.assertEqual(self.srv.collect_sessions(), [])
        log = self.srv.log_for_date(FIXTURE_DAY)
        self.assertEqual(log["entries"], [])
        self.assertFalse(log["projects_dir_exists"])

    def test_parse_cache_follows_file_changes(self):
        self.assertIn("sess-tiny", by_id(self.srv.collect_sessions()))
        (self.projects_dir / "-nonexistent-logbook-test-alpha" / "sess-tiny.jsonl").unlink()
        self.assertNotIn("sess-tiny", by_id(self.srv.collect_sessions()))


class DailyLogTest(SandboxedServerTest):
    copy_fixtures = True
    config = {"coworkSkipSessions": ["cw-skip"]}

    def test_day_entries_and_token_filter(self):
        entries, totals, pending, settled = self.srv._compute_day(date.fromisoformat(FIXTURE_DAY))
        ids = [e["id"] for e in entries]
        # Sorted by start time; sess-tiny (499 tokens) is filtered out.
        self.assertEqual(ids, ["sess-normal", "sess-malformed", "sess-worktree", "cw-main"])
        normal = entries[0]
        self.assertEqual((normal["start"], normal["end"]), ("10:00", "10:10"))
        self.assertEqual((normal["user_turns"], normal["assistant_turns"]), (3, 2))
        self.assertEqual(normal["tokens"], 2300)
        self.assertEqual(totals["sessions"], 4)
        self.assertEqual(totals["projects"], ["Gamma", "alpha", "beta"])
        self.assertEqual(totals["tokens"], 2300 + 2034 + 1200 + 2000)
        # No `claude` on PATH: names stay pending and nothing is frozen.
        self.assertTrue(pending)
        self.assertFalse(settled)

    def test_min_tokens_threshold_is_inclusive_and_configurable(self):
        self.srv.MIN_SESSION_TOKENS = 499
        entries, *_ = self.srv._compute_day(date.fromisoformat(FIXTURE_DAY))
        self.assertIn("sess-tiny", [e["id"] for e in entries])
        self.srv.MIN_SESSION_TOKENS = 500
        entries, *_ = self.srv._compute_day(date.fromisoformat(FIXTURE_DAY))
        self.assertNotIn("sess-tiny", [e["id"] for e in entries])

    def test_other_days_are_empty(self):
        entries, totals, *_ = self.srv._compute_day(date(2026, 1, 14))
        self.assertEqual(entries, [])
        self.assertEqual(totals["tokens"], 0)
        self.assertEqual(self.srv.available_dates(), [FIXTURE_DAY])

    def test_cached_summaries_are_used_and_past_day_is_frozen(self):
        # Pre-seeding the summary cache stands in for the LLM.
        names = {"sess-normal": "Added CSV export", "sess-malformed": "Tidied parser",
                 "sess-worktree": "Refactored importer", "cw-main": "Drafted newsletter"}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.srv.SUMMARY_CACHE_FILE.write_text(
            json.dumps({k: {"summary": v} for k, v in names.items()}), encoding="utf-8")
        log = self.srv.log_for_date(FIXTURE_DAY)
        self.assertEqual({e["id"]: e["summary"] for e in log["entries"]}, names)
        self.assertFalse(log["sessions_pending"])
        frozen = json.loads(self.srv.DAY_LOG_CACHE_FILE.read_text(encoding="utf-8"))
        self.assertIn(FIXTURE_DAY, frozen)
        # Once frozen, later transcript edits don't change a past day.
        for p in self.projects_dir.rglob("*.jsonl"):
            p.unlink()
        again = self.srv.log_for_date(FIXTURE_DAY)
        self.assertEqual(len(again["entries"]), 4)

    def test_bad_date_falls_back_to_today(self):
        log = self.srv.log_for_date("not-a-date")
        self.assertEqual(log["date"], date.today().isoformat())


class TimezoneTest(SandboxedServerTest):
    """Events are bucketed into days by local time, whatever the offset in
    the transcript."""

    tz = "America/Chicago"   # UTC-6 in January

    def write_session(self, sid, stamps, tokens=1500):
        d = self.projects_dir / "-tz"
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        for i, ts in enumerate(stamps):
            role = "user" if i % 2 == 0 else "assistant"
            msg = {"role": role, "content": f"{role} message {i} for {sid}"}
            if role == "assistant":
                msg["usage"] = {"input_tokens": tokens}
            lines.append(json.dumps({"type": role, "sessionId": sid, "cwd": "/nonexistent/tz",
                                     "timestamp": ts, "message": msg}))
        (d / f"{sid}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_utc_evening_lands_on_previous_local_day(self):
        # 03:30Z on Jan 16 is 21:30 on Jan 15 in Chicago.
        self.write_session("late", ["2026-01-16T03:30:00Z", "2026-01-16T03:45:00.123Z"])
        entries, *_ = self.srv._compute_day(date(2026, 1, 15))
        self.assertEqual([(e["id"], e["start"], e["end"]) for e in entries],
                         [("late", "21:30", "21:45")])
        self.assertEqual(self.srv._compute_day(date(2026, 1, 16))[0], [])

    def test_explicit_offsets_and_naive_timestamps(self):
        # +05:30 and naive (treated as UTC) both convert to local time.
        self.write_session("offsets", ["2026-01-15T20:00:00+05:30", "2026-01-15T15:00:00"])
        s = by_id(self.srv.collect_sessions())["offsets"]
        local = [ts.strftime("%Y-%m-%d %H:%M") for ts, _, _ in s["events"]]
        self.assertEqual(local, ["2026-01-15 08:30", "2026-01-15 09:00"])

    def test_session_spanning_midnight_splits_across_days(self):
        # 23:50 and 00:20 local, with tokens on each side.
        self.write_session("span", ["2026-01-16T05:50:00Z", "2026-01-16T05:55:00Z",
                                    "2026-01-16T06:20:00Z", "2026-01-16T06:25:00Z"])
        day1, *_ = self.srv._compute_day(date(2026, 1, 15))
        day2, *_ = self.srv._compute_day(date(2026, 1, 16))
        self.assertEqual([(e["start"], e["end"]) for e in day1], [("23:50", "23:55")])
        self.assertEqual([(e["start"], e["end"]) for e in day2], [("00:20", "00:25")])
        self.assertEqual(self.srv.available_dates(), ["2026-01-16", "2026-01-15"])

    def test_positive_offset_zone(self):
        set_tz("Asia/Tokyo")   # UTC+9: 20:00Z on Jan 15 is 05:00 on Jan 16
        self.write_session("tokyo", ["2026-01-15T20:00:00Z", "2026-01-15T20:10:00Z"])
        self.assertEqual(self.srv._compute_day(date(2026, 1, 15))[0], [])
        entries, *_ = self.srv._compute_day(date(2026, 1, 16))
        self.assertEqual([(e["id"], e["start"]) for e in entries], [("tokyo", "05:00")])

    def test_garbage_timestamps_parse_to_none(self):
        for bad in (None, "", 17, "yesterday", "2026-13-45T00:00:00Z"):
            self.assertIsNone(self.srv.parse_ts(bad))
