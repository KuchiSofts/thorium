# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.audit.tests.gitfixture import GitRepo
from tools.build import buildinfo

KEYS = {"schema", "product", "variant", "chromium_version", "thoron_commit", "thoron_dirty", "upstream_ref",
        "depot_tools_commit", "gn_args_sha256", "gn_args", "toolchain", "host", "started_utc",
        "finished_utc", "duration_s"}


class BuildInfoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def make_src(self):
        src = self.tmp / "chromium" / "src"
        (src / "chrome").mkdir(parents=True)
        (src / "chrome" / "VERSION").write_text("MAJOR=156\nMINOR=0\nBUILD=8078\nPATCH=28\n", encoding="utf-8")
        return src

    def test_chromium_version_reads_VERSION_file(self):
        self.assertEqual(buildinfo.chromium_version(self.make_src()), "156.0.8078.28")

    def test_gn_args_digest_ignores_comments_and_order(self):
        a = "# comment\nis_official_build = true\n\nuse_avx2 = true  # inline\n"
        b = "use_avx2 = true\n# other comment\nis_official_build = true\n"
        c = "use_avx2 = false\nis_official_build = true\n"
        self.assertEqual(buildinfo.gn_args_digest(a), buildinfo.gn_args_digest(b))
        self.assertNotEqual(buildinfo.gn_args_digest(a), buildinfo.gn_args_digest(c))

    def test_redact_relativizes_and_hides_user_paths(self):
        self.assertEqual(buildinfo.redact("J:\\thoron-build\\chromium\\src", "J:\\thoron-build"),
                         "<build_root>/chromium/src")
        self.assertEqual(buildinfo.redact("C:\\Users\\Someone\\x", "J:\\thoron-build"), "<redacted>")  # privacy-check: allow
        self.assertEqual(buildinfo.redact("/home/someone/x", "/opt/b"), "<redacted>")  # privacy-check: allow
        self.assertEqual(buildinfo.redact("C:\\Program Files\\VS\\18", "J:\\thoron-build"), "C:\\Program Files\\VS\\18")

    def test_collect_has_schema_and_no_personal_paths(self):
        repo = GitRepo()
        try:
            repo.write("a.txt", b"x\n")
            repo.commit("init")
            info = buildinfo.collect(
                build_root=self.tmp, src=self.make_src(), thoron_repo=Path(repo.path),
                upstream_ref="gz83 M156.0.8078.28 de9a1bc6", variant="win-x64-avx2",
                args_text="is_official_build = true\n",
                toolchain={"vs": "C:\\Users\\Someone\\VS", "sdk": "10.0.28000.0"},  # privacy-check: allow
                started=1_700_000_000.0, finished=1_700_003_600.5)
        finally:
            repo.cleanup()
        self.assertEqual(set(info), KEYS)
        self.assertEqual(info["schema"], 1)
        self.assertEqual(info["product"], "Thoron")
        self.assertEqual(info["chromium_version"], "156.0.8078.28")
        self.assertEqual(info["duration_s"], 3600)
        self.assertTrue(info["started_utc"].endswith("Z"))
        dumped = json.dumps(info)
        self.assertNotIn("Someone", dumped)
        self.assertNotIn(str(self.tmp).replace("\\", "\\\\"), dumped)

    def test_paths_anywhere_in_any_string_are_scrubbed(self):
        args = ('pgo_data_path = "C:/Users/Someone/pgo/chrome.profdata"\n'          # privacy-check: allow
                f'extra_dir = "{self.tmp.as_posix()}/chromium/extra"\n')
        toolchain = {"vs": {"note": "InstalledDir: C:\\Users\\Someone\\VS"},        # privacy-check: allow
                     "paths": ["/home/someone/sdk", "ok"]}                          # privacy-check: allow
        info = buildinfo.collect(build_root=self.tmp, src=self.make_src(), thoron_repo=self.tmp,
                                 upstream_ref="x", variant="v", args_text=args, toolchain=toolchain,
                                 started=1.0, finished=2.0)
        dumped = json.dumps(info)
        self.assertNotIn("omeone", dumped)
        self.assertNotIn(self.tmp.as_posix(), dumped)
        self.assertIn("<build_root>/chromium/extra", dumped)
        self.assertEqual(info["gn_args_sha256"], buildinfo.gn_args_digest(args))   # digest of the real args

    def test_write_refuses_a_personal_path(self):
        out = self.tmp / "BUILDINFO.json"
        with self.assertRaises(ValueError):
            buildinfo.write(out, {"note": "copied from C:\\Users\\Someone\\x"})       # privacy-check: allow
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
