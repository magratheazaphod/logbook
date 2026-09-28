"""Which dates the daily log accepts, and what a future day looks like."""

from datetime import date, timedelta

from support import FIXTURE_DAY, HttpTestCase


class LogDateTest(HttpTestCase):
    copy_fixtures = True

    def cached_days(self):
        f = self.srv.DAY_LOG_CACHE_FILE
        return set(self.srv._load_day_log_cache()) if f.exists() else set()

    def test_parse_day_is_strict(self):
        self.assertEqual(self.srv.parse_day("2026-09-27"), date(2026, 9, 27))
        # A date field mid-edit, or another spelling of the same day.
        for bad in ["2-09-27", "20260927", "2026-9-27", "2026-02-30", "", "today"]:
            with self.assertRaises(ValueError, msg=bad):
                self.srv.parse_day(bad)

    def test_malformed_date_is_rejected_not_swapped_for_today(self):
        code, body = self.json_request("GET", "/api/log?date=2-09-27")
        self.assertEqual(code, 400)
        self.assertIn("YYYY-MM-DD", body["error"])
        self.assertEqual(self.cached_days(), set())

    def test_well_formed_date_still_served(self):
        code, body = self.json_request("GET", "/api/log?date=" + FIXTURE_DAY)
        self.assertEqual(code, 200)
        self.assertEqual(body["date"], FIXTURE_DAY)

    def test_future_day_is_empty_and_never_frozen(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        code, body = self.json_request("GET", "/api/log?date=" + future)
        self.assertEqual(code, 200)
        self.assertEqual(body["date"], future)
        self.assertEqual(body["entries"], [])
        self.assertFalse(body["pending"])
        self.assertNotIn(future, self.cached_days())

    def test_day_summary_endpoints_reject_bad_dates(self):
        for path, payload in [("/api/day-summary", {"date": "2-09-27", "text": "x"}),
                              ("/api/day-summary", {"text": "x"}),
                              ("/api/day-summary/regenerate", {"date": "20260927"})]:
            code, _ = self.json_request("POST", path, payload)
            self.assertEqual(code, 400, path)
        self.assertFalse(self.srv.DAY_SUMMARY_FILE.exists()
                         and "2-09-27" in self.srv._load_day_summaries())
