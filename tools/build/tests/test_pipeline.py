# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import shutil
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

from tools.build import pipeline

Usage = namedtuple("Usage", "total used free")
GB = 1024 ** 3


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.clean_drive = self.tmp / "drive"          # stands in for a drive root without .bzvol
        self.clean_drive.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def preflight(self, root, need=0, **kw):
        with mock.patch.object(pipeline, "_drive_root", return_value=self.clean_drive), \
                mock.patch.object(pipeline, "_volume_label", return_value="Build SSD"):
            return pipeline.preflight(root, need, **kw)

    def test_preflight_flags_cloud_path_and_spaces(self):
        problems = self.preflight(self.tmp / "Google Drive" / "my build")
        self.assertGreaterEqual(len(problems), 2, problems)
        self.assertEqual(self.preflight(self.tmp / "thoron-build"), [])

    def test_preflight_warns_on_backblaze_drive(self):
        (self.clean_drive / ".bzvol").mkdir()
        problems = self.preflight(self.tmp / "thoron-build")
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("warning:"))

    def test_preflight_flags_low_disk(self):
        with mock.patch.object(pipeline.shutil, "disk_usage", return_value=Usage(1000 * GB, 900 * GB, 100 * GB)):
            problems = self.preflight(self.tmp / "thoron-build", need=250)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("250", problems[0])

    def test_preflight_checks_wsl_memory_when_required(self):
        with mock.patch.object(pipeline, "_mem_total_gb", return_value=23.5):
            problems = self.preflight(self.tmp / "thoron-build", require_wsl_limits={"memory_gb": 44})
        self.assertEqual(len(problems), 1, problems)

    def test_find_rejects_lists_rej_files_but_skips_out_and_git(self):
        src = self.tmp / "src"
        for rel in ("a/b.rej", "c/d/e.rej", "out/x/f.rej", ".git/g.rej", "a/ok.cc"):
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text("x", encoding="utf-8")
        self.assertEqual(pipeline.find_rejects(src), ["a/b.rej", "c/d/e.rej"])

    def test_apply_upstream_raises_with_rejects(self):
        tree, src = self.tmp / "upstream", self.tmp / "src"
        tree.mkdir()
        src.mkdir()
        (tree / "setup.py").write_text(
            "import sys, pathlib\n"
            "a = sys.argv\n"
            "src = pathlib.Path(a[a.index('--chromium-src') + 1])\n"
            "(src / 'a').mkdir(parents=True, exist_ok=True)\n"
            "(src / 'a' / 'b.rej').write_text('rejected hunk')\n", encoding="utf-8")
        log = self.tmp / "logs" / "apply.log"
        with self.assertRaises(RuntimeError) as ctx:
            pipeline.apply_upstream(tree, src, "avx2", log=log)
        self.assertIn("a/b.rej", str(ctx.exception))
        self.assertTrue(log.is_file(), "the log is kept when setup fails too")

    def test_apply_upstream_writes_full_log(self):
        tree, src = self.tmp / "upstream", self.tmp / "src"
        tree.mkdir()
        src.mkdir()
        (tree / "setup.py").write_text(
            "import sys\n"
            "print('copied overlay')\n"
            "print('patch series ok', file=sys.stderr)\n", encoding="utf-8")
        log = self.tmp / "logs" / "apply.log"
        pipeline.apply_upstream(tree, src, "avx2", log=log)
        text = log.read_text(encoding="utf-8")
        self.assertIn("copied overlay", text)
        self.assertIn("patch series ok", text)
        self.assertIn("--avx2", text)                    # the exact command is recorded


if __name__ == "__main__":
    unittest.main()
