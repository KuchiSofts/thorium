# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import unittest

from tools.credits import contributors

START, END = "<!-- contributors:start -->", "<!-- contributors:end -->"


class ContributorsTests(unittest.TestCase):
    def test_render_orders_and_excludes_bots(self):
        data = [
            {"type": "User", "login": "a", "contributions": 5},
            {"type": "User", "login": "b", "contributions": 9},
            {"type": "Anonymous", "name": "Zed", "contributions": 5},
            {"type": "Bot", "login": "x[bot]", "contributions": 50},
        ]
        lines = contributors.render_contributors(data).strip().splitlines()
        self.assertEqual(lines, [
            "- [@b](https://github.com/b) (9 commits)",
            "- [@a](https://github.com/a) (5 commits)",
            "- Zed (5 commits)",
        ])
        self.assertNotIn("x[bot]", contributors.render_contributors(data))

    def test_replace_section_idempotent(self):
        text = f"before\n{START}\nold\n{END}\nafter\n"
        once = contributors.replace_section(text, "- new\n")
        twice = contributors.replace_section(once, "- new\n")
        self.assertEqual(once, twice)
        self.assertTrue(once.startswith("before\n") and once.endswith("after\n"))
        self.assertIn("- new", once)
        self.assertNotIn("old", once)

    def test_replace_section_requires_markers(self):
        with self.assertRaises(ValueError):
            contributors.replace_section("no markers here", "- x\n")


if __name__ == "__main__":
    unittest.main()
