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

    def test_conditional_series_lines_resolve_to_the_patch_file(self):
        tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        try:
            series = tmp / "patch_scripts" / "series" / "series"
            series.parent.mkdir(parents=True)
            series.write_text("[raspi] other/a.patch\n[sse2] third_party/angle: other/SSE2/b.patch\n"
                              "v8: other/c.patch\nother/d.patch\n", encoding="utf-8")
            self.assertEqual(pl.series_patches(tmp),
                             ["other/a.patch", "other/SSE2/b.patch", "other/c.patch", "other/d.patch"])
        finally:
            shutil.rmtree(tmp)

    def test_runs_as_a_script(self):
        import subprocess
        import sys
        tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        try:
            (tmp / "patch_scripts" / "series").mkdir(parents=True)
            (tmp / "docs").mkdir()
            (tmp / "patch_scripts" / "series" / "series").write_text("[raspi] other/a.patch\n", encoding="utf-8")
            (tmp / "docs" / "PATCHES.md").write_text(PATCHES_MD, encoding="utf-8")
            (tmp / "credits.md").write_text(CREDITS, encoding="utf-8")
            script = Path(pl.__file__)
            proc = subprocess.run([sys.executable, "-I", str(script), "--tree", str(tmp), "--credits",
                                   str(tmp / "credits.md"), "--out", str(tmp / "out.md")],
                                  capture_output=True, text=True)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn(proc.returncode, (0, 1))
        finally:
            shutil.rmtree(tmp)

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


RESEARCH = ("patch\torigin\tlicense\tevidence\n"
            "# comment lines and blank lines are ignored\n\n"
            "mystery.patch\tThorium (Alex313031)\tBSD-3-Clause\tno match in the compared projects\n"
            "bromite-thing.patch\tCromite\tGPL-3.0\t120 of 130 added lines identical to Cromite X.patch\n"
            "unclear.patch\tChromium_Clang (RobRich999)\tNOT STATED\tauthor publishes no licence\n")


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.projects = pl.load_projects(CREDITS)
        self.research = pl.load_research(RESEARCH)

    def test_load_research_reads_rows(self):
        self.assertEqual(set(self.research), {"mystery.patch", "bromite-thing.patch", "unclear.patch"})
        self.assertEqual(self.research["unclear.patch"]["license"], "NOT STATED")

    def test_load_research_rejects_bad_rows(self):
        bad = ("patch\torigin\tlicense\tevidence\nx.patch\tA\tBSD-3-Clause\n",                       # missing column
               "patch\torigin\tlicense\tevidence\nx.patch\tA\tPublic-ish\te\n",                      # not an allowed licence
               "patch\torigin\tlicense\tevidence\nx.patch\tA\tMIT\te\nx.patch\tB\tMIT\te\n",          # duplicate
               "patch\torigin\tlicense\tevidence\nx.patch\tA\tMIT\tsee " + chr(0x2014) + " here\n",    # long dash
               "patch\torigin\tlicense\tevidence\nx.patch\tA\tUNKNOWN\te\n")                          # research never says UNKNOWN
        for text in bad:
            with self.assertRaises(ValueError, msg=text):
                pl.load_research(text)

    def test_research_beats_patches_md_but_not_the_header(self):
        row = pl.classify("diff\n", PATCHES_MD, "bromite-thing.patch", self.projects, self.research)
        self.assertEqual((row["origin"], row["license"]), ("Cromite", "GPL-3.0"))
        self.assertTrue(row["evidence"].startswith("research: "))
        row = pl.classify("diff\n", PATCHES_MD, "mystery.patch", self.projects, self.research)
        self.assertEqual(row["license"], "BSD-3-Clause")
        header = "License: MIT\n---\n"
        self.assertEqual(pl.classify(header, PATCHES_MD, "mystery.patch", self.projects, self.research)["license"], "MIT")

    def test_header_that_agrees_with_research_keeps_the_research_evidence(self):
        header = "Origin: Cromite\nAuthor: uazo\nLicense: GPL-3.0\n\ndiff\n"
        row = pl.classify(header, PATCHES_MD, "bromite-thing.patch", self.projects, self.research)
        self.assertEqual(row["license"], "GPL-3.0")
        self.assertTrue(row["evidence"].startswith("research: "), row["evidence"])

    def test_header_that_agrees_with_patches_md_keeps_that_evidence(self):
        plain = pl.classify("diff\n", PATCHES_MD, "bromite-thing.patch", self.projects)   # no research row
        header = f"Origin: {plain['origin']}\nAuthor: x\nLicense: {plain['license']}\n\ndiff\n"
        row = pl.classify(header, PATCHES_MD, "bromite-thing.patch", self.projects)
        self.assertEqual(row["evidence"], plain["evidence"])

    def test_not_stated_project_licence_is_kept_distinct(self):
        projects = pl.load_projects("| Chromium_Clang (RobRich999) | https://github.com/RobRich999/Chromium_Clang | not stated |\n")
        self.assertEqual(projects["Chromium_Clang (RobRich999)"]["license"], "NOT STATED")

    def test_not_stated_is_flagged_in_the_table(self):
        row = pl.classify("diff\n", PATCHES_MD, "unclear.patch", self.projects, self.research)
        table = pl.render_table([row])
        self.assertIn("**NOT STATED**", table)
        self.assertIn("NOT STATED: 1", table)

    def test_main_fails_on_not_stated_and_on_stale_research(self):
        tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        try:
            tree = tmp / "tree"
            (tree / "patch_scripts" / "series").mkdir(parents=True)
            (tree / "docs").mkdir()
            (tree / "other").mkdir()
            (tree / "docs" / "PATCHES.md").write_text(PATCHES_MD, encoding="utf-8")
            for n in ("mystery.patch", "unclear.patch"):
                (tree / "other" / n).write_text("diff\n", encoding="utf-8")
            (tmp / "CREDITS.md").write_text(CREDITS, encoding="utf-8")
            research = tmp / "origins.tsv"
            series = tree / "patch_scripts" / "series" / "series"
            args = ["--tree", str(tree), "--credits", str(tmp / "CREDITS.md"), "--out", str(tmp / "out.md"),
                    "--research", str(research)]
            series.write_text("chrome: other/mystery.patch\n", encoding="utf-8")
            research.write_text("patch\torigin\tlicense\tevidence\nmystery.patch\tThorium\tBSD-3-Clause\te\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pl.main(args), 0)
            series.write_text("chrome: other/mystery.patch\nchrome: other/unclear.patch\n", encoding="utf-8")
            research.write_text(RESEARCH.replace("bromite-thing.patch\tCromite\tGPL-3.0\t120 of 130 added lines identical to Cromite X.patch\n", ""),
                                encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pl.main(args), 1)                 # NOT STATED blocks a release
            research.write_text(RESEARCH, encoding="utf-8")         # names bromite-thing.patch, not in the series
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(pl.main(args), 1)
            self.assertIn("bromite-thing.patch", out.getvalue())   # stale research row is reported
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
