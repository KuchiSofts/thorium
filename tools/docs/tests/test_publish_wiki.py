# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.docs import publish_wiki as pw


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.source, self.clone = self.tmp / "docs-wiki", self.tmp / "clone"
        self.source.mkdir()
        (self.clone / ".git").mkdir(parents=True)
        (self.clone / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        (self.source / "Home.md").write_text("# Thoron\n", encoding="utf-8")
        (self.source / "Install.md").write_text("# Install\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pages(self):
        return sorted(p.name for p in self.clone.iterdir() if p.is_file())

    def test_pages_are_copied(self):
        self.assertEqual(pw.sync(self.source, self.clone), ["Home.md", "Install.md"])
        self.assertEqual(self.pages(), ["Home.md", "Install.md"])
        self.assertEqual((self.clone / "Install.md").read_text(encoding="utf-8"), "# Install\n")

    def test_a_page_that_is_gone_from_the_source_is_removed(self):
        (self.clone / "Old.md").write_text("# Old\n", encoding="utf-8")
        self.assertEqual(pw.sync(self.source, self.clone), ["Home.md", "Install.md", "Old.md"])
        self.assertEqual(self.pages(), ["Home.md", "Install.md"])

    def test_an_unchanged_page_is_not_reported(self):
        pw.sync(self.source, self.clone)
        (self.source / "Install.md").write_text("# Install, again\n", encoding="utf-8")
        self.assertEqual(pw.sync(self.source, self.clone), ["Install.md"])

    def test_pages_are_published_with_unix_line_ends_whatever_the_checkout_has(self):
        (self.source / "Install.md").write_bytes(b"# Install\r\n\r\ntext\r\n")
        pw.sync(self.source, self.clone)
        self.assertEqual((self.clone / "Install.md").read_bytes(), b"# Install\n\ntext\n")
        self.assertEqual(pw.sync(self.source, self.clone), [])

    def test_the_clone_itself_is_left_alone(self):
        pw.sync(self.source, self.clone)
        self.assertEqual((self.clone / ".git" / "config").read_text(encoding="utf-8"), "[core]\n")

    def test_a_source_without_a_home_page_is_refused(self):
        (self.source / "Home.md").unlink()
        with self.assertRaises(pw.WikiError):
            pw.sync(self.source, self.clone)
        self.assertEqual(self.pages(), [])

    def test_only_pages_are_published(self):
        (self.source / "notes.txt").write_text("not a page\n", encoding="utf-8")
        (self.source / "drafts").mkdir()
        (self.source / "drafts" / "Later.md").write_text("# Later\n", encoding="utf-8")
        pw.sync(self.source, self.clone)
        self.assertEqual(self.pages(), ["Home.md", "Install.md"])


class PublishTests(unittest.TestCase):
    """Against a local bare repository standing in for the wiki on GitHub."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.remote = self.tmp / "wiki.git"
        seed = self.tmp / "seed"
        subprocess.run(["git", "init", "-q", "-b", "master", str(seed)], check=True)
        (seed / "Home.md").write_bytes(b"first page\n")
        for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com",
                                     "commit", "-q", "-m", "first page"]):
            subprocess.run(["git", "-C", str(seed), *args], check=True, capture_output=True)
        subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(self.remote)], check=True)
        self.source = self.tmp / "docs-wiki"
        self.source.mkdir()
        (self.source / "Home.md").write_bytes(b"# Thoron\n\nline two\n")
        (self.source / "Install.md").write_bytes(b"# Install\n")
        self.identity = ("t", "t@users.noreply.github.com")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def show(self, name):
        return subprocess.run(["git", "-C", str(self.remote), "show", f"master:{name}"], capture_output=True).stdout

    def test_publishes_then_has_nothing_left_to_do(self):
        first = pw.publish("o/r", self.source, url=str(self.remote), identity=self.identity)
        self.assertEqual(first, ["Home.md", "Install.md"])
        self.assertEqual(self.show("Home.md"), b"# Thoron\n\nline two\n")
        self.assertEqual(pw.publish("o/r", self.source, url=str(self.remote), identity=self.identity), [])

    def test_a_dry_run_publishes_nothing(self):
        self.assertEqual(pw.publish("o/r", self.source, dry_run=True, url=str(self.remote), identity=self.identity),
                         ["Home.md", "Install.md"])
        self.assertEqual(self.show("Home.md"), b"first page\n")

    def test_commits_carry_utc_time_stamps(self):
        pw.publish("o/r", self.source, url=str(self.remote), identity=self.identity)
        offsets = subprocess.run(["git", "-C", str(self.remote), "log", "-1", "--format=%ad %cd", "--date=format:%z"],
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(offsets, ["+0000", "+0000"])

    def test_an_identity_that_is_not_a_noreply_address_publishes_nothing(self):
        with self.assertRaises(pw.WikiError):
            pw.publish("o/r", self.source, url=str(self.remote), identity=("t", "someone@example.com"))
        self.assertEqual(self.show("Home.md"), b"first page\n")


if __name__ == "__main__":
    unittest.main()
