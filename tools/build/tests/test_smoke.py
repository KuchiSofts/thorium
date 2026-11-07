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


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.shim = make_shim(self.tmp)
        self.log = self.tmp / "argv.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_mode(self, mode):
        with mock.patch.dict(os.environ, {"FAKE_MODE": mode, "FAKE_ARGV_LOG": str(self.log)}):
            return smoke.run_smoke(self.shim, self.tmp / "work", timeout_s=60)

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
