# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the list viewer: the offline check (ROADMAP P5.55)."""
import unittest

from tools.qa import adblock_viewer_check as vc


class StepTests(unittest.TestCase):
    def test_builtin(self):
        seen = {"open": True, "title": "EasyList", "rules": 60000, "count": "61,234 lines",
                "about": "Expires: 6 days (update frequency)  |  Last modified: x"}
        self.assertEqual(vc.builtin_problems(seen), [])
        self.assertEqual(len(vc.builtin_problems({"open": False})), 1)
        self.assertEqual(len(vc.builtin_problems({**seen, "rules": 3, "count": "Loading...", "about": ""})), 3)
        self.assertEqual(len(vc.builtin_problems({**seen, "more": True})), 1)

    def test_find(self):
        seen = {"count": "120 of 61,234 lines", "every": True}
        self.assertEqual(vc.find_problems(seen, "61,234 lines"), [])
        self.assertEqual(len(vc.find_problems({**seen, "every": False}, "61,234 lines")), 1)
        self.assertEqual(len(vc.find_problems({**seen, "count": "0 of 61,234 lines"}, "61,234 lines")), 1)
        self.assertEqual(len(vc.find_problems(seen, "5 lines")), 1)
        self.assertEqual(len(vc.find_problems({"count": "61,234 lines"}, "61,234 lines")), 1)

    def test_added(self):
        seen = {"open": True, "title": "Viewer check", "text": vc.LIST_TEXT.rstrip("\n"),
                "about": "Expires: 2 days  |  Homepage: https://lists.example/"}
        self.assertEqual(vc.added_problems(seen), [])
        self.assertEqual(len(vc.added_problems({**seen, "text": "", "about": ""})), 2)

    def test_refused(self):
        self.assertEqual(vc.refused_problems([None, None, None]), [])
        self.assertEqual(len(vc.refused_problems([None, "x", None])), 1)

    def test_scripts(self):
        self.assertIn('"easylist"', vc.view("easylist"))
        self.assertIn('"doubleclick"', vc.read_viewer("doubleclick"))
        self.assertTrue(vc.list_url(8123).endswith("/lists/viewer.txt"))


if __name__ == "__main__":
    unittest.main()
