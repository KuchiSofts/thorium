# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.audit.tests.gitfixture import GitRepo
from tools.docs import check_docs

LEGEND = "Status legend: ⬜ todo · 🔄 in progress · ✅ done · ⛔ blocked\n"


class CheckDocsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="thoron-test-"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_broken_relative_link_reported(self):
        a = self.write("a.md", "[x](docs/missing.md)\n")
        problems = check_docs.check_links(self.root, [a])
        self.assertEqual(len(problems), 1)
        self.assertIn("a.md:1", problems[0])

    def test_valid_links_and_anchors_pass(self):
        self.write("docs/b.md", "# sec\n")
        a = self.write("a.md", "[x](docs/b.md#sec) [y](https://e.org) [z](#top)\n\n## Top\n")
        self.assertEqual(check_docs.check_links(self.root, [a]), [])

    def test_changelog_requires_unreleased(self):
        bad = self.write("bad/CHANGELOG.md", "# Changelog\n\n## [1.0.0] - 2026-01-01\n")
        good = self.write("good/CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n")
        self.assertEqual(len(check_docs.check_changelog(bad)), 1)
        self.assertEqual(check_docs.check_changelog(good), [])

    def test_roadmap_duplicate_ids_and_legend(self):
        bad = self.write("bad/ROADMAP.md",
                         "Last updated: 2026-11-07\n- [ ] **P1.1** one\n- [x] **P1.1** two\n")
        good = self.write("good/ROADMAP.md",
                          "Last updated: 2026-11-07\n" + LEGEND + "- [ ] **P1.1** one\n- [x] **S.2** two\n")
        self.assertGreaterEqual(len(check_docs.check_roadmap(bad)), 2)
        self.assertEqual(check_docs.check_roadmap(good), [])

    def test_private_path_detected_without_echo(self):
        doc = self.write("README.md", "Data lives in C:\\Users\\Someone\\x here.\n")  # privacy-check: allow
        problems = check_docs.check_private(self.root, [doc], None)
        self.assertEqual(len(problems), 1)
        self.assertFalse(any("Someone" in p for p in problems))

    def test_private_list_entry_detected_without_echo(self):
        secrets = self.write("private.txt", "SecretWord\n\n")
        doc = self.write("README.md", "nothing to see: secretword\n")
        problems = check_docs.check_private(self.root, [doc], secrets)
        self.assertEqual(len(problems), 1)
        self.assertFalse(any("secret" in p.lower() for p in problems))

    # --- review I3: realistic personal paths, list encodings, scope, root ------------------
    def test_private_path_variants_detected(self):
        samples = [
            "c:\\users\\someone\\x",       # privacy-check: allow
            "/c/Users/Someone/x",          # privacy-check: allow
            "/mnt/c/Users/Someone/x",      # privacy-check: allow
            "/home/Someone/x",             # privacy-check: allow
            "/Users/someone/x",            # privacy-check: allow
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                doc = self.write("README.md", f"path: {sample}\n")
                problems = check_docs.check_private(self.root, [doc], None)
                self.assertEqual(len(problems), 1, problems)
                self.assertFalse(any("someone" in p.lower() for p in problems))

    def test_urls_with_users_segment_not_flagged(self):
        doc = self.write("README.md", "see https://api.github.com/users/octocat and /home/user/x\n")
        self.assertEqual(check_docs.check_private(self.root, [doc], None), [])

    def test_private_list_with_bom_or_utf16_is_read(self):
        doc = self.write("README.md", "mentions secretword here\n")
        for encoding in ("utf-8-sig", "utf-16"):
            with self.subTest(encoding=encoding):
                lst = self.root / f"list-{encoding}.txt"
                lst.write_bytes("SecretWord\r\nOther\r\n".encode(encoding))
                self.assertEqual(len(check_docs.check_private(self.root, [doc], lst)), 1)

    def test_allow_marker_skips_line(self):
        doc = self.write("README.md", "fixture C:\\Users\\Someone\\x  privacy-check: allow\n")  # privacy-check: allow
        self.assertEqual(check_docs.check_private(self.root, [doc], None), [])

    def test_long_dashes_flagged(self):
        em, en = chr(0x2014), chr(0x2013)  # built from code points so no sweep can alter them
        bad = self.write("README.md", f"one {em} two\nsizes 16{en}512\nfine - here\n")
        problems = check_docs.check_dashes(self.root, [bad])
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(problems[0].startswith("README.md:1:"))
        good = self.write("docs/ok.md", "only - short - dashes\n")
        self.assertEqual(check_docs.check_dashes(self.root, [good]), [])

    def test_main_requires_readme_at_root(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_docs.main(["--root", str(self.root)]), 2)

    def test_main_scans_owned_python_files_for_private_data(self):
        self.write("README.md", "# ok\n")
        self.write("tools/x.py", "P = 'C:\\\\Users\\\\Someone\\\\x'\n")  # privacy-check: allow
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_docs.main(["--root", str(self.root), "--private"]), 1)

    # --- nothing that describes one particular PC -----------------------------------------
    def test_a_path_on_a_drive_other_than_c_is_flagged_without_echo(self):
        samples = [
            "build under X:\\work\\out",                 # privacy-check: allow
            "copy it to x:/work/out",                    # privacy-check: allow
            "swapFile=X:\\\\work\\\\swap.vhdx",          # privacy-check: allow
            "$repo = 'X:\\path\\to\\repo'",              # privacy-check: allow
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                doc = self.write("README.md", f"{sample}\n")
                problems = check_docs.check_private(self.root, [doc], None)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("drive", problems[0])
                self.assertNotIn("work", problems[0])

    def test_c_drive_placeholders_and_urls_are_not_taken_for_a_drive(self):
        doc = self.write("README.md", "C:\\thoron-build\\out, c:/x, <drive>:\\x, %LOCALAPPDATA%\\x\n"
                                      "https://e.org/a file:///C:/x git@github.com:a/b\n"
                                      "a regex [a-z]:[\\\\/] and a ratio 10:/2 and key:/value\n")
        self.assertEqual(check_docs.check_private(self.root, [doc], None), [])

    def test_a_hardware_model_is_flagged(self):
        samples = ["CPU: Core i5-9400", "an AMD Ryzen 5 3600", "GeForce RTX 3060", "Xeon E5 box"]   # privacy-check: allow
        for sample in samples:
            with self.subTest(sample=sample):
                doc = self.write("README.md", f"measured on {sample}\n")
                problems = check_docs.check_private(self.root, [doc], None)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("hardware", problems[0])

    def test_a_hardware_class_is_not_flagged(self):
        doc = self.write("README.md", "a 16-core / 32-thread desktop CPU with 64 GB of RAM\n"
                                      "AVX2 needs Haswell, Ryzen or newer; Core 2 is not enough\n")
        self.assertEqual(check_docs.check_private(self.root, [doc], None), [])

    def test_main_scans_scripts_and_every_doc_folder_of_ours(self):
        for rel in ("tools/build/env.ps1", "tools/x.sh", "docs/security/NET.md", "docs/perf/run.md", "docs/new/x.md"):
            with self.subTest(rel=rel):
                shutil.rmtree(self.root)
                self.write("README.md", "# ok\n")
                self.write(rel, "root is X:\\work here\n")       # privacy-check: allow
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(check_docs.main(["--root", str(self.root), "--private"]), 1)

    def test_upstream_reference_docs_are_not_ours_to_judge(self):
        self.write("README.md", "# ok\n")
        self.write("docs/upstream/BUILDING.md", "root is X:\\work here\n")   # privacy-check: allow
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_docs.main(["--root", str(self.root), "--private"]), 0)

    # --- review I4: every link form, exact case, inside the repository ---------------------
    def assert_one_broken(self, text):
        a = self.write("a.md", text)
        problems = check_docs.check_links(self.root, [a])
        self.assertEqual(len(problems), 1, problems)

    def test_reference_style_link_checked(self):
        self.assert_one_broken("see [x][r]\n\n[r]: missing.md\n")

    def test_badge_outer_link_checked(self):
        self.write("ok.png", "x")
        self.assert_one_broken("[![b](ok.png)](missing.md)\n")

    def test_html_href_and_src_checked(self):
        a = self.write("a.md", '<a href="missing.md">x</a> <img src="nope.png"> <a href="https://e.org">e</a>\n')
        self.assertEqual(len(check_docs.check_links(self.root, [a])), 2)

    def test_case_mismatch_is_broken(self):
        self.write("docs/real.md", "x")
        self.assert_one_broken("[x](docs/REAL.md)\n")

    def test_link_outside_root_is_broken(self):
        (self.root.parent / f"{self.root.name}-outside.md").write_text("x", encoding="utf-8")
        try:
            self.assert_one_broken(f"[x](../{self.root.name}-outside.md)\n")
        finally:
            (self.root.parent / f"{self.root.name}-outside.md").unlink()

    def test_link_to_gitignored_file_is_broken(self):
        repo = GitRepo()
        try:
            root = Path(repo.path)
            (root / ".gitignore").write_text("secret.md\n", encoding="utf-8")
            (root / "secret.md").write_text("x", encoding="utf-8")
            (root / "public.md").write_text("x", encoding="utf-8")
            a = root / "README.md"
            a.write_text("[s](secret.md) [p](public.md)\n", encoding="utf-8")
            problems = check_docs.check_links(root, [a])
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("secret.md", problems[0])
        finally:
            repo.cleanup()

    # --- section anchors must exist (GitHub heading slugs) -----------------------------------
    def test_broken_anchor_reported(self):
        self.write("ROADMAP.md", "## P0 - Foundation\n")
        self.assert_one_broken("[p0](ROADMAP.md#p0--foundation)\n")

    def test_valid_anchors_pass(self):
        self.write("ROADMAP.md", "## P0 - Foundation\n## Quality & performance (Q)\n")
        a = self.write("a.md", "[p0](ROADMAP.md#p0---foundation) [q](ROADMAP.md#quality--performance-q) [t](#top)\n\n## Top\n")
        self.assertEqual(check_docs.check_links(self.root, [a]), [])

if __name__ == "__main__":
    unittest.main()
