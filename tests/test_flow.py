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
