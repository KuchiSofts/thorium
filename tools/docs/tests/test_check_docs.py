# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import shutil
import tempfile
import unittest
from pathlib import Path

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
        a = self.write("a.md", "[x](docs/b.md#sec) [y](https://e.org) [z](#top)\n")
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
        doc = self.write("README.md", "Data lives in C:\\Users\\Someone\\x here.\n")
        problems = check_docs.check_private(self.root, [doc], None)
        self.assertEqual(len(problems), 1)
        self.assertFalse(any("Someone" in p for p in problems))

    def test_private_list_entry_detected_without_echo(self):
        secrets = self.write("private.txt", "SecretWord\n\n")
        doc = self.write("README.md", "nothing to see: secretword\n")
        problems = check_docs.check_private(self.root, [doc], secrets)
        self.assertEqual(len(problems), 1)
        self.assertFalse(any("secret" in p.lower() for p in problems))


if __name__ == "__main__":
    unittest.main()
