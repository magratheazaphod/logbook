"""config.json loading: every key optional, and a bad file means defaults."""

import contextlib
import io
import json

from support import SandboxedServerTest


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

    def test_malformed_json_is_ignored_with_a_note(self):
        for raw in ('{"coworkSkipSessions": ', "", "not json", b"\xff\xfe\x00garbage"):
            srv, out = self.reload(raw)
            self.assertEqual(srv.CONFIG, {}, repr(raw))
            self.assertDefaults(srv)
            self.assertIn("Ignoring unreadable", out)
