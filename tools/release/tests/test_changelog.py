# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Release notes generator (ROADMAP P2.13)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.release import changelog as cl


def git(repo, *args, env_name="Dev", env_mail="dev@users.noreply.github.com"):
    return subprocess.run(["git", "-c", f"user.name={env_name}", "-c", f"user.email={env_mail}",
                           "-c", "commit.gpgsign=false", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def commit(repo, subject, body="", author="Dev", name="f.txt"):
    p = Path(repo) / name
    p.write_text(p.read_text(encoding="utf-8") + subject + "\n" if p.exists() else subject + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    msg = subject + ("\n\n" + body if body else "")
    git(repo, "commit", "-q", "-m", msg, env_name=author, env_mail=f"{author}@users.noreply.github.com")
    return git(repo, "rev-parse", "HEAD")


class GroupingTests(unittest.TestCase):
    def test_prefixes_group_and_are_stripped(self):
        groups = cl.group_commits(["sec: close a hole", "fix: tab colours", "perf: faster start",
                                   "ui: new icon", "build: faster CI", "docs: guide", "Something else",
                                   "Merge pull request #9 from x/y"])
        self.assertEqual(groups["Security"], ["close a hole"])
        self.assertEqual(groups["Fixes"], ["tab colours"])
        self.assertEqual(groups["Performance"], ["faster start"])
        self.assertEqual(groups["User interface"], ["new icon"])
        self.assertEqual(groups["Build"], ["faster CI"])
        self.assertEqual(groups["Documentation"], ["guide"])
        self.assertEqual(groups["Other changes"], ["Something else"])
        self.assertNotIn("Merge pull request #9 from x/y", sum(groups.values(), []))

    def test_security_comes_first(self):
        self.assertEqual(cl.CATEGORIES[0], "Security")

    def test_issue_references(self):
        self.assertEqual(cl.issues(["Fixes #12", "closes #3 and fixes #12", "see #99"]), [3, 12])


class SeriesTests(unittest.TestCase):
    def test_added_removed_refreshed(self):
        old = {"other/a.patch": "A", "other/b.patch": "B", "other/c.patch": "C"}
        new = {"other/a.patch": "A", "other/b.patch": "B2", "other/d.patch": "D"}
        ch = cl.series_changes(old, new)
        self.assertEqual(ch, {"added": ["d.patch"], "removed": ["c.patch"], "refreshed": ["b.patch"]})


class SecurityTests(unittest.TestCase):
    def test_sorted_by_severity_then_cve(self):
        fixes = [{"cve": "CVE-2026-2", "severity": "Medium", "title": "m"},
                 {"cve": "CVE-2026-3", "severity": "Critical", "title": "c"},
                 {"cve": "CVE-2026-1", "severity": "High", "title": "h"}]
        self.assertEqual([f["cve"] for f in cl.sort_security(fixes)], ["CVE-2026-3", "CVE-2026-1", "CVE-2026-2"])

    def test_unknown_severity_is_refused(self):
        with self.assertRaises(cl.NotesError):
            cl.sort_security([{"cve": "CVE-1", "severity": "Spicy", "title": "x"}])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "thoron"
        self.up = root / "upstream"
        for r in (self.repo, self.up):
            r.mkdir()
            git(r, "init", "-q")
        self.base = commit(self.repo, "docs: start")
        commit(self.repo, "sec: refuse Google API keys", "Fixes #7")
        commit(self.repo, "fix: keep tab groups")
        self.up_base = commit(self.up, "M158 start", author="gz83")
        commit(self.up, "Refresh patches", author="gz83")
        commit(self.up, "Fix FFmpeg on Linux", author="Alex313031")
        commit(self.up, "Fix FFmpeg on ARM", author="Alex313031")

    def tearDown(self):
        self.tmp.cleanup()

    def notes(self, **kw):
        args = dict(version="158.0.8127.3000", chromium_old="156.0.8078.80", chromium_new="158.0.8127.30",
                    repo=self.repo, since=self.base, upstream=self.up, upstream_since=self.up_base,
                    series={"added": ["ks-x.patch"], "removed": ["GPC.patch"], "refreshed": []},
                    security=[{"cve": "CVE-2026-9", "severity": "High", "title": "Use after free in V8"}],
                    artifacts=["a" * 64 + "  thoron_AVX2_mini_installer.exe"])
        args.update(kw)
        return cl.render(**args)

    def test_sections_in_design_order(self):
        text = self.notes()
        order = ["# Thoron 158.0.8127.3000", "## Chromium", "## Thoron changes", "## Upstream Thorium",
                 "## Patches", "## Fixed issues", "## Downloads", "## Credits"]
        positions = [text.index(h) for h in order]
        self.assertEqual(positions, sorted(positions))

    def test_content(self):
        text = self.notes()
        self.assertIn("Chromium 156.0.8078.80 to 158.0.8127.30", text)
        self.assertIn("CVE-2026-9", text)
        self.assertIn("refuse Google API keys", text)
        self.assertLess(text.index("### Security"), text.index("### Fixes"))
        self.assertIn("#7", text)
        self.assertIn("ks-x.patch", text)
        self.assertIn("GPC.patch", text)
        self.assertIn("thoron_AVX2_mini_installer.exe", text)

    def test_upstream_commits_are_credited_by_author(self):
        text = self.notes()
        self.assertIn("Fix FFmpeg on Linux (Alex313031)", text)
        self.assertIn("Refresh patches (gz83)", text)
        self.assertIn("Alex313031 (2 commits)", text)

    def test_house_style_and_no_emails(self):
        text = self.notes(security=[{"cve": "CVE-1", "severity": "Low", "title": "a " + chr(0x2014) + " b"}])
        self.assertNotIn(chr(0x2014), text)
        self.assertNotIn(chr(0x2013), text)
        self.assertNotIn("@users.noreply", text)

    def test_cli_writes_the_notes(self):
        sec = Path(self.tmp.name) / "security.json"
        sec.write_text(json.dumps([{"cve": "CVE-2026-9", "severity": "High", "title": "x"}]), encoding="utf-8")
        out = Path(self.tmp.name) / "NOTES.md"
        rc = cl.main(["--version", "158.0.8127.3000", "--chromium-old", "156.0.8078.80", "--chromium-new",
                      "158.0.8127.30", "--repo", str(self.repo), "--since", self.base, "--security", str(sec),
                      "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertIn("CVE-2026-9", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
