# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.build import smoke

FAKE = Path(__file__).with_name("fake_browser.py")


def make_shim(directory: Path) -> Path:
    """An executable that runs fake_browser.py, so run_smoke can treat it as a browser binary."""
    if os.name == "nt":
        shim = directory / "fake-browser.cmd"
        shim.write_text(f'@"{sys.executable}" -I "{FAKE}" %*\r\n', encoding="utf-8")
    else:
        shim = directory / "fake-browser"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{FAKE}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
    return shim


class SandboxReportTests(unittest.TestCase):
    BROWSER = {"pid": 1, "ppid": 0, "cmd": "thorium.exe --headless=new"}

    def report(self, children, levels):
        procs = [self.BROWSER] + children
        return smoke.sandbox_report(1, lambda: procs, lambda pid: levels.get(pid))

    def test_low_or_untrusted_renderers_pass(self):
        kids = [{"pid": 2, "ppid": 1, "cmd": "thorium.exe --type=renderer"},
                {"pid": 3, "ppid": 1, "cmd": "thorium.exe --type=gpu-process"},
                {"pid": 4, "ppid": 2, "cmd": "thorium.exe --type=renderer"}]
        self.assertEqual(self.report(kids, {2: 0x0000, 4: 0x1000, 3: 0x2000}), [])

    def test_medium_integrity_renderer_fails(self):
        kids = [{"pid": 2, "ppid": 1, "cmd": "thorium.exe --type=renderer"}]
        problems = self.report(kids, {2: 0x2000})
        self.assertEqual(len(problems), 1)
        self.assertIn("Medium", problems[0])

    def test_no_sandbox_switch_in_any_child_fails(self):
        kids = [{"pid": 2, "ppid": 1, "cmd": "thorium.exe --type=renderer"},
                {"pid": 3, "ppid": 1, "cmd": "thorium.exe --type=utility --no-sandbox"}]
        self.assertTrue(any("--no-sandbox" in p for p in self.report(kids, {2: 0})))

    def test_unknown_level_or_no_renderer_fails(self):
        self.assertTrue(self.report([], {}))
        kids = [{"pid": 2, "ppid": 1, "cmd": "thorium.exe --type=renderer"}]
        self.assertTrue(self.report(kids, {}))

    def test_processes_of_other_programs_are_ignored(self):
        kids = [{"pid": 2, "ppid": 1, "cmd": "thorium.exe --type=renderer"},
                {"pid": 9, "ppid": 77, "cmd": "other.exe --type=renderer --no-sandbox"}]
        self.assertEqual(self.report(kids, {2: 0}), [])

    @unittest.skipUnless(os.name == "nt", "Windows token query")
    def test_integrity_of_this_process_is_medium_or_high(self):
        self.assertIn(smoke._integrity_rid(os.getpid()), (0x2000, 0x3000))


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.shim = make_shim(self.tmp)
        self.log = self.tmp / "argv.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_mode(self, mode, sandbox_check=lambda *a, **k: []):
        with mock.patch.dict(os.environ, {"FAKE_MODE": mode, "FAKE_ARGV_LOG": str(self.log)}):
            return smoke.run_smoke(self.shim, self.tmp / "work", timeout_s=60, sandbox_check=sandbox_check)

    def logged(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()]

    def test_ok_build_passes(self):
        result = self.run_mode("ok")
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["exit_code"], 0)

    def test_crash_dump_fails(self):
        result = self.run_mode("crash")
        self.assertFalse(result["passed"])
        self.assertTrue(any("crash" in f for f in result["failures"]))

    def test_nonzero_exit_fails(self):
        self.assertFalse(self.run_mode("exit1")["passed"])

    def test_missing_capability_fails(self):
        result = self.run_mode("missing")
        self.assertFalse(result["passed"])
        self.assertTrue(any("jxl" in f for f in result["failures"]))

    def test_page_that_never_ran_fails(self):
        # the page script did not run (e.g. JavaScript broken): the result stays empty or is not an object
        for mode in ("empty", "null", "list"):
            result = self.run_mode(mode)
            self.assertFalse(result["passed"], mode)
            self.assertTrue(result["failures"], mode)

    def test_sandbox_failure_fails_the_smoke_test(self):
        result = self.run_mode("ok", sandbox_check=lambda *a, **k: ["renderer 42 runs at Medium integrity"])
        self.assertFalse(result["passed"])
        self.assertIn("renderer 42 runs at Medium integrity", result["failures"])

    def test_never_passes_no_sandbox(self):
        result = self.run_mode("nosandbox")
        self.assertTrue(result["passed"], result["failures"])
        self.assertNotIn("--no-sandbox", self.logged()[0]["argv"])

    def test_fresh_profile_each_run(self):
        self.run_mode("ok")
        self.run_mode("ok")
        first, second = self.logged()
        self.assertNotEqual(first["profile"], second["profile"])
        self.assertEqual(first["profile_initial"], [])
        self.assertEqual(second["profile_initial"], [])


if __name__ == "__main__":
    unittest.main()
