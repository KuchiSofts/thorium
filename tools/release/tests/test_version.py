# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron's version numbers (ROADMAP P2.14)."""
import tempfile
import unittest
from pathlib import Path

from tools.release import version as v

VERSION_FILE = "MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=30\n"


class SchemeTests(unittest.TestCase):
    def test_first_build_and_rebuilds(self):
        self.assertEqual(v.thoron_version("158.0.8127.30", 0), "158.0.8127.3000")
        self.assertEqual(v.thoron_version("158.0.8127.30", 1), "158.0.8127.3001")
        self.assertEqual(v.thoron_version("158.0.8127.30", 99), "158.0.8127.3099")

    def test_chromium_version_comes_back(self):
        self.assertEqual(v.split("158.0.8127.3001"), ("158.0.8127.30", 1))
        self.assertEqual(v.split("158.0.8127.0"), ("158.0.8127.0", 0))

    def test_order_newer_chromium_beats_every_rebuild(self):
        rebuild = v.thoron_version("158.0.8127.30", 99)
        next_chromium = v.thoron_version("158.0.8127.45", 0)
        self.assertLess(v.key(rebuild), v.key(next_chromium))
        self.assertLess(v.key(v.thoron_version("158.0.8127.30", 1)), v.key(rebuild))
        self.assertLess(v.key(v.thoron_version("158.0.8127.300", 5)), v.key(v.thoron_version("159.0.8200.1", 0)))

    def test_fits_the_windows_version_resource(self):
        self.assertEqual(v.thoron_version("158.0.8127.655", 35), "158.0.8127.65535")
        with self.assertRaisesRegex(v.VersionError, "65535"):
            v.thoron_version("158.0.8127.656", 0)

    def test_rebuild_range(self):
        for bad in (-1, 100):
            with self.assertRaises(v.VersionError):
                v.thoron_version("158.0.8127.30", bad)

    def test_rejects_malformed_versions(self):
        for bad in ("158.0.8127", "158.0.8127.30.1", "158.a.8127.30", "158.0.8127.-1", ""):
            with self.assertRaises(v.VersionError, msg=bad):
                v.key(bad)


class CheckNewTests(unittest.TestCase):
    def test_new_release_must_be_higher(self):
        self.assertEqual(v.check_new("158.0.8127.3001", "158.0.8127.3000"), [])
        self.assertTrue(v.check_new("158.0.8127.3000", "158.0.8127.3000"))
        self.assertTrue(v.check_new("158.0.8127.2999", "158.0.8127.3000"))

    def test_plain_chromium_numbers_of_the_old_scheme_are_older(self):
        # The owner's Thoron 156 install (P2.20) carries the plain Chromium number.
        self.assertEqual(v.check_new("156.0.8078.2801", "156.0.8078.28"), [])
        self.assertEqual(v.check_new("158.0.8127.3000", "156.0.8078.28"), [])


class VersionFileTests(unittest.TestCase):
    def test_set_rewrites_only_patch_and_is_idempotent(self):
        out = v.set_version_file(VERSION_FILE, 1)
        self.assertEqual(out, "MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=3001\nTHORON_REBUILD=1\n")
        self.assertEqual(v.set_version_file(VERSION_FILE.replace("\n", "\r\n"), 1).count("\r\n"), 5)
        with self.assertRaisesRegex(v.VersionError, "already"):
            v.set_version_file(out, 2)        # never encode twice

    def test_cli_set_and_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            (src / "chrome").mkdir()
            (src / "chrome" / "VERSION").write_text(VERSION_FILE, encoding="utf-8")
            self.assertEqual(v.main(["set", "--src", str(src), "--rebuild", "2"]), 0)
            self.assertIn("PATCH=3002", (src / "chrome" / "VERSION").read_text(encoding="utf-8"))
            self.assertEqual(v.main(["check", "--new", "158.0.8127.3002", "--previous", "158.0.8127.3002"]), 1)


if __name__ == "__main__":
    unittest.main()
