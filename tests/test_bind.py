"""Listening on both loopbacks, and refusing loudly when the port is taken."""

import contextlib
import errno
import io
import json
import socket
import threading
import unittest
import urllib.request

from support import SandboxedServerTest


def ipv6_loopback_available():
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


HAS_V6 = ipv6_loopback_available()


def listener(family, host, port=0):
    s = socket.socket(family, socket.SOCK_STREAM)
    if family == socket.AF_INET6:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    s.bind((host, port))
    s.listen()
    return s


class BindCase(SandboxedServerTest):
    def setUp(self):
        super().setUp()
        self.srv.ensure_data()
        self.warnings = []

    def bind(self, port=0):
        servers = self.srv.bind_loopbacks(port, self.srv.Handler, warn=self.warnings.append)
        for s in servers:
            self.addCleanup(s.server_close)
        return servers

    def run_servers(self, servers):
        t = threading.Thread(target=self.srv.serve, args=(servers,), daemon=True)
        t.start()
        def stop():
            servers[-1].shutdown()
            t.join(5)
        self.addCleanup(stop)

    def get_board(self, host, port):
        with urllib.request.urlopen(f"http://{host}:{port}/api/board", timeout=10) as r:
            return json.loads(r.read())


class DualBindTest(BindCase):
    @unittest.skipUnless(HAS_V6, "no IPv6 loopback on this host")
    def test_serves_on_both_loopbacks_at_one_port(self):
        servers = self.bind()
        self.assertEqual([s.server_address[0] for s in servers], ["127.0.0.1", "::1"])
        port = servers[0].server_address[1]
        self.assertEqual(servers[1].server_address[1], port)
        self.run_servers(servers)
        self.assertIn("rev", self.get_board("127.0.0.1", port))
        self.assertIn("rev", self.get_board("[::1]", port))
        self.assertEqual(self.warnings, [])

    def test_never_binds_a_public_interface(self):
        for s in self.bind():
            self.assertIn(s.server_address[0], ("127.0.0.1", "::1"))

    @unittest.skipUnless(HAS_V6, "no IPv6 loopback on this host")
    def test_squatter_on_ipv6_loopback_is_refused(self):
        squat = listener(socket.AF_INET6, "::1")
        self.addCleanup(squat.close)
        port = squat.getsockname()[1]
        with self.assertRaises(self.srv.PortInUse) as cm:
            self.bind(port)
        self.assertIn("::1", str(cm.exception))
        self.assertIn(str(port), str(cm.exception))
        # The IPv4 half must not be left holding the port.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))

    @unittest.skipUnless(HAS_V6, "no IPv6 loopback on this host")
    def test_later_server_cannot_take_either_loopback(self):
        port = self.bind()[0].server_address[1]
        for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                with self.assertRaises(OSError) as cm:
                    s.bind((host, port))
                self.assertEqual(cm.exception.errno, errno.EADDRINUSE)

    def test_host_without_ipv6_falls_back_to_ipv4_with_a_warning(self):
        def no_v6(*a, **k):
            raise OSError(errno.EADDRNOTAVAIL, "Can't assign requested address")
        self.srv._IPv6Server = no_v6
        servers = self.bind()
        self.assertEqual([s.server_address[0] for s in servers], ["127.0.0.1"])
        self.assertEqual(len(self.warnings), 1)
        self.assertIn("127.0.0.1 only", self.warnings[0])
        self.run_servers(servers)
        self.assertIn("rev", self.get_board("127.0.0.1", servers[0].server_address[1]))


class PortProbeTest(BindCase):
    def test_main_exits_loudly_when_the_port_is_taken(self):
        squat = listener(socket.AF_INET, "127.0.0.1")
        self.addCleanup(squat.close)
        self.srv.PORT = squat.getsockname()[1]
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.srv.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Logbook could not start", err.getvalue())
        self.assertIn("already in use", err.getvalue())


if __name__ == "__main__":
    unittest.main()
