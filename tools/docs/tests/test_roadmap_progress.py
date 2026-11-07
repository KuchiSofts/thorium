# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import unittest

from tools.docs import roadmap_progress as rp

ROADMAP = """# Roadmap
**Last updated:** 2026-11-07

## P0 - Foundation
- [x] **P0.1** Set up the repo - *Role:* Owner · *Depends:* - · *Done when:* done · ✅ 2026-11-07
- [ ] **P0.2** Write the docs - *Role:* Docs · *Depends:* P0.1 · *Done when:* written · 🔄

## P1 - Build environment
- [ ] **P1.1** Toolchain - *Role:* Release · *Depends:* P0 · *Done when:* builds
- [ ] **P1.2** Blocked thing - *Role:* Release · *Depends:* P1.1 · *Done when:* x · ⛔ waiting

### Security (S)
- [x] **S.1** Audit - *Role:* Security · *Depends:* - · *Done when:* y · ✅ 2026-11-07
"""


class RoadmapProgressTests(unittest.TestCase):
    def test_github_slug_matches_github_rules(self):
        self.assertEqual(rp.github_slug("P0 - Foundation"), "p0---foundation")
        self.assertEqual(rp.github_slug("P3 - Updater v1 + Import"), "p3---updater-v1--import")
        self.assertEqual(rp.github_slug("Quality & performance (Q)"), "quality--performance-q")
        self.assertEqual(rp.github_slug("16. Owner decisions log (2026-11-07)"), "16-owner-decisions-log-2026-11-07")

    def test_parse_sections_tasks_and_states(self):
        sections = rp.parse_roadmap(ROADMAP)
        self.assertEqual([s["title"] for s in sections], ["P0 - Foundation", "P1 - Build environment", "Security (S)"])
        p0 = sections[0]["tasks"]
        self.assertEqual([(t["id"], t["title"], t["state"]) for t in p0],
                         [("P0.1", "Set up the repo", "done"), ("P0.2", "Write the docs", "in progress")])
        self.assertEqual(sections[1]["tasks"][1]["state"], "blocked")

    def test_render_has_overall_and_per_section_progress(self):
        block = rp.render(rp.parse_roadmap(ROADMAP), last_updated="2026-11-07")
        self.assertIn("2 of 5 tasks done (40%)", block)
        self.assertIn("[P0 - Foundation](ROADMAP.md#p0---foundation)", block)
        self.assertIn("1/2", block)
        self.assertIn("- [ ] **P0.2** Write the docs", block)   # full task list
        self.assertIn("P1.1", block.split("What's next")[1])   # next open tasks are listed

    def test_update_readme_is_idempotent_and_detects_staleness(self):
        readme = "# Title\n<!-- roadmap:start -->\nold\n<!-- roadmap:end -->\nfooter\n"
        once = rp.update_readme(readme, "NEW BLOCK\n")
        self.assertEqual(rp.update_readme(once, "NEW BLOCK\n"), once)
        self.assertTrue(once.startswith("# Title\n") and once.endswith("footer\n"))
        self.assertTrue(rp.is_stale(readme, "NEW BLOCK\n"))
        self.assertFalse(rp.is_stale(once, "NEW BLOCK\n"))

    def test_update_readme_requires_markers(self):
        with self.assertRaises(ValueError):
            rp.update_readme("no markers", "x")

    def test_badge_region_updated_when_present(self):
        sections = rp.parse_roadmap(ROADMAP)
        nl = chr(10)
        readme = nl.join(["<!-- progress-badge:start -->", "old", "<!-- progress-badge:end -->",
                          "<!-- roadmap:start -->", "<!-- roadmap:end -->", ""])
        block, badge = rp.render(sections, "2026-11-07"), rp.render_badge(sections)
        out = rp.update_readme(readme, block, badge)
        self.assertIn("roadmap-40%25", out)
        self.assertNotIn("old", out)
        self.assertFalse(rp.is_stale(out, block, badge))


if __name__ == "__main__":
    unittest.main()
