# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Release script (ROADMAP P2.12)."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.build import release_args as ra
from tools.release import release as rel

UPSTREAM_ARGS = 'target_os = "win"\nbundle_widevine_cdm = true\nenable_rlz = true\n'
GOOD_LIST = ["Chrome-bin/thoron.exe", "Chrome-bin/158.0.8127.3000/chrome.dll"]


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src, self.out, self.dist = root / "src", root / "src/out/rel", root / "dist"
        (self.src / "chrome").mkdir(parents=True)
        self.out.mkdir(parents=True)
        (self.src / "chrome/VERSION").write_text(
            "MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=3000\nTHORON_REBUILD=0\n", encoding="utf-8")
        (self.out / "args.gn").write_text(ra.compose(UPSTREAM_ARGS, "win", "test"), encoding="ascii")
        (self.out / "mini_installer.exe").write_bytes(b"installer bytes")
        (self.out / "chrome.7z").write_bytes(b"7z")
        self.buildinfo = root / "BUILDINFO.json"
        self.buildinfo.write_text('{"variant": "win-x64-avx2"}', encoding="utf-8")

    def cleanup(self):
        self.tmp.cleanup()


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def run_preflight(self, previous="156.0.8078.28", names=GOOD_LIST):
        return rel.preflight(self.f.src, self.f.out, "win", previous, lister=lambda archive: names)

    def test_clean_build_passes(self):
        version, problems = self.run_preflight()
        self.assertEqual(version, "158.0.8127.3000")
        self.assertEqual(problems, [])

    def test_version_not_set_is_refused(self):
        (self.f.src / "chrome/VERSION").write_text("MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=30\n", encoding="utf-8")
        _, problems = self.run_preflight()
        self.assertTrue([p for p in problems if "version.py set" in p])

    def test_version_must_be_higher_than_the_last_release(self):
        _, problems = self.run_preflight(previous="158.0.8127.3000")
        self.assertTrue([p for p in problems if "not higher" in p])

    def test_privacy_args_are_checked(self):
        (self.f.out / "args.gn").write_text(UPSTREAM_ARGS, encoding="ascii")
        _, problems = self.run_preflight()
        self.assertTrue([p for p in problems if "enable_rlz" in p])

    def test_package_audit_runs_on_the_installer_archive(self):
        _, problems = self.run_preflight(names=GOOD_LIST + ["Chrome-bin/thor_ver"])
        self.assertTrue([p for p in problems if "thor_ver" in p])


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def test_files_names_and_checksums(self):
        files = rel.assemble(self.f.out, self.f.dist, "158.0.8127.3000", "win-x64-avx2", self.f.buildinfo)
        names = sorted(p.name for p in files)
        self.assertEqual(names, ["BUILDINFO-158.0.8127.3000-win-x64-avx2.json", "SHA256SUMS",
                                 "thoron-158.0.8127.3000-win-x64-avx2-installer.exe"])
        sums = (self.f.dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        digest = hashlib.sha256(b"installer bytes").hexdigest()
        self.assertIn(f"{digest}  thoron-158.0.8127.3000-win-x64-avx2-installer.exe", sums)
        self.assertEqual(len(sums), 2)        # every file except SHA256SUMS itself

    def test_refuses_to_overwrite_an_existing_release_folder(self):
        rel.assemble(self.f.out, self.f.dist, "158.0.8127.3000", "win-x64-avx2", self.f.buildinfo)
        with self.assertRaises(rel.ReleaseError):
            rel.assemble(self.f.out, self.f.dist, "158.0.8127.3000", "win-x64-avx2", self.f.buildinfo)

    def test_variant_names_are_checked(self):
        with self.assertRaises(rel.ReleaseError):
            rel.assemble(self.f.out, self.f.dist, "158.0.8127.3000", "win x64; rm -rf", self.f.buildinfo)


class PublishTests(unittest.TestCase):
    def test_always_a_draft_and_never_unsigned(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            (dist / "SHA256SUMS").write_text("x  a\n", encoding="utf-8")
            (dist / "NOTES.md").write_text("# Thoron\n", encoding="utf-8")
            with self.assertRaisesRegex(rel.ReleaseError, "signature"):
                rel.publish(dist, "158.0.8127.3000", "KuchiSofts/thoron", run=calls.append)
            (dist / "SHA256SUMS.minisig").write_text("sig", encoding="utf-8")
            rel.publish(dist, "158.0.8127.3000", "KuchiSofts/thoron", run=calls.append)
        cmd = calls[-1]
        self.assertEqual(cmd[:3], ["gh", "release", "create"])
        self.assertIn("--draft", cmd)
        self.assertIn("v158.0.8127.3000", cmd)
        self.assertEqual(cmd[cmd.index("--repo") + 1], "KuchiSofts/thoron")


if __name__ == "__main__":
    unittest.main()
