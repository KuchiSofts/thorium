# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Vendoring Thoron's Rust crates with Chromium's gnrt on Windows (ROADMAP P5.14)."""
import unittest
from pathlib import Path

from tools.build import rust_crates as rc


class ApplyArgsTests(unittest.TestCase):
    def test_forward_slashes_and_strip_count(self):
        args = rc.git_apply_args("third_party/rust/chromium_crates_io/vendor/seahash-v4")
        # gnrt passes this path with backslashes on Windows, which git rejects as invalid
        self.assertEqual(args, ["apply", "-p6", "--directory=third_party/rust/chromium_crates_io/vendor/seahash-v4"])

    def test_backslashes_are_normalised(self):
        args = rc.git_apply_args(r"third_party\rust\chromium_crates_io\vendor\flatbuffers-v25")
        self.assertEqual(args[2], "--directory=third_party/rust/chromium_crates_io/vendor/flatbuffers-v25")


class PlanTests(unittest.TestCase):
    def test_our_crate_patches_are_listed_by_epoch_dir(self):
        self.assertEqual(rc.PATCHED_CRATES, ("seahash-v4", "flatbuffers-v25"))

    def test_files_gnrt_rewrites_by_mistake_are_restored(self):
        self.assertIn("third_party/rust/zune_jpeg/v0_5/README.chromium", rc.RESTORE_AFTER_GEN)

    def test_vendor_command_skips_our_patches(self):
        cmd = rc.vendor_args()
        self.assertEqual(cmd[0], "vendor")
        self.assertIn("--no-patches=seahash-v4", cmd)
        self.assertIn("--no-patches=flatbuffers-v25", cmd)



class EnvTests(unittest.TestCase):
    def test_gn_and_the_rust_toolchain_are_on_the_path(self):
        # without gn, gnrt cannot format the BUILD.gn files and every crate's file changes
        env = rc._env(Path("src"))
        first = env["PATH"].split(rc.os.pathsep)[:2]
        self.assertIn(str(Path("src") / "third_party" / "rust-toolchain" / "bin"), first)
        self.assertTrue(any(p.startswith(str(Path("src") / "buildtools")) for p in first), first)

class FormatTests(unittest.TestCase):
    def test_only_rust_build_files_with_forward_slashes(self):
        porcelain = (" M third_party/rust/litemap/v0_8/BUILD.gn\n"
                     "?? third_party/rust/adblock/v0_13/BUILD.gn\n"
                     " M third_party/rust/regex/v1/README.chromium\n"
                     " M chrome/BUILD.gn\n")
        self.assertEqual(rc.changed_rust_build_files(porcelain),
                         ["third_party/rust/adblock/v0_13/BUILD.gn", "third_party/rust/litemap/v0_8/BUILD.gn"])


if __name__ == "__main__":
    unittest.main()
