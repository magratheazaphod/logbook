"""Board persistence: the rev 409 guard, day-plan rollover and daily backups."""

import json
from datetime import date, timedelta

from support import HttpTestCase, SandboxedServerTest


class BoardRevGuardTest(HttpTestCase):
    def disk(self):
        return json.loads(self.srv.BOARD_FILE.read_text(encoding="utf-8"))

    def test_fresh_board(self):
        code, board = self.json_request("GET", "/api/board")
        self.assertEqual(code, 200)
        self.assertEqual(board["rev"], 0)
        self.assertEqual((board["tasks"], board["ideas"], board["content"], board["dayPlans"]),
                         ([], [], [], {}))

    def test_save_with_current_rev_bumps_it(self):
        task = {"id": "t1", "title": "Write tests", "status": "backlog"}
        code, resp = self.json_request("POST", "/api/board", {"rev": 0, "tasks": [task]})
        self.assertEqual(code, 200)
        self.assertEqual(resp["rev"], 1)
        self.assertEqual(self.disk()["tasks"], [task])
        self.assertEqual(self.disk()["rev"], 1)
        code, resp = self.json_request("POST", "/api/board", {"rev": 1, "tasks": []})
        self.assertEqual((code, resp["rev"]), (200, 2))

    def test_stale_rev_is_rejected_with_fresh_board(self):
        keep = {"id": "t1", "title": "Newer work", "status": "doing"}
        self.json_request("POST", "/api/board", {"rev": 0, "tasks": [keep]})
        before = self.srv.BOARD_FILE.read_bytes()
        # A long-lived tab still holding rev 0 tries to save an empty board.
        code, resp = self.json_request("POST", "/api/board", {"rev": 0, "tasks": []})
        self.assertEqual(code, 409)
        self.assertEqual(resp["error"], "stale")
        self.assertEqual(resp["board"]["tasks"], [keep])
        self.assertEqual(resp["board"]["rev"], 1)
        self.assertEqual(self.srv.BOARD_FILE.read_bytes(), before)

    def test_missing_wrong_type_or_future_rev_is_rejected(self):
        self.json_request("POST", "/api/board", {"rev": 0, "tasks": [{"id": "a"}]})
        before = self.srv.BOARD_FILE.read_bytes()
        for rev in (None, "1", 1.5, 1.0, 2, -1, True, [1]):
            body = {"tasks": []} if rev is None else {"rev": rev, "tasks": []}
            code, resp = self.json_request("POST", "/api/board", body)
            self.assertEqual(code, 409, f"rev={rev!r} was accepted")
        self.assertEqual(self.srv.BOARD_FILE.read_bytes(), before)

    def test_bad_json_is_400_and_leaves_board_alone(self):
        before = self.srv.BOARD_FILE.read_bytes()
        code, _ = self.json_request("POST", "/api/board", raw=b"{not json")
        self.assertEqual(code, 400)
        self.assertEqual(self.srv.BOARD_FILE.read_bytes(), before)

    def test_agent_edit_on_disk_is_respected(self):
        # An agent appending to board.json directly (preserving rev) must not
        # be clobbered by a client holding the old rev once it bumps rev.
        board = self.disk()
        board["tasks"].append({"id": "agent", "title": "From cron", "status": "backlog"})
        board["rev"] = board.get("rev", 0) + 1
        self.srv.BOARD_FILE.write_text(json.dumps(board), encoding="utf-8")
        code, resp = self.json_request("POST", "/api/board", {"rev": 0, "tasks": []})
        self.assertEqual(code, 409)
        self.assertEqual(resp["board"]["tasks"][0]["id"], "agent")


class DayPlanRolloverTest(SandboxedServerTest):
    def test_unfinished_past_items_return_to_the_pile(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()
        self.srv.ensure_data()
        self.srv.save_board({
            "rev": 3, "tasks": [{"id": "b", "status": "backlog"}], "ideas": [], "content": [],
            "dayPlans": {
                yesterday: {"tasks": [{"id": "done", "status": "done"},
                                      {"id": "left", "status": "doing"}],
                            "ideas": [{"id": "idea"}]},
                today: {"tasks": [{"id": "now", "status": "doing"}], "ideas": []},
            },
        })
        board = self.srv.load_board()
        self.assertEqual([t["id"] for t in board["tasks"]], ["left", "b"])
        self.assertEqual([i["id"] for i in board["ideas"]], ["idea"])
        self.assertEqual([t["id"] for t in board["dayPlans"][yesterday]["tasks"]], ["done"])
        self.assertEqual(board["dayPlans"][yesterday]["ideas"], [])
        self.assertEqual(board["dayPlans"][today]["tasks"][0]["id"], "now")
        self.assertEqual(board["rev"], 4)   # the rollover is a write, so rev moves
        on_disk = json.loads(self.srv.BOARD_FILE.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["rev"], 4)

    def test_unreadable_board_loads_as_empty(self):
        self.srv.DATA_DIR.mkdir(parents=True)
        self.srv.BOARD_FILE.write_text("{truncated", encoding="utf-8")
        board = self.srv.load_board()
        self.assertEqual(board["tasks"], [])


class FakeDate(date):
    today_value = date(2026, 3, 1)

    @classmethod
    def today(cls):
        return cls.today_value


class DailyBackupTest(SandboxedServerTest):
    def setUp(self):
        super().setUp()
        self.srv.date = FakeDate
        FakeDate.today_value = date(2026, 3, 1)

    def backups(self):
        return sorted(p.name for p in self.srv.BOARD_BACKUP_DIR.glob("board-*.json"))

    def test_backup_holds_state_before_first_write_of_the_day(self):
        self.srv.ensure_data()   # first ever write: nothing to back up yet
        self.assertEqual(self.backups(), [])
        self.srv.save_board({"rev": 1, "tasks": [{"id": "day1"}]})
        backup = self.srv.BOARD_BACKUP_DIR / "board-2026-03-01.json"
        self.assertEqual(json.loads(backup.read_text())["tasks"], [])   # pre-change state
        self.srv.save_board({"rev": 2, "tasks": [{"id": "day1-later"}]})
        self.assertEqual(json.loads(backup.read_text())["tasks"], [])   # not overwritten

        FakeDate.today_value = date(2026, 3, 2)
        self.srv.save_board({"rev": 3, "tasks": [{"id": "day2"}]})
        day2 = self.srv.BOARD_BACKUP_DIR / "board-2026-03-02.json"
        self.assertEqual(json.loads(day2.read_text())["tasks"], [{"id": "day1-later"}])
        self.assertEqual(self.backups(), ["board-2026-03-01.json", "board-2026-03-02.json"])

    def test_backups_are_pruned_to_the_newest_60(self):
        self.srv.ensure_data()
        self.srv.BOARD_BACKUP_DIR.mkdir(parents=True)
        start = date(2025, 12, 1)
        for i in range(70):
            d = (start + timedelta(days=i)).isoformat()
            (self.srv.BOARD_BACKUP_DIR / f"board-{d}.json").write_text("{}")
        other = self.srv.BOARD_BACKUP_DIR / "notes.txt"
        other.write_text("keep me")
        self.srv.save_board({"rev": 1})
        names = self.backups()
        self.assertEqual(len(names), 60)
        self.assertEqual(names[-1], "board-2026-03-01.json")
        self.assertTrue(other.exists())

    def test_writes_are_atomic_and_leave_no_temp_file(self):
        self.srv.ensure_data()
        self.srv.save_board({"rev": 1, "tasks": [{"id": "x", "title": "Unicode ok - é"}]})
        self.assertEqual(list(self.srv.DATA_DIR.glob("*.tmp")), [])
        text = self.srv.BOARD_FILE.read_text(encoding="utf-8")
        self.assertIn("é", text)
