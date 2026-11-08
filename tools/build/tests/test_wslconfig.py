# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.build import wslconfig

HEBREW = "".join(chr(c) for c in (0x5D4, 0x2D, 0x5D5, 0x5D0, 0x20, 0x5DC, 0x5D0))  # a short Hebrew comment
ORIGINAL = ("[wsl2]\r\n# " + HEBREW + "\r\nvmIdleTimeout=2000000000\r\nmemory=24GB\r\nswap=8GB\r\n\r\n"
            "[experimental]\r\nautoMemoryReclaim=dropCache\r\n").encode("utf-8")
SWAP_FILE_LINE = b"swapFile=J:\\\\thoron-build\\\\wsl\\\\swap.vhdx"


class WslConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.cfg = self.tmp / ".wslconfig"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_raise_then_restore_is_byte_exact(self):
        self.cfg.write_bytes(ORIGINAL)
        backup = wslconfig.raise_limits(self.cfg)
        raised = self.cfg.read_bytes()
        self.assertIn(b"memory=48GB\r\n", raised)
        self.assertIn(b"swap=32GB\r\n", raised)
        self.assertNotIn(b"memory=24GB", raised)
        for kept in (b"# " + HEBREW.encode("utf-8") + b"\r\n", b"vmIdleTimeout=2000000000\r\n",
                     b"[experimental]\r\nautoMemoryReclaim=dropCache\r\n"):
            self.assertIn(kept, raised)
        wslconfig.restore(self.cfg, backup)
        self.assertEqual(self.cfg.read_bytes(), ORIGINAL)
        self.assertFalse(backup.exists())

    def test_restore_refuses_anything_but_a_thoron_backup_of_this_file(self):
        self.cfg.write_bytes(ORIGINAL)
        other = self.tmp / "sub"
        other.mkdir()
        (other / ".wslconfig.thoron-backup-20261108T010203").write_bytes(b"x")
        (self.tmp / "notes.txt").write_bytes(b"x")
        for bad in (self.cfg, self.tmp / "notes.txt", other / ".wslconfig.thoron-backup-20261108T010203"):
            with self.assertRaises(ValueError, msg=str(bad)):
                wslconfig.restore(self.cfg, bad)
        self.assertEqual(self.cfg.read_bytes(), ORIGINAL)            # nothing changed, nothing deleted

    def test_second_raise_is_refused_and_the_first_backup_kept(self):
        self.cfg.write_bytes(ORIGINAL)
        backup = wslconfig.raise_limits(self.cfg)
        with self.assertRaises(FileExistsError):
            wslconfig.raise_limits(self.cfg)
        self.assertEqual(backup.read_bytes(), ORIGINAL)
        wslconfig.restore(self.cfg, backup)
        self.assertEqual(self.cfg.read_bytes(), ORIGINAL)

    def test_raise_adds_missing_keys_and_section(self):
        self.cfg.write_bytes(b"[experimental]\nautoMemoryReclaim=dropCache\n")
        wslconfig.raise_limits(self.cfg)
        limits = wslconfig.current_limits(self.cfg)
        self.assertEqual((limits.get("memory"), limits.get("swap")), ("48GB", "32GB"))
        self.assertIn(b"[experimental]\nautoMemoryReclaim=dropCache\n", self.cfg.read_bytes())

    def test_raise_without_file_then_restore_removes_it(self):
        backup = wslconfig.raise_limits(self.cfg)
        self.assertTrue(self.cfg.exists())
        wslconfig.restore(self.cfg, backup)
        self.assertFalse(self.cfg.exists())
        self.assertFalse(backup.exists())

    def test_swap_file_set_on_build_drive_and_restored(self):
        self.cfg.write_bytes(ORIGINAL)
        backup = wslconfig.raise_limits(self.cfg)
        self.assertIn(SWAP_FILE_LINE, self.cfg.read_bytes())
        wslconfig.restore(self.cfg, backup)
        self.assertNotIn(b"swapFile", self.cfg.read_bytes())

    def test_main_never_shuts_down_wsl(self):
        self.cfg.write_bytes(ORIGINAL)

        def forbidden(*args, **kwargs):
            raise AssertionError(f"tool tried to run a process: {args}")
        out = io.StringIO()
        with mock.patch.object(subprocess, "run", forbidden), mock.patch.object(subprocess, "Popen", forbidden), \
                contextlib.redirect_stdout(out):
            self.assertEqual(wslconfig.main(["raise", "--path", str(self.cfg)]), 0)
        self.assertIn("wsl --shutdown", out.getvalue())   # tells the owner, never runs it


if __name__ == "__main__":
    unittest.main()
