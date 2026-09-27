"""config.json loading: every key optional, and a bad file means defaults."""

import contextlib
import io
import json

from support import FIXTURES, SandboxedServerTest


class ConfigCase(SandboxedServerTest):
    def reload(self, config):
        """Write `config` (dict/list -> JSON, str/bytes -> raw, None -> no
        file) and import a fresh server.py against it, capturing its output."""
        if self.config_file.exists():
            self.config_file.unlink()
        if isinstance(config, (dict, list)):
            self.config_file.write_text(json.dumps(config), encoding="utf-8")
        elif isinstance(config, str):
            self.config_file.write_text(config, encoding="utf-8")
        elif isinstance(config, bytes):
            self.config_file.write_bytes(config)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            srv = self.load_server()
        return srv, out.getvalue()

    def assertDefaults(self, srv):
        self.assertIsInstance(srv.CONFIG, dict)
        self.assertEqual(srv.ISSUE_MATCH_OWNERS, [])
        self.assertEqual(srv.ISSUE_MATCH_REPOS, [])
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, set())


class ConfigLoadingTest(ConfigCase):
    def test_missing_file_means_defaults_quietly(self):
        srv, out = self.reload(None)
        self.assertEqual(srv.CONFIG, {})
        self.assertDefaults(srv)
        self.assertEqual(out, "")

    def test_full_config(self):
        srv, _ = self.reload({
            "issueMatch": {"owners": ["some-org"], "repos": ["someone/repo"]},
            "coworkSkipSessions": ["abc", "def"],
            "launchdLabel": "local.logbook",
        })
        self.assertEqual(srv.ISSUE_MATCH_OWNERS, ["some-org"])
        self.assertEqual(srv.ISSUE_MATCH_REPOS, ["someone/repo"])
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc", "def"})

    def test_example_config_parses(self):
        example = json.loads((FIXTURES.parent.parent / "config.example.json").read_text())
        srv, out = self.reload(example)
        self.assertEqual(out, "")
        self.assertEqual(srv.ISSUE_MATCH_REPOS, example["issueMatch"]["repos"])

    def test_partial_configs_default_the_rest(self):
        srv, _ = self.reload({"coworkSkipSessions": ["abc"]})
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc"})
        self.assertEqual((srv.ISSUE_MATCH_OWNERS, srv.ISSUE_MATCH_REPOS), ([], []))
        srv, _ = self.reload({"issueMatch": {"repos": ["a/b"]}})
        self.assertEqual((srv.ISSUE_MATCH_OWNERS, srv.ISSUE_MATCH_REPOS), ([], ["a/b"]))
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, set())
        srv, _ = self.reload({})
        self.assertDefaults(srv)

    def test_malformed_json_is_ignored_with_a_note(self):
        for raw in ('{"issueMatch": ', "", "not json", b"\xff\xfe\x00garbage"):
            srv, out = self.reload(raw)
            self.assertEqual(srv.CONFIG, {}, repr(raw))
            self.assertDefaults(srv)
            self.assertIn("Ignoring unreadable", out)

    def test_non_object_top_level_is_ignored(self):
        for value in ([1, 2], "a string", 42, None):
            srv, _ = self.reload(json.dumps(value))
            self.assertEqual(srv.CONFIG, {})
            self.assertDefaults(srv)

    def test_wrong_types_degrade_instead_of_crashing(self):
        for cfg in (
            {"issueMatch": ["some-org"]},
            {"issueMatch": "some-org"},
            {"issueMatch": None},
            {"issueMatch": {"owners": "some-org", "repos": {"a": "b"}}},
            {"coworkSkipSessions": "abc"},       # a string is not a list of ids
            {"coworkSkipSessions": {"abc": True}},
            {"coworkSkipSessions": None},
        ):
            srv, _ = self.reload(cfg)
            self.assertDefaults(srv)

    def test_non_string_list_items_are_dropped(self):
        srv, _ = self.reload({"issueMatch": {"owners": ["ok", 7, None, "", {"x": 1}]},
                              "coworkSkipSessions": ["abc", ["nested"], 3]})
        self.assertEqual(srv.ISSUE_MATCH_OWNERS, ["ok"])
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc"})

    def test_config_file_is_a_directory(self):
        self.config_file.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            srv = self.load_server()
        self.assertEqual(srv.CONFIG, {})

    def test_issue_match_stays_off_without_gh(self):
        srv, _ = self.reload({"issueMatch": {"owners": ["some-org"]}})
        self.assertIsNone(srv.find_matching_issue("Fix the thing"))
