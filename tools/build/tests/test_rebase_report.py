# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import unittest
from pathlib import Path

from tools.audit.tests.gitfixture import GitRepo
from tools.build import rebase_report as rr

BASE = "".join(f"line {i}\n" for i in range(1, 31))


def lines_with(**changes) -> str:
    out = []
    for i in range(1, 31):
        out.append(changes.get(f"l{i}", f"line {i}") + "\n")
    return "".join(out)


class SeriesParsingTests(unittest.TestCase):
    def test_parse_series_roots_conditions_and_comments(self):
        entries = rr.parse_series("# comment\n\nother/a.patch\nv8: other/b.patch\n[raspi] third_party/x: other/c.patch\n")
        self.assertEqual([(e.root, e.patch, e.conditions) for e in entries],
                         [(".", "other/a.patch", ()), ("v8", "other/b.patch", ()),
                          ("third_party/x", "other/c.patch", ("raspi",))])

    def test_selected_honours_conditions(self):
        entries = rr.parse_series("other/a.patch\n[raspi] other/c.patch\n")
        self.assertEqual([e.patch for e in rr.select(entries, set())], ["other/a.patch"])
        self.assertEqual([e.patch for e in rr.select(entries, {"raspi"})], ["other/a.patch", "other/c.patch"])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.src = GitRepo()                 # stands in for the Chromium checkout
        self.tree = GitRepo()                # stands in for the upstream Thorium tree
        self.src.write("f.txt", BASE.encode())
        self.src.write("g.txt", BASE.encode())
        self.src.commit("base")

    def tearDown(self):
        self.src.cleanup()
        self.tree.cleanup()

    def make_patch(self, name, rel, before: str, after: str):
        """A git patch turning `before` into `after`, created in a scratch commit and then undone."""
        self.src.write(rel, before.encode())
        self.src.git("add", "-A")
        self.src.git("commit", "-q", "--allow-empty", "-m", "scratch before")
        self.src.write(rel, after.encode())
        patch = self.src.git("diff") + "\n"
        self.src.git("reset", "-q", "--hard", "HEAD~1")
        self.tree.write(f"other/{name}", patch.encode())
        return f"other/{name}"

    def run_report(self, series_text, conditions=()):
        self.tree.write("patch_scripts/series/series", series_text.encode())
        return rr.check_series(Path(self.tree.path), Path(self.src.path), set(conditions))

    def test_statuses_applied_fuzz_rejected_and_already_applied(self):
        clean = self.make_patch("clean.patch", "f.txt", BASE, lines_with(l5="changed 5"))
        # made against a tree whose line 13 differed; line 13 is outer context for a change at line 15
        fuzz = self.make_patch("fuzz.patch", "g.txt", lines_with(l13="old 13"),
                               lines_with(l13="old 13", l15="changed 15"))
        rejected = self.make_patch("rejected.patch", "f.txt", lines_with(l25="something else"),
                                   lines_with(l25="new 25"))
        already = self.make_patch("already.patch", "g.txt", lines_with(l28="x"), BASE)
        rows = self.run_report("\n".join([clean, fuzz, rejected, already]) + "\n")
        self.assertEqual([r["status"] for r in rows], ["applied", "fuzz", "rejected", "already applied"])
        self.assertIn("f.txt", rows[2]["detail"])

    def test_series_applies_cumulatively(self):
        first = self.make_patch("first.patch", "f.txt", BASE, lines_with(l10="first"))
        second = self.make_patch("second.patch", "f.txt", lines_with(l10="first"), lines_with(l10="second"))
        rows = self.run_report(f"{first}\n{second}\n")
        self.assertEqual([r["status"] for r in rows], ["applied", "applied"])

    def test_report_never_touches_the_working_tree(self):
        clean = self.make_patch("clean.patch", "f.txt", BASE, lines_with(l5="changed 5"))
        self.run_report(clean + "\n")
        self.assertEqual(Path(self.src.path, "f.txt").read_text(encoding="utf-8"), BASE)
        self.assertEqual(self.src.git("status", "--porcelain"), "")

    def test_missing_patch_and_missing_root_are_reported(self):
        rows = self.run_report("other/nope.patch\nno_such_dir: other/nope2.patch\n")
        self.assertEqual([r["status"] for r in rows], ["missing", "missing"])

    def test_render_summarises_and_lists_every_patch(self):
        rows = [{"patch": "other/a.patch", "root": ".", "status": "applied", "detail": ""},
                {"patch": "other/b.patch", "root": "v8", "status": "rejected", "detail": "error: patch failed: x.cc:3"}]
        text = rr.render(rows, "Thorium M156 series", "158.0.8127.30")
        self.assertIn("applied: 1", text)
        self.assertIn("rejected: 1", text)
        self.assertIn("`other/b.patch`", text)
        self.assertIn("158.0.8127.30", text)

    def test_main_writes_report_and_exit_code(self):
        clean = self.make_patch("clean.patch", "f.txt", BASE, lines_with(l5="changed 5"))
        self.tree.write("patch_scripts/series/series", (clean + "\n").encode())
        out = Path(self.tree.path, "report.md")
        args = ["--tree", self.tree.path, "--src", self.src.path, "--out", str(out), "--chromium", "1.2.3.4"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rr.main(args), 0)
        self.assertIn("other/clean.patch", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
