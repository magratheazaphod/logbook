"""The project-flow endpoint: active minutes per project per bucket."""

from datetime import date

from support import FIXTURE_DAY, HttpTestCase


class FlowTest(HttpTestCase):
    copy_fixtures = True

    def test_fixture_day_lands_in_its_bucket(self):
        day = date.fromisoformat(FIXTURE_DAY)
        for bucket in ("day", "week"):
            flow = self.srv.project_flow(bucket, 3, today=day)
            self.assertEqual(len(flow["buckets"]), 3)
            self.assertTrue(flow["projects"])
            for p in flow["projects"]:
                self.assertEqual(len(p["minutes"]), 3)
                self.assertEqual(sum(p["minutes"][:2]), 0)  # nothing before the fixture day
                self.assertGreaterEqual(p["total"], 1)

    def test_rank_is_the_same_in_every_range(self):
        day = date.fromisoformat(FIXTURE_DAY)
        a = {p["name"]: p["rank"] for p in self.srv.project_flow("day", 1, today=day)["projects"]}
        b = {p["name"]: p["rank"] for p in self.srv.project_flow("week", 52, today=day)["projects"]}
        self.assertTrue(a)
        for name, r in a.items():
            self.assertEqual(b[name], r)

    def test_week_buckets_start_on_monday(self):
        flow = self.srv.project_flow("week", 4)
        for b in flow["buckets"]:
            self.assertEqual(date.fromisoformat(b).weekday(), 0)

    def test_bad_bucket_is_400(self):
        code, _ = self.json_request("GET", "/api/flow?bucket=month")
        self.assertEqual(code, 400)
        code, body = self.json_request("GET", "/api/flow?bucket=day&count=7")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["buckets"]), 7)


class FlowHistoryTest(HttpTestCase):
    copy_fixtures = True

    def write_history(self, rows):
        import json
        from datetime import datetime
        with open(self.srv.HISTORY_FILE, "w") as f:
            for when, proj in rows:
                f.write(json.dumps({"timestamp": datetime.fromisoformat(when).timestamp() * 1000,
                                    "project": proj, "sessionId": "s1", "display": "x"}) + "\n")

    def test_days_before_transcripts_come_from_history(self):
        self.write_history([("2026-01-10T10:00:00", "/x/old-proj"),
                            ("2026-01-10T10:10:00", "/x/old-proj"),
                            # a lone prompt on a day transcripts cover well: ignored
                            (FIXTURE_DAY + "T10:00:00", "/x/old-proj")])
        flow = self.srv.project_flow("day", 10, today=date.fromisoformat(FIXTURE_DAY))
        old = next(p for p in flow["projects"] if p["name"] == "old-proj")
        # 10 min gap + 5 min tail, all on Jan 10
        self.assertEqual(old["total"], 15)
        self.assertEqual(flow["estimated"], [flow["buckets"].index("2026-01-10")])

    def test_missing_history_is_harmless(self):
        flow = self.srv.project_flow("week", 4)
        self.assertEqual(flow["estimated"], [])
