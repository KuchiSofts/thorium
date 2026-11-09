# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Origin, Author and License lines in every patch (ROADMAP S.7)."""
import tempfile
import unittest
from pathlib import Path

from tools.legal import patch_headers as ph

DIFF = "diff --git a/x.cc b/x.cc\nindex 1..2 100644\n--- a/x.cc\n+++ b/x.cc\n@@ -1 +1 @@\n-a\n+b\n"
OURS = "Thoron: a fix.\n\nOrigin: Thoron\nAuthor: KuchiSofts\nLicense: BSD-3-Clause\n\n" + DIFF
ROW = {"origin": "Thorium (Alex313031, gz83)", "license": "BSD-3-Clause", "evidence": "x"}


class FieldTests(unittest.TestCase):
    def test_fields_only_from_the_text_before_the_diff(self):
        self.assertEqual(ph.header_fields(OURS), {"origin": "Thoron", "author": "KuchiSofts", "license": "BSD-3-Clause"})
        # a License: line inside the diff (for example in a changed source file) does not count
        self.assertEqual(ph.header_fields(DIFF + "+License: MIT\n"), {})

    def test_missing(self):
        self.assertEqual(ph.missing(OURS), [])
        self.assertEqual(ph.missing(DIFF), ["Origin", "Author", "License"])


class AddTests(unittest.TestCase):
    def test_adds_lines_from_research_before_the_diff(self):
        out = ph.add_header(DIFF, ROW)
        self.assertTrue(out.endswith(DIFF))
        self.assertEqual(ph.header_fields(out), {"origin": "Thorium (Alex313031, gz83)", "author": "Alex313031, gz83",
                                                 "license": "BSD-3-Clause"})
        self.assertIn("docs/legal/PATCH_ORIGINS.md", out.split("diff --git")[0])

    def test_author_falls_back_to_the_origin(self):
        out = ph.add_header(DIFF, {"origin": "Chromium, Thorium", "license": "BSD-3-Clause", "evidence": "x"})
        self.assertEqual(ph.header_fields(out)["author"], "Chromium, Thorium")

    def test_several_projects_list_every_author(self):
        row = {"origin": "Thorium, RobRich999, electron-chromium-codecs (Muril-o)", "license": "NOT STATED", "evidence": "x"}
        fields = ph.header_fields(ph.add_header(DIFF, row))
        self.assertEqual(fields["author"], "Thorium, RobRich999, electron-chromium-codecs (Muril-o)")
        self.assertEqual(fields["license"], "NOT STATED")

    def test_idempotent_and_never_overwrites(self):
        once = ph.add_header(DIFF, ROW)
        self.assertEqual(ph.add_header(once, ROW), once)
        self.assertEqual(ph.add_header(OURS, ROW), OURS)       # an existing header is never replaced

    def test_partial_header_raises(self):
        with self.assertRaisesRegex(ph.HeaderError, "Author"):
            ph.add_header("Origin: Thoron\nLicense: MIT\n\n" + DIFF, ROW)

    def test_keeps_an_existing_description_and_crlf(self):
        text = "Upstream description.\r\n\r\n" + DIFF.replace("\n", "\r\n")
        out = ph.add_header(text, ROW)
        self.assertIn("Upstream description.", out)
        self.assertNotIn("\n", out.replace("\r\n", ""))


class LintTests(unittest.TestCase):
    def test_lint_names_patches_without_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "other").mkdir()
            (tree / "patch_scripts/series").mkdir(parents=True)
            (tree / "other/ours.patch").write_text(OURS, encoding="utf-8")
            (tree / "other/theirs.patch").write_text(DIFF, encoding="utf-8")
            (tree / "patch_scripts/series/series").write_text("other/ours.patch\nother/theirs.patch\n", encoding="utf-8")
            problems = ph.lint(tree)
            self.assertEqual(len(problems), 1)
            self.assertIn("theirs.patch", problems[0])

    def test_header_licence_must_match_the_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "other").mkdir()
            (tree / "patch_scripts/series").mkdir(parents=True)
            (tree / "other/a.patch").write_text(ph.add_header(DIFF, ROW), encoding="utf-8")
            (tree / "patch_scripts/series/series").write_text("other/a.patch\n", encoding="utf-8")
            self.assertEqual(ph.lint(tree, {"a.patch": ROW}), [])
            other = dict(ROW, license="GPL-3.0")
            self.assertTrue([p for p in ph.lint(tree, {"a.patch": other}) if "GPL-3.0" in p])


if __name__ == "__main__":
    unittest.main()
