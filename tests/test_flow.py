"""The project-flow endpoint: active minutes per project per time bucket."""

import json
from datetime import datetime

from support import FIXTURE_DAY, HttpTestCase


def t(text):
    return datetime.fromisoformat(text)


class FlowTest(HttpTestCase):
    copy_fixtures = True

    def test_fixture_day_lands_in_its_bucket(self):
        for unit, start in (("1d", "2026-01-13"), ("1w", "2025-12-29")):
            flow = self.srv.project_flow(t(start), t(FIXTURE_DAY + "T23:59"), unit)
            self.assertTrue(flow["projects"])
            self.assertEqual(len(flow["edges"]), len(flow["buckets"]) + 1)
            last = len(flow["buckets"]) - 1
            for p in flow["projects"]:
                self.assertEqual(sum(p["minutes"][:last]), 0)
                self.assertGreater(p["total"], 0)

    def test_zooming_in_keeps_the_total(self):
        day = self.srv.project_flow(t(FIXTURE_DAY), t(FIXTURE_DAY + "T23:59"), "1d")
        quarter = self.srv.project_flow(t(FIXTURE_DAY), t(FIXTURE_DAY + "T23:59"), "15m")
        self.assertEqual(len(quarter["buckets"]), 96)
        tot = lambda f: {p["name"]: round(sum(p["minutes"])) for p in f["projects"]}
        self.assertEqual(tot(day), tot(quarter))
        self.assertTrue(quarter["buckets"][1].endswith("T00:15"))

    def test_rank_is_the_same_at_every_zoom(self):
        a = {p["name"]: p["rank"] for p in
             self.srv.project_flow(t(FIXTURE_DAY), t(FIXTURE_DAY + "T23:59"), "1h")["projects"]}
        b = {p["name"]: p["rank"] for p in
             self.srv.project_flow(t("2025-06-01"), t("2026-06-01"), "1w")["projects"]}
        self.assertTrue(a)
        for name, r in a.items():
            self.assertEqual(b[name], r)

    def test_weeks_start_on_monday(self):
        flow = self.srv.project_flow(t("2026-01-15"), t("2026-03-01"), "1w")
        for b in flow["buckets"]:
            self.assertEqual(t(b).weekday(), 0)

    def test_bad_requests_are_400(self):
        for q in ["from=2026-01-01&to=2026-02-01&unit=month",
                  "from=2026-1-01&to=2026-02-01&unit=1d",
                  "from=2026-02-01&to=2026-01-01&unit=1d",
                  "from=2020-01-01&to=2026-01-01&unit=15m"]:
            code, _ = self.json_request("GET", "/api/flow?" + q)
            self.assertEqual(code, 400, q)
        code, body = self.json_request("GET", "/api/flow?from=2026-01-09&to=2026-01-16&unit=1d")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["buckets"]), 7)


class FlowHistoryTest(HttpTestCase):
    copy_fixtures = True

    def write_history(self, rows):
        with open(self.srv.HISTORY_FILE, "w") as f:
            for when, proj in rows:
                f.write(json.dumps({"timestamp": t(when).timestamp() * 1000,
                                    "project": proj, "sessionId": "s1", "display": "x"}) + "\n")

    def test_days_without_transcripts_come_from_history(self):
        self.write_history([("2026-01-10T10:00:00", "/x/old-proj"),
                            ("2026-01-10T10:10:00", "/x/old-proj"),
                            # a lone prompt on a day transcripts cover well: ignored
                            (FIXTURE_DAY + "T10:00:00", "/x/old-proj")])
        flow = self.srv.project_flow(t("2026-01-06"), t(FIXTURE_DAY + "T23:59"), "1d")
        old = next(p for p in flow["projects"] if p["name"] == "old-proj")
        self.assertEqual(old["total"], 15)    # 10 min gap + 5 min tail
        self.assertEqual(flow["estimated"], [flow["buckets"].index("2026-01-10T00:00")])

    def test_missing_history_is_harmless(self):
        flow = self.srv.project_flow(t("2026-01-01"), t("2026-02-01"), "1w")
        self.assertEqual(flow["estimated"], [])
