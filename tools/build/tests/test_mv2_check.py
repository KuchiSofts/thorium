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
        rules = next(a for a in args if a.startswith("--host-resolver-rules="))
        self.assertIn(f"MAP {mc.AD_HOST} 127.0.0.1:4321", rules)
        self.assertIn("MAP * ~NOTFOUND", rules)                 # offline: no other host resolves
        self.assertIn("EXCLUDE 127.0.0.1", rules)
        self.assertIn("--disable-background-networking", args)
        self.assertIn("--disable-component-update", args)
        self.assertIn("--load-extension=ext", args)
        self.assertEqual(args[-1], "http://127.0.0.1:4321/test.html")
        self.assertFalse(any(a.startswith("--load-extension") for a in
                             mc.browser_args(Path("b.exe"), Path("prof"), 1, None, "u")))

    def test_headed_args_open_a_real_window_off_screen(self):
        args = mc.browser_args(Path("b.exe"), Path("prof"), 1, Path("ext"), "u", headed=True)
        self.assertNotIn("--headless=new", args)
        self.assertNotIn("--dump-dom", args)
        self.assertIn("--window-position=-32000,-32000", args)
        self.assertNotIn("--no-sandbox", args)
        self.assertEqual(args[-1], "u")

    def test_bundled_mode_lets_the_browser_install_its_own_ublock(self):
        args = mc.browser_args(Path("b.exe"), Path("prof"), 1, None, "u", headed=True, bundled=True)
        self.assertNotIn("--disable-default-apps", args)          # the built-in uBlock Origin installs itself
        self.assertFalse(any(a.startswith("--load-extension") for a in args))
        control = mc.browser_args(Path("b.exe"), Path("prof"), 1, None, "u", headed=True)
        self.assertIn("--disable-default-apps", control)          # the control run has no blocker

    def test_page_posts_its_result_to_the_local_server(self):
        self.assertIn("fetch('/result'", mc.PAGE)
        with mc.TestServer(Path(tempfile.gettempdir())) as server:
            req = urllib.request.Request(f"http://127.0.0.1:{server.port}/result", method="POST",
                                         data=b'{"attempts": 10, "frame": true}')
            urllib.request.urlopen(req).read()
            self.assertEqual(server.posted, {"attempts": 10, "frame": True})
            big = urllib.request.Request(f"http://127.0.0.1:{server.port}/result", method="POST", data=b"x" * 70000)
            with self.assertRaises(Exception):
                urllib.request.urlopen(big).read()                  # oversized bodies are refused
            self.assertEqual(server.posted, {"attempts": 10, "frame": True})

    def test_parse_result(self):
        dom = '<html><pre id="thoron-mv2-result">{"attempts": 4, "loaded": 0, "ad_element_hidden": true}</pre>'
        self.assertEqual(mc.parse_result(dom), {"attempts": 4, "loaded": 0, "ad_element_hidden": True})
        self.assertIsNone(mc.parse_result("<html>no result</html>"))

    def test_server_counts_ad_requests_only(self):
        with mc.TestServer(Path(tempfile.gettempdir())) as server:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/pagead/js/adsbygoogle.js?n=1").read()
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/test.html").read()
            self.assertEqual(server.ad_requests, 1)


def run(hits, late, loaded=0, stand_ins=0, errors=0, attempts=None, hidden=False, frame=True):
    attempts = mc.ATTEMPTS if attempts is None else attempts
    return {"ok": True, "ad_requests": hits, "late_ad_requests": late,
            "page": {"attempts": attempts, "loaded": loaded, "stand_ins": stand_ins, "errors": errors,
                     "frame": frame, "ad_element_hidden": hidden}}


CONTROL = run(hits=mc.ATTEMPTS, late=mc.LATE_ATTEMPTS, loaded=mc.ATTEMPTS)


class VerdictTests(unittest.TestCase):
    def test_works_when_both_kinds_of_blocking_happen(self):
        blocked = run(hits=3, late=0, loaded=3, stand_ins=mc.ATTEMPTS - 3, hidden=True)
        self.assertEqual(mc.verdict(CONTROL, blocked)[0], "works")

    def test_fails_when_extension_changes_nothing(self):
        self.assertEqual(mc.verdict(CONTROL, dict(CONTROL))[0], "fails")

    def test_partial_when_only_one_kind_of_blocking_happens(self):
        cosmetic_only = run(hits=mc.ATTEMPTS, late=mc.LATE_ATTEMPTS, loaded=mc.ATTEMPTS, hidden=True)
        self.assertEqual(mc.verdict(CONTROL, cosmetic_only)[0], "partial")

    def test_invalid_when_control_shows_no_ads(self):
        bad_control = run(hits=0, late=0, errors=mc.ATTEMPTS)
        self.assertEqual(mc.verdict(bad_control, bad_control)[0], "invalid")

    def test_invalid_when_a_run_failed(self):
        self.assertEqual(mc.verdict({"ok": False, "error": "timeout"}, CONTROL)[0], "invalid")

    def test_invalid_when_the_page_stopped_early(self):
        # same traffic as the control but the page made only 4 attempts: no late hits, yet nothing was blocked
        stopped = run(hits=4, late=0, loaded=4, attempts=4)
        self.assertEqual(mc.verdict(CONTROL, stopped)[0], "invalid")

    def test_invalid_when_attempts_did_not_finish(self):
        unfinished = run(hits=0, late=0)                    # 10 attempts, none loaded, none failed
        self.assertEqual(mc.verdict(CONTROL, unfinished)[0], "invalid")

    def test_invalid_when_the_control_was_blocked_late(self):
        contaminated = run(hits=7, late=0, loaded=7, stand_ins=3)   # e.g. a blocker installed by default apps
        self.assertEqual(mc.verdict(contaminated, run(hits=0, late=0, errors=mc.ATTEMPTS, hidden=True))[0], "invalid")

    def test_invalid_when_the_ad_frame_was_never_checked(self):
        no_frame = run(hits=mc.ATTEMPTS, late=mc.LATE_ATTEMPTS, loaded=mc.ATTEMPTS, frame=False)
        self.assertEqual(mc.verdict(no_frame, run(hits=0, late=0, errors=mc.ATTEMPTS, hidden=True))[0], "invalid")


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
