# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the theme of its pages: the offline check (ROADMAP P5.59)."""
import unittest

from tools.qa import adblock_theme_check as tc


class ColourTests(unittest.TestCase):
    def test_as_wanted(self):
        self.assertEqual(tc.colour_problems("dark", "menu", {"theme": "dark", "accent": tc.DARK}, tc.DARK, "dark"), [])
        self.assertEqual(tc.colour_problems("auto", "menu", {"theme": "", "accent": tc.LIGHT}, tc.LIGHT, ""), [])

    def test_what_differs_is_named(self):
        found = tc.colour_problems("dark", "settings", {"theme": "", "accent": tc.LIGHT}, tc.DARK, "dark")
        self.assertEqual(len(found), 2)
        self.assertIn("is light, not dark", found[0])

    def test_the_pages(self):
        self.assertEqual(set(tc.PAGES), {"settings", "menu"})
        self.assertIn("data-theme", tc.READ)


if __name__ == "__main__":
    unittest.main()
