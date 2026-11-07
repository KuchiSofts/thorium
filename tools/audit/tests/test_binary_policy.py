# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import hashlib
import io
import unittest
from pathlib import Path

from tools.audit import binary_policy as bp
from tools.audit.tests.gitfixture import GitRepo

PE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 56
ELF = b"\x7fELF\x02\x01\x01" + b"\x00" * 9
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def entry(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "license": "MIT", "source": "built from pak_src"}


class ClassifyTests(unittest.TestCase):
    def test_detects_executables_and_packages_by_content(self):
        self.assertEqual(bp.classify(PE), "PE executable")
        self.assertEqual(bp.classify(ELF), "ELF binary")
        self.assertEqual(bp.classify(b"\xcf\xfa\xed\xfe" + b"\x00" * 12), "Mach-O binary")
        self.assertEqual(bp.classify(b"!<arch>\ndebian-binary   "), "ar archive")
        self.assertEqual(bp.classify(b"Cr24\x03\x00\x00\x00"), "CRX package")
        self.assertEqual(bp.classify(b"PK\x03\x04\x14\x00"), "zip archive")
        self.assertEqual(bp.classify(b"BZh91AY&SY\x00"), "bzip2 archive")

    def test_ignores_text_images_and_lookalikes(self):
        self.assertIsNone(bp.classify(b"# Title\n"))
        self.assertIsNone(bp.classify(PNG))
        self.assertIsNone(bp.classify(b""))
        self.assertIsNone(bp.classify(b"MZ is a text line, not an executable\n"))
        self.assertIsNone(bp.classify(b"BZh is just text\n"))

    def test_proprietary_blobs_are_named(self):
        for path in ("src/third_party/widevine/cdm/win/x64/widevinecdm.dll",
                     "src/third_party/widevine/cdm/win/x64/widevinecdm.dll.lib",
                     "src/third_party/widevine/cdm/win/x64/widevinecdm.dll.sig",
                     "arm/raspi/libwidevinecdm_patched.so",
                     "src/third_party/widevine/cdm/mac/x64/libwidevinecdm.dylib",
                     "infra/libpepflashplayer.so"):
            self.assertIsNotNone(bp.forbidden_reason(path), path)
        for path in ("src/third_party/widevine/cdm/widevine.gni",
                     "src/third_party/widevine/cdm/linux/x64/widevine_cdm_version.h",
                     "arm/raspi/widevine_fixup.py"):
            self.assertIsNone(bp.forbidden_reason(path), path)


class AllowlistTests(unittest.TestCase):
    def test_load_allowlist(self):
        sha = "a" * 64
        allow = bp.load_allowlist(f"# comment\n\n{sha}\tbin/pak\tMIT\tbuilt from pak_src\n")
        self.assertEqual(allow, {"bin/pak": {"sha256": sha, "license": "MIT", "source": "built from pak_src"}})

    def test_malformed_allowlist_line_is_an_error(self):
        with self.assertRaises(ValueError):
            bp.load_allowlist("not-a-hash\tbin/pak\tMIT\tsource\n")
        with self.assertRaises(ValueError):
            bp.load_allowlist("a" * 64 + "\tbin/pak\tMIT\n")


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo()
        self.root = Path(self.repo.path)

    def tearDown(self):
        self.repo.cleanup()

    def test_unlisted_binary_is_a_problem_even_when_renamed(self):
        self.repo.write("tools/helper.txt", PE)
        self.repo.write("README.md", b"hello\n")
        self.repo.write("logo.png", PNG)
        self.repo.commit("x")
        problems = bp.check(self.root, {})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("tools/helper.txt", problems[0])
        self.assertIn("PE executable", problems[0])

    def test_allowlisted_binary_passes_until_it_changes(self):
        self.repo.write("bin/pak", ELF)
        self.repo.commit("x")
        allow = {"bin/pak": entry(ELF)}
        self.assertEqual(bp.check(self.root, allow), [])
        self.repo.write("bin/pak", ELF + b"tampered")
        self.repo.commit("y")
        problems = bp.check(self.root, allow)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("changed", problems[0])

    def test_proprietary_blob_fails_even_when_allowlisted(self):
        path = "third_party/widevine/cdm/win/x64/widevinecdm.dll"
        self.repo.write(path, PE)
        self.repo.commit("x")
        problems = bp.check(self.root, {path: entry(PE)})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("never allowed", problems[0])

    def test_stale_allowlist_entry_is_reported(self):
        self.repo.write("README.md", b"hello\n")
        self.repo.commit("x")
        problems = bp.check(self.root, {"gone.exe": entry(PE)})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("gone.exe", problems[0])

    def test_untracked_files_are_ignored(self):
        self.repo.write("README.md", b"hello\n")
        self.repo.commit("x")
        self.repo.write("out/build.exe", PE)          # build output, never committed
        self.assertEqual(bp.check(self.root, {}), [])

    def test_main_exit_codes(self):
        self.repo.write("bin/pak", ELF)
        self.repo.commit("x")
        allowlist = self.root / "allow.txt"
        args = ["--root", str(self.root), "--allowlist", str(allowlist)]
        allowlist.write_text("", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bp.main(args), 1)
        allowlist.write_text(f"{entry(ELF)['sha256']}\tbin/pak\tMIT\tbuilt from pak_src\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bp.main(args), 0)


if __name__ == "__main__":
    unittest.main()
