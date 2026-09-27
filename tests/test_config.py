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
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, set())


class ConfigLoadingTest(ConfigCase):
    def test_missing_file_means_defaults_quietly(self):
        srv, out = self.reload(None)
        self.assertEqual(srv.CONFIG, {})
        self.assertDefaults(srv)
        self.assertEqual(out, "")

    def test_full_config(self):
        srv, _ = self.reload({
            "coworkSkipSessions": ["abc", "def"],
            "launchdLabel": "local.logbook",
        })
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc", "def"})

    def test_example_config_parses(self):
        example = json.loads((FIXTURES.parent.parent / "config.example.json").read_text())
        srv, out = self.reload(example)
        self.assertEqual(out, "")
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, set(example["coworkSkipSessions"]))

    def test_partial_configs_default_the_rest(self):
        srv, _ = self.reload({"coworkSkipSessions": ["abc"]})
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc"})
        srv, _ = self.reload({"launchdLabel": "x"})
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, set())
        srv, _ = self.reload({})
        self.assertDefaults(srv)

    def test_malformed_json_is_ignored_with_a_note(self):
        for raw in ('{"coworkSkipSessions": ', "", "not json", b"\xff\xfe\x00garbage"):
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
            {"issueMatch": {"owners": ["some-org"]}},  # retired key: ignored
            {"coworkSkipSessions": "abc"},       # a string is not a list of ids
            {"coworkSkipSessions": {"abc": True}},
            {"coworkSkipSessions": None},
        ):
            srv, _ = self.reload(cfg)
            self.assertDefaults(srv)

    def test_non_string_list_items_are_dropped(self):
        srv, _ = self.reload({"coworkSkipSessions": ["abc", ["nested"], 3, "", None]})
        self.assertEqual(srv.COWORK_SESSION_DENYLIST, {"abc"})

    def test_config_file_is_a_directory(self):
        self.config_file.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            srv = self.load_server()
        self.assertEqual(srv.CONFIG, {})

    def test_issue_auto_match_is_gone(self):
        srv, _ = self.reload({"issueMatch": {"owners": ["some-org"]}})
        for name in ("find_matching_issue", "GH_BIN", "ISSUE_MATCH_OWNERS", "ISSUE_MATCH_REPOS"):
            self.assertFalse(hasattr(srv, name), name)
