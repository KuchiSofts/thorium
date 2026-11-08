# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import shutil
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from tools.build import mv2_check as mc

FAKE = Path(__file__).with_name("fake_mv2_browser.py")


class FakeBrowserMixin:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.ext = self.tmp / "ext"
        self.ext.mkdir()
        # a launcher the tool can run like a browser executable
        if sys.platform == "win32":
            self.browser = self.tmp / "fake.cmd"
            self.browser.write_text(f'@"{sys.executable}" -I "{FAKE}" %*\n', encoding="utf-8")
        else:
            self.browser = self.tmp / "fake.sh"
            self.browser.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{FAKE}" "$@"\n', encoding="utf-8")
            self.browser.chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class ArgsAndParsingTests(unittest.TestCase):
    def test_browser_args_are_safe_and_complete(self):
        args = mc.browser_args(Path("b.exe"), Path("prof"), 4321, Path("ext"), "http://127.0.0.1:4321/test.html")
        self.assertNotIn("--no-sandbox", args)
        self.assertIn("--headless=new", args)
        # no default apps: Thorium installs uBlock Origin from the Web Store into every new profile,
        # which would turn the control run into a blocked run (found on the real M156 build)
        self.assertIn("--disable-default-apps", args)
        self.assertIn("--user-data-dir=prof", args)
        self.assertIn(f"--host-resolver-rules=MAP {mc.AD_HOST} 127.0.0.1:4321", args)
        self.assertIn("--load-extension=ext", args)
        self.assertEqual(args[-1], "http://127.0.0.1:4321/test.html")
        self.assertFalse(any(a.startswith("--load-extension") for a in
                             mc.browser_args(Path("b.exe"), Path("prof"), 1, None, "u")))

    def test_parse_result(self):
        dom = '<html><pre id="thoron-mv2-result">{"attempts": 4, "loaded": 0, "ad_element_hidden": true}</pre>'
        self.assertEqual(mc.parse_result(dom), {"attempts": 4, "loaded": 0, "ad_element_hidden": True})
        self.assertIsNone(mc.parse_result("<html>no result</html>"))

    def test_server_counts_ad_requests_only(self):
        with mc.TestServer(Path(tempfile.gettempdir())) as server:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/pagead/js/adsbygoogle.js?n=1").read()
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/test.html").read()
            self.assertEqual(server.ad_requests, 1)


class VerdictTests(unittest.TestCase):
    CONTROL = {"ok": True, "ad_requests": 6, "page": {"attempts": 6, "loaded": 6, "ad_element_hidden": False}}

    def test_works_when_both_kinds_of_blocking_happen(self):
        blocked = {"ok": True, "ad_requests": 0, "page": {"attempts": 6, "loaded": 0, "ad_element_hidden": True}}
        self.assertEqual(mc.verdict(self.CONTROL, blocked)[0], "works")

    def test_fails_when_extension_changes_nothing(self):
        self.assertEqual(mc.verdict(self.CONTROL, dict(self.CONTROL))[0], "fails")

    def test_partial_when_only_one_kind_of_blocking_happens(self):
        cosmetic_only = {"ok": True, "ad_requests": 6, "page": {"attempts": 6, "loaded": 6, "ad_element_hidden": True}}
        self.assertEqual(mc.verdict(self.CONTROL, cosmetic_only)[0], "partial")

    def test_invalid_when_control_shows_no_ads(self):
        bad_control = {"ok": True, "ad_requests": 0, "page": {"attempts": 6, "loaded": 0, "ad_element_hidden": True}}
        self.assertEqual(mc.verdict(bad_control, bad_control)[0], "invalid")

    def test_invalid_when_a_run_failed(self):
        self.assertEqual(mc.verdict({"ok": False, "error": "timeout"}, self.CONTROL)[0], "invalid")


class EndToEndTests(FakeBrowserMixin, unittest.TestCase):
    def test_working_extension(self):
        report = mc.run_both(self.browser, self.ext, self.tmp / "work", timeout_s=60)
        self.assertEqual(report["verdict"], "works", report)
        self.assertEqual(report["control"]["ad_hits"], list(range(mc.ATTEMPTS)))
        self.assertEqual(report["with_extension"]["ad_requests"], 0)

    def test_blocking_that_starts_late_still_counts(self):
        # a blocker that is still starting lets the first attempts through; only the last ones matter
        (self.ext / "SLOW").write_text("x", encoding="utf-8")
        report = mc.run_both(self.browser, self.ext, self.tmp / "work", timeout_s=60)
        self.assertGreater(report["with_extension"]["ad_requests"], 0)
        self.assertEqual(report["verdict"], "works", report)

    def test_extension_that_never_runs(self):
        (self.ext / "BROKEN").write_text("x", encoding="utf-8")
        report = mc.run_both(self.browser, self.ext, self.tmp / "work", timeout_s=60)
        self.assertEqual(report["verdict"], "fails", report)


if __name__ == "__main__":
    unittest.main()
