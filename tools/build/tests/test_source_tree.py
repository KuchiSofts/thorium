# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.audit.tests.gitfixture import GitRepo
from tools.build import source_tree as st

CRLF = b"line one\r\nline two\r\n"


class SourceTreeTests(unittest.TestCase):
    """An upstream repository with three patches; our branch changes one, removes one and adds one."""

    def setUp(self):
        self.repo = GitRepo()
        self.repo.write("other/keep.patch", b"upstream keeps this\n")
        self.repo.write("other/change.patch", b"upstream version\n")
        self.repo.write("other/drop.patch", b"we leave this out\n")
        self.repo.write("src/overlay.cc", b"int upstream();\n")
        self.base = self.repo.commit("upstream")
        self.repo.write("other/change.patch", b"our version\n")
        self.repo.remove("other/drop.patch")
        self.repo.write("other/ks-new.patch", CRLF)
        self.repo.git("config", "core.fileMode", "false")       # the mode comes from the index, as on Windows
        self.repo.write("tools/run.sh", b"#!/bin/sh\n")
        self.repo.add_entry("tools/run.sh", b"#!/bin/sh\n", mode="100755")
        self.repo.git("add", "-A", "other")
        self.head = self.repo.commit_index("ours")
        self.tree = self.repo.git("rev-parse", "HEAD^{tree}")
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.source = self.tmp / "source"

    def tearDown(self):
        self.repo.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def export(self):
        return st.export(Path(self.repo.path), self.base, self.source, chromium="158.0.1.2",
                         repository="https://example.org/upstream.git")

    def overlay_files(self):
        root = self.source / "overlay"
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    # --- export -----------------------------------------------------------------------------
    def test_export_holds_only_what_we_add_or_change(self):
        self.export()
        self.assertEqual(self.overlay_files(), ["other/change.patch", "other/ks-new.patch", "tools/run.sh"])
        self.assertEqual((self.source / "overlay/other/change.patch").read_bytes(), b"our version\n")
        self.assertEqual((self.source / "REMOVED.txt").read_text(encoding="utf-8").split(), ["other/drop.patch"])

    def test_export_keeps_every_byte(self):
        self.export()
        self.assertEqual((self.source / "overlay/other/ks-new.patch").read_bytes(), CRLF)

    def test_export_records_where_it_came_from_and_what_it_makes(self):
        info = self.export()
        on_disk = json.loads((self.source / "UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual(info, on_disk)
        self.assertEqual(on_disk["commit"], self.base)
        self.assertEqual(on_disk["tree"], self.tree)
        self.assertEqual(on_disk["chromium"], "158.0.1.2")
        self.assertEqual(on_disk["repository"], "https://example.org/upstream.git")
        self.assertEqual(on_disk["executable"], ["tools/run.sh"])

    def test_export_again_drops_what_is_no_longer_ours(self):
        self.export()
        stale = self.source / "overlay/other/old.patch"
        stale.write_bytes(b"left from an earlier export\n")
        self.export()
        self.assertFalse(stale.exists())

    def test_export_refuses_uncommitted_changes(self):
        self.repo.write("other/keep.patch", b"edited, not committed\n")
        with self.assertRaises(st.SourceError) as ctx:
            self.export()
        self.assertIn("uncommitted", str(ctx.exception))

    def test_export_never_writes_outside_its_folder(self):
        (self.tmp / "source").mkdir()
        (self.tmp / "source" / "NOTES.md").write_text("ours, not the tool's\n", encoding="utf-8")
        self.export()
        self.assertTrue((self.source / "NOTES.md").is_file())           # only overlay/, REMOVED.txt, UPSTREAM.json

    # --- a file that must not be published (credentials that are not ours) ---------------------
    def export_withholding(self):
        return st.export(Path(self.repo.path), self.base, self.source, chromium="158.0.1.2",
                         repository="https://example.org/upstream.git", withhold=["other/change.patch"])

    def test_a_withheld_file_is_recorded_by_hash_and_never_written(self):
        info = self.export_withholding()
        self.assertEqual(self.overlay_files(), ["other/ks-new.patch", "tools/run.sh"])
        self.assertEqual(info["withheld"], {"other/change.patch": self.repo.git("rev-parse", "HEAD:other/change.patch")})
        everything = b"".join(p.read_bytes() for p in self.source.rglob("*") if p.is_file())
        self.assertNotIn(b"our version", everything)

    def test_the_tree_still_verifies_with_a_withheld_file(self):
        self.export_withholding()
        self.assertEqual(st.verify(Path(self.repo.path), self.source), self.tree)
        info = json.loads((self.source / "UPSTREAM.json").read_text(encoding="utf-8"))
        info["withheld"]["other/change.patch"] = "0" * 40
        (self.source / "UPSTREAM.json").write_text(json.dumps(info), encoding="utf-8")
        with self.assertRaises(st.SourceError):
            st.verify(Path(self.repo.path), self.source)

    def test_materialize_writes_a_withheld_file_only_where_its_content_exists(self):
        self.export_withholding()
        out = self.tmp / "tree"
        st.materialize(Path(self.repo.path), self.source, out)          # this clone has the content
        self.assertEqual((out / "other/change.patch").read_bytes(), b"our version\n")
        elsewhere = GitRepo()                                           # a clone of upstream alone has not
        try:
            elsewhere.git("fetch", "-q", self.repo.path, self.base)
            with self.assertRaises(st.SourceError) as ctx:
                st.materialize(Path(elsewhere.path), self.source, self.tmp / "tree2")
            self.assertIn("withheld", str(ctx.exception))
            self.assertIn("other/change.patch", str(ctx.exception))
            self.assertFalse((self.tmp / "tree2").exists() and any((self.tmp / "tree2").iterdir()))
            self.assertEqual(st.verify(Path(elsewhere.path), self.source), self.tree)   # the record still checks
        finally:
            elsewhere.cleanup()

    def test_withholding_a_file_that_is_not_ours_is_refused(self):
        with self.assertRaises(st.SourceError):
            st.export(Path(self.repo.path), self.base, self.source, chromium="1", repository="r",
                      withhold=["other/keep.patch"])

    # --- verify -----------------------------------------------------------------------------
    def test_verify_accepts_what_export_wrote(self):
        self.export()
        self.assertEqual(st.verify(Path(self.repo.path), self.source), self.tree)

    def test_verify_notices_a_changed_overlay_file(self):
        self.export()
        (self.source / "overlay/other/change.patch").write_bytes(b"tampered\n")
        with self.assertRaises(st.SourceError) as ctx:
            st.verify(Path(self.repo.path), self.source)
        self.assertIn("does not match", str(ctx.exception))

    def test_verify_notices_an_extra_or_a_missing_file(self):
        self.export()
        (self.source / "overlay/other/extra.patch").write_bytes(b"sneaked in\n")
        with self.assertRaises(st.SourceError):
            st.verify(Path(self.repo.path), self.source)
        (self.source / "overlay/other/extra.patch").unlink()
        (self.source / "REMOVED.txt").write_text("", encoding="utf-8")
        with self.assertRaises(st.SourceError):
            st.verify(Path(self.repo.path), self.source)

    def test_verify_compares_raw_bytes_whatever_the_tree_says_about_line_endings(self):
        repo = GitRepo()                                    # upstream asks git to normalise patches
        try:
            repo.write(".gitattributes", b"*.patch text eol=lf\n")
            base = repo.commit("upstream")
            repo.add_entry("other/ks-crlf.patch", CRLF)     # our patch keeps its CRLF lines: stored as they are
            repo.commit_index("ours")
            tree = repo.git("rev-parse", "HEAD^{tree}")
            source = self.tmp / "by-hand"
            (source / "overlay" / "other").mkdir(parents=True)
            (source / "overlay" / "other" / "ks-crlf.patch").write_bytes(CRLF)
            (source / "REMOVED.txt").write_bytes(b"")
            (source / "UPSTREAM.json").write_text(json.dumps({"commit": base, "tree": tree, "executable": []}),
                                                  encoding="utf-8")
            self.assertEqual(st.verify(Path(repo.path), source), tree)
        finally:
            repo.cleanup()

    def test_verify_needs_the_pinned_commit(self):
        self.export()
        other = GitRepo()
        try:
            other.write("x", b"x\n")
            other.commit("something else")
            with self.assertRaises(st.SourceError) as ctx:
                st.verify(Path(other.path), self.source)
            self.assertIn("pinned", str(ctx.exception))
        finally:
            other.cleanup()

    def test_paths_that_leave_the_tree_are_refused(self):
        self.export()
        for bad in ("../outside.txt", "/abs.txt", "other/../../x", "C:/x"):
            with self.subTest(bad=bad):
                (self.source / "REMOVED.txt").write_text(bad + "\n", encoding="utf-8")
                with self.assertRaises(st.SourceError) as ctx:
                    st.verify(Path(self.repo.path), self.source)
                self.assertIn("path", str(ctx.exception))

    def test_verify_leaves_the_upstream_checkout_alone(self):
        self.export()
        before = (self.repo.git("status", "--porcelain"), self.repo.git("rev-parse", "HEAD"))
        st.verify(Path(self.repo.path), self.source)
        self.assertEqual((self.repo.git("status", "--porcelain"), self.repo.git("rev-parse", "HEAD")), before)

    # --- materialize ------------------------------------------------------------------------
    def test_materialize_gives_the_exact_tree(self):
        self.export()
        out = self.tmp / "tree"
        st.materialize(Path(self.repo.path), self.source, out)
        files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        self.assertEqual(files, ["other/change.patch", "other/keep.patch", "other/ks-new.patch", "src/overlay.cc",
                                 "tools/run.sh"])
        self.assertEqual((out / "other/change.patch").read_bytes(), b"our version\n")
        self.assertEqual((out / "other/ks-new.patch").read_bytes(), CRLF)
        self.assertEqual((out / "other/keep.patch").read_bytes(), b"upstream keeps this\n")

    def test_materialize_refuses_a_folder_that_holds_something(self):
        self.export()
        out = self.tmp / "tree"
        out.mkdir()
        (out / "mine.txt").write_text("keep\n", encoding="utf-8")
        with self.assertRaises(st.SourceError):
            st.materialize(Path(self.repo.path), self.source, out)
        self.assertEqual([p.name for p in out.iterdir()], ["mine.txt"])

    def test_materialize_writes_nothing_when_the_source_does_not_verify(self):
        self.export()
        (self.source / "overlay/other/change.patch").write_bytes(b"tampered\n")
        out = self.tmp / "tree"
        with self.assertRaises(st.SourceError):
            st.materialize(Path(self.repo.path), self.source, out)
        self.assertFalse(out.exists() and any(out.iterdir()))

    # --- command line -----------------------------------------------------------------------
    def test_command_line_round_trip(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = st.main(["export", "--tree", self.repo.path, "--base", self.base, "--out", str(self.source),
                            "--chromium", "158.0.1.2", "--repository", "https://example.org/upstream.git"])
            self.assertEqual(code, 0)
            self.assertEqual(st.main(["verify", "--upstream", self.repo.path, "--source", str(self.source)]), 0)
            (self.source / "overlay/other/change.patch").write_bytes(b"tampered\n")
            self.assertEqual(st.main(["verify", "--upstream", self.repo.path, "--source", str(self.source)]), 1)
        self.assertIn(self.tree, out.getvalue())


if __name__ == "__main__":
    unittest.main()
