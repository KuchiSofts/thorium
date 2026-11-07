# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.legal import patch_licenses as pl

CREDITS = """| Project | Link | Licence of the project |
|---|---|---|
| Bromite | https://github.com/bromite/bromite | GPL-3.0 |
| enable-chromium-hevc-hardware-decoding (StaZhu) | https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding | MIT |
| Debian Chromium packaging | https://salsa.debian.org/chromium-team/chromium | see licence inventory (ROADMAP **L.1**) |
"""
PATCHES_MD = """| Patch | Source |
|---|---|
| [`bromite-thing.patch`](../other/bromite-thing.patch) | From [Bromite](https://github.com/bromite/bromite) flags work |
| [`hevc.patch`](../other/hevc.patch) | [StaZhu/enable-chromium-hevc-hardware-decoding](https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding) HEVC |
| [`debian-fix.patch`](../other/debian-fix.patch) | Debian packaging fix from https://salsa.debian.org/chromium-team/chromium |
| [`mystery.patch`](../other/mystery.patch) | does something useful |
"""


class PatchLicenseTests(unittest.TestCase):
    def setUp(self):
        self.projects = pl.load_projects(CREDITS)

    def test_load_projects_from_credits_table(self):
        self.assertEqual(self.projects["Bromite"]["license"], "GPL-3.0")
        self.assertEqual(self.projects["Debian Chromium packaging"]["license"], "UNKNOWN")

    def test_header_wins(self):
        text = "Origin: Some Project https://example.org\nAuthor: A Person\nLicense: BSD-3-Clause\n---\n"
        row = pl.classify(text, PATCHES_MD, "bromite-thing.patch", self.projects)
        self.assertEqual((row["origin"], row["license"]), ("Some Project https://example.org", "BSD-3-Clause"))
        self.assertIn("header", row["evidence"])

    def test_patches_md_mapping(self):
        row = pl.classify("diff --git a/x b/x\n", PATCHES_MD, "bromite-thing.patch", self.projects)
        self.assertEqual((row["origin"], row["license"]), ("Bromite", "GPL-3.0"))
        self.assertEqual(pl.classify("", PATCHES_MD, "hevc.patch", self.projects)["license"], "MIT")

    def test_unknown_flagged_and_sorted_first(self):
        rows = [pl.classify("", PATCHES_MD, n, self.projects)
                for n in ("bromite-thing.patch", "mystery.patch", "debian-fix.patch")]
        self.assertEqual(rows[1]["license"], "UNKNOWN")
        self.assertEqual(rows[2]["license"], "UNKNOWN")       # project known, licence still pending
        table = pl.render_table(rows)
        body = [l for l in table.splitlines() if l.startswith("| `")]
        self.assertTrue(body[0].startswith("| `debian-fix.patch`") or body[0].startswith("| `mystery.patch`"))
        self.assertTrue(body[-1].startswith("| `bromite-thing.patch`"))
        self.assertNotIn("](../", table)                       # relative links from PATCHES.md are flattened

    def test_exit_code_reflects_unknowns(self):
        tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        try:
            tree = tmp / "tree"
            (tree / "patch_scripts" / "series").mkdir(parents=True)
            (tree / "docs").mkdir()
            (tree / "other").mkdir()
            (tree / "docs" / "PATCHES.md").write_text(PATCHES_MD, encoding="utf-8")
            (tree / "other" / "bromite-thing.patch").write_text("diff\n", encoding="utf-8")
            (tree / "other" / "mystery.patch").write_text("diff\n", encoding="utf-8")
            credits = tmp / "CREDITS.md"
            credits.write_text(CREDITS, encoding="utf-8")
            series = tree / "patch_scripts" / "series" / "series"
            args = ["--tree", str(tree), "--credits", str(credits), "--out", str(tmp / "out.md")]
            series.write_text("chrome: other/bromite-thing.patch\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pl.main(args), 0)
            series.write_text("# comment\nchrome: other/bromite-thing.patch\nchrome: other/mystery.patch\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pl.main(args), 1)
            self.assertIn("mystery.patch", (tmp / "out.md").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
