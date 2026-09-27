"""Handoff docs: ids can't be steered at arbitrary files, and only drafts
are ever written to."""

import base64
import json
import re

from support import HttpTestCase

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


class HandoffTest(HttpTestCase):
    def setUp(self):
        super().setUp()
        # A file outside the data dir standing in for a real doc on disk.
        self.outside = self.tmp / "elsewhere"
        self.outside.mkdir()
        self.doc = self.outside / "plan.md"
        self.doc.write_text("# Plan\nOriginal text", encoding="utf-8")
        self.secret = self.outside / "secret.txt"
        self.secret.write_text("TOP SECRET", encoding="utf-8")

    def add(self, **body):
        code, resp = self.json_request("POST", "/api/handoff", body)
        self.assertEqual(code, 200, resp)
        return resp

    def get(self, hid):
        return self.json_request("GET", "/api/handoff?id=" + hid)

    def test_doc_tracks_live_file_then_falls_back_to_snapshot(self):
        rec = self.add(name="plan.md", path=str(self.doc), text="# Plan\nOriginal text")
        self.assertRegex(rec["id"], r"^[0-9a-f]{12}$")
        self.assertEqual(rec["kind"], "doc")
        self.doc.write_text("# Plan\nEdited later", encoding="utf-8")
        code, got = self.get(rec["id"])
        self.assertEqual((code, got["source"], got["text"]), (200, "live", "# Plan\nEdited later"))
        self.doc.unlink()
        code, got = self.get(rec["id"])
        self.assertEqual((got["source"], got["text"]), ("snapshot", "# Plan\nOriginal text"))

    def test_bogus_path_is_not_recorded(self):
        rec = self.add(name="x.md", path=str(self.outside / "missing.md"), text="snap")
        idx = json.loads(self.srv.HANDOFF_INDEX_FILE.read_text())
        self.assertEqual(idx[rec["id"]]["path"], "")
        rec = self.add(name="dir.md", path=str(self.outside), text="snap")   # a directory
        self.assertEqual(json.loads(self.srv.HANDOFF_INDEX_FILE.read_text())[rec["id"]]["path"], "")

    def test_ids_cannot_escape(self):
        self.add(name="plan.md", path=str(self.doc), text="x")
        # Also plant a file named like a traversal target inside handoffs/.
        attempts = [
            "", "..", "../../elsewhere/secret", "../elsewhere/secret.txt",
            str(self.secret), "%2e%2e%2fsecret", "index", "index.json",
            "__proto__", "constructor", "*", "%27%20OR%201%3D1", "a" * 5000,
        ]
        for hid in attempts:
            for path in ("/api/handoff?id=", "/api/handoff/image?id="):
                code, body, _ = self.request("GET", path + hid)
                self.assertEqual(code, 404, f"{path}{hid!r} -> {code}")
                self.assertNotIn(b"TOP SECRET", body)

    def test_repeated_and_odd_query_params(self):
        rec = self.add(name="plan.md", path=str(self.doc), text="x")
        code, _ = self.get(rec["id"] + "&id=../secret")
        self.assertEqual(code, 200)     # first id wins, and it's a real one
        code, _, _ = self.request("GET", "/api/handoff?id=" + rec["id"] + "%00")
        self.assertEqual(code, 404)

    def test_client_cannot_choose_the_id_or_snapshot_name(self):
        rec = self.add(id="../../pwned", name="../../pwned.md", path="", text="hello")
        self.assertRegex(rec["id"], r"^[0-9a-f]{12}$")
        files = sorted(p.name for p in self.srv.HANDOFF_DIR.iterdir())
        self.assertEqual(files, sorted(["index.json", rec["id"] + ".md"]))
        self.assertFalse((self.tmp / "pwned.md").exists())
        self.assertFalse(any(self.tmp.rglob("pwned*")))

    def test_drafts_are_the_only_writable_kind(self):
        doc = self.add(name="plan.md", path=str(self.doc), text="# Plan\nOriginal text")
        code, resp = self.json_request("POST", "/api/handoff/draft", {"id": doc["id"], "text": "OVERWRITE"})
        self.assertEqual((code, resp["error"]), (400, "not a draft"))
        self.assertEqual(self.doc.read_text(), "# Plan\nOriginal text")
        snap = self.srv.HANDOFF_DIR / (doc["id"] + ".md")
        self.assertEqual(snap.read_text(), "# Plan\nOriginal text")

        for hid in ("", "nope", "../elsewhere/plan", None, 123, ["x"], {"id": doc["id"]}):
            code, resp = self.json_request("POST", "/api/handoff/draft", {"id": hid, "text": "x"})
            self.assertEqual(code, 400, f"id={hid!r}")
        self.assertEqual(self.doc.read_text(), "# Plan\nOriginal text")

    def test_draft_round_trip_and_ignores_client_path(self):
        rec = self.add(name="Draft", kind="draft", path=str(self.secret), text="first")
        self.assertEqual(rec["kind"], "draft")
        idx = json.loads(self.srv.HANDOFF_INDEX_FILE.read_text())
        self.assertEqual(idx[rec["id"]]["path"], "")    # a draft never tracks a real file
        code, resp = self.json_request("POST", "/api/handoff/draft", {"id": rec["id"], "text": "second"})
        self.assertEqual((code, resp["ok"]), (200, True))
        code, got = self.get(rec["id"])
        self.assertEqual((got["kind"], got["source"], got["text"]), ("draft", "saved", "second"))
        self.assertEqual(self.secret.read_text(), "TOP SECRET")
        self.assertEqual(list(self.srv.HANDOFF_DIR.glob("*.tmp")), [])

    def test_unknown_kinds_become_docs(self):
        rec = self.add(name="x", kind="../../draft", text="t")
        self.assertEqual(rec["kind"], "doc")
        code, resp = self.json_request("POST", "/api/handoff/draft", {"id": rec["id"], "text": "y"})
        self.assertEqual(code, 400)

    def test_size_limits(self):
        big = "x" * (self.srv.HANDOFF_MAX_BYTES + 1)
        code, resp = self.json_request("POST", "/api/handoff", {"name": "big", "text": big})
        self.assertEqual((code, resp["error"]), (400, "file too large"))
        rec = self.add(name="d", kind="draft", text="")
        code, resp = self.json_request("POST", "/api/handoff/draft", {"id": rec["id"], "text": big})
        self.assertEqual((code, resp["error"]), (400, "draft too large"))

    def test_live_file_over_size_limit_falls_back_to_snapshot(self):
        rec = self.add(name="plan.md", path=str(self.doc), text="snapshot")
        self.srv.HANDOFF_MAX_BYTES = 10
        self.doc.write_text("this live file is now too big", encoding="utf-8")
        code, got = self.get(rec["id"])
        self.assertEqual((got["source"], got["text"]), ("snapshot", "snapshot"))

    def test_image_round_trip(self):
        rec = self.add(name="shot.png", kind="image", mime="image/png",
                       data=base64.b64encode(PNG).decode())
        self.assertEqual(rec["kind"], "image")
        code, body, ctype = self.request("GET", "/api/handoff/image?id=" + rec["id"])
        self.assertEqual((code, body, ctype), (200, PNG, "image/png"))
        code, meta = self.get(rec["id"])
        self.assertEqual((meta["kind"], meta["text"]), ("image", ""))
        # A doc id is not an image, and an image is not a writable draft.
        doc = self.add(name="plan.md", path=str(self.doc), text="x")
        self.assertEqual(self.request("GET", "/api/handoff/image?id=" + doc["id"])[0], 404)
        code, _ = self.json_request("POST", "/api/handoff/draft", {"id": rec["id"], "text": "x"})
        self.assertEqual(code, 400)

    def test_bad_images_are_rejected(self):
        cases = [
            ({"mime": "text/html", "name": "x.html", "data": base64.b64encode(b"<script>").decode()},
             "unsupported image type"),
            ({"mime": "image/png", "name": "x.png", "data": "!!!not base64!!!"}, "bad image data"),
            ({"mime": "image/png", "name": "x.png", "data": ""}, "empty image"),
        ]
        for extra, err in cases:
            code, resp = self.json_request("POST", "/api/handoff", dict(kind="image", **extra))
            self.assertEqual((code, resp["error"]), (400, err))
        self.assertFalse(self.srv.HANDOFF_INDEX_FILE.exists())

    def test_image_extension_comes_from_the_allowlist(self):
        rec = self.add(name="../../x.png", kind="image", mime="image/png; charset=binary",
                       data=base64.b64encode(PNG).decode())
        names = [p.name for p in self.srv.HANDOFF_DIR.iterdir() if p.name != "index.json"]
        self.assertEqual(names, [rec["id"] + ".png"])
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{12}\.png", n) for n in names))


class StaticFileTest(HttpTestCase):
    def test_icon_route_cannot_escape_icons_dir(self):
        for path in ("/icons/../server.py", "/icons/..%2fserver.py", "/icons/%2e%2e/server.py",
                     "/icons/../../etc/passwd", "/icons/"):
            code, body, _ = self.request("GET", path)
            self.assertEqual(code, 404, path)
            self.assertNotIn(b"import", body)

    def test_index_and_manifest_serve(self):
        code, body, ctype = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertTrue(ctype.startswith("text/html"))
        code, manifest = self.json_request("GET", "/manifest.webmanifest")
        self.assertEqual((code, manifest["name"]), (200, "Logbook"))
