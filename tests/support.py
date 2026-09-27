"""Shared helpers: load a fresh, fully sandboxed copy of server.py per test.

server.py resolves its paths, config and the `claude`/`gh` binaries once at
import, so each test imports its own copy with the environment pointed at a
temp dir. Nothing a test does can reach the real data/, config.json,
~/.claude/projects, the Cowork sessions dir, or a billable `claude -p` call.
"""

import importlib.util
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER_PY = REPO / "server.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Every day the fixtures describe (in UTC).
FIXTURE_DAY = "2026-01-15"


def set_tz(name):
    """Switch the process's local timezone (POSIX only; CI runs macOS/Linux)."""
    os.environ["TZ"] = name
    time.tzset()


class SandboxedServerTest(unittest.TestCase):
    """Gives each test `self.srv` - a private import of server.py whose data
    dir, config file, transcript dirs and PATH all live under `self.tmp`."""

    # Subclasses may set these before setUp runs.
    config = None            # dict -> written as JSON; str -> written raw; None -> no file
    copy_fixtures = False    # copy tests/fixtures into the sandbox's transcript dirs
    tz = "UTC"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="logbook-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.data_dir = self.tmp / "data"
        self.projects_dir = self.tmp / "projects"
        self.cowork_dir = self.tmp / "cowork"
        self.config_file = self.tmp / "config.json"
        empty_bin = self.tmp / "bin"
        empty_bin.mkdir()

        if self.copy_fixtures:
            shutil.copytree(FIXTURES / "projects", self.projects_dir)
            shutil.copytree(FIXTURES / "cowork", self.cowork_dir)
        if isinstance(self.config, (dict, list)):
            self.config_file.write_text(json.dumps(self.config), encoding="utf-8")
        elif isinstance(self.config, str):
            self.config_file.write_text(self.config, encoding="utf-8")

        saved_env = dict(os.environ)

        def restore_env():
            os.environ.clear()
            os.environ.update(saved_env)
            time.tzset()
        self.addCleanup(restore_env)

        os.environ.update({
            "LOGBOOK_DATA_DIR": str(self.data_dir),
            "LOGBOOK_CONFIG": str(self.config_file),
            "CLAUDE_PROJECTS_DIR": str(self.projects_dir),
            "COWORK_SESSIONS_DIR": str(self.cowork_dir),
            # No `claude` reachable: summaries stay off.
            "PATH": str(empty_bin),
        })
        os.environ.pop("LOGBOOK_MIN_TOKENS", None)
        set_tz(self.tz)

        self.srv = self.load_server()

    def load_server(self):
        name = f"logbook_server_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(name, SERVER_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.addCleanup(mod._summary_pool.shutdown, True)

        # Belt and braces: refuse to run if anything points outside the sandbox.
        for attr in ("DATA_DIR", "BOARD_FILE", "HANDOFF_DIR", "CONFIG_FILE",
                     "PROJECTS_DIR", "COWORK_SESSIONS_DIR", "SUMMARY_CACHE_FILE",
                     "DAY_LOG_CACHE_FILE", "DAY_SUMMARY_FILE", "BOARD_BACKUP_DIR"):
            path = Path(getattr(mod, attr)).resolve()
            assert self.tmp in path.parents, f"{attr} escaped the sandbox: {path}"
        assert mod.CLAUDE_BIN is None, "a real `claude` binary is reachable"
        return mod


class HttpTestCase(SandboxedServerTest):
    """Runs the real Handler on an ephemeral 127.0.0.1 port."""

    def setUp(self):
        super().setUp()
        self.srv.ensure_data()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.srv.Handler)
        t = threading.Thread(target=self.httpd.serve_forever, args=(0.05,), daemon=True)
        t.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def request(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "")

    def json_request(self, method, path, body=None, raw=None):
        code, payload, _ = self.request(method, path, body, raw)
        return code, json.loads(payload)
