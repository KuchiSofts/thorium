# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.migrate import import_profile as ip


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.src = self.tmp / "Thorium" / "User Data"
        (self.src / "Default" / "Sessions").mkdir(parents=True)
        (self.src / "Local State").write_text('{"os_crypt": {"encrypted_key": "k"}}', encoding="utf-8")
        (self.src / "Default" / "Login Data").write_bytes(b"\x00sqlite-ish" * 100)
        (self.src / "Default" / "Sessions" / "Session_1").write_bytes(b"SNSS" + b"\x03\x00\x00\x00")
        self.dst = self.tmp / "Thoron" / "User Data"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def snapshot(self, root: Path) -> dict:
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_copies_every_file_and_verifies(self):
        before = self.snapshot(self.src)
        report = ip.import_profile(self.src, self.dst)
        self.assertEqual(self.snapshot(self.dst), before)
        self.assertEqual(self.snapshot(self.src), before)             # the source is never changed
        self.assertEqual(report["files"], len(before))
        self.assertTrue(report["verified"])

    def test_accepts_a_fresh_install_folder_with_only_crashpad(self):
        (self.dst / "Crashpad").mkdir(parents=True)
        ip.import_profile(self.src, self.dst)
        self.assertTrue((self.dst / "Local State").is_file())

    def test_refuses_a_destination_that_already_has_a_profile(self):
        self.dst.mkdir(parents=True)
        (self.dst / "Local State").write_text("{}", encoding="utf-8")
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src, self.dst)
        self.assertEqual((self.dst / "Local State").read_text(encoding="utf-8"), "{}")

    def test_refuses_while_either_browser_runs(self):
        (self.src / "lockfile").write_bytes(b"")
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src, self.dst)
        (self.src / "lockfile").unlink()
        (self.dst).mkdir(parents=True)
        (self.dst / "lockfile").write_bytes(b"")
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src, self.dst)

    def test_refuses_a_source_that_is_not_user_data(self):
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src.parent, self.dst)

    def test_refuses_copying_into_the_source(self):
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src, self.src / "Default")

    def test_verification_failure_is_reported(self):
        original = ip._sha256
        calls = {"n": 0}

        def flaky(path):
            calls["n"] += 1
            return "bad" if calls["n"] == 2 else original(path)        # second hash (a copy) differs
        ip._sha256 = flaky
        try:
            with self.assertRaises(ip.VerificationFailed):
                ip.import_profile(self.src, self.dst)
        finally:
            ip._sha256 = original

    def test_unreadable_folder_stops_the_import(self):
        original = ip._walk_entries

        def denied(root):
            for item in original(root):
                yield item
            raise PermissionError("listing denied")
        ip._walk_entries = denied
        try:
            with self.assertRaises(ip.ImportRefused):
                ip.import_profile(self.src, self.dst)
        finally:
            ip._walk_entries = original

    def test_refuses_junctions_and_links(self):
        target = self.tmp / "elsewhere"
        target.mkdir()
        (target / "x.txt").write_text("outside", encoding="utf-8")
        link = self.src / "Default" / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            import subprocess
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True).returncode:
                self.skipTest("cannot create a link here")
        with self.assertRaises(ip.ImportRefused):
            ip.import_profile(self.src, self.dst)

    def test_browser_started_during_copy_fails(self):
        original = ip._sha256

        def start_browser(path):
            (self.src / "lockfile").write_bytes(b"")
            return original(path)
        ip._sha256 = start_browser
        try:
            with self.assertRaises(ip.ImportRefused):
                ip.import_profile(self.src, self.dst)
        finally:
            ip._sha256 = original

    def test_cli(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ip.main(["--from", str(self.src), "--to", str(self.dst)]), 0)
        self.assertIn("verified", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ip.main(["--from", str(self.src), "--to", str(self.dst)]), 1)   # now refused


if __name__ == "__main__":
    unittest.main()
