# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, keyboard shortcuts: the offline check (ROADMAP P5.50)."""
import unittest

from tools.qa import adblock_shortcuts_check as sc


class StepTests(unittest.TestCase):
    def test_the_boxes(self):
        self.assertEqual(sc.set_problems({"zapper": "Ctrl+Alt+Z", "javascript": "Ctrl+Alt+J", "picker": ""}), [])
        self.assertEqual(len(sc.set_problems({"zapper": "Ctrl+Z"})), 2)

    def test_the_page(self):
        self.assertEqual(sc.page_problems("zapper", {"title": "script ran", "zapped": True}, script=True,
                                          zapped=True), [])
        self.assertEqual(sc.page_problems("off", {"title": "no script"}, script=False), [])
        self.assertEqual(sc.page_problems("unset", {"title": "script ran", "keys": ["KeyQ", "KeyZ"]}, script=True,
                                          page_keys=["KeyQ", "KeyZ"]), [])
        found = sc.page_problems("zapper", {"title": "no script", "zapped": False, "keys": []}, script=True,
                                 zapped=True, page_keys=["KeyQ"])
        self.assertEqual(len(found), 3)

    def test_the_test_page(self):
        self.assertIn('id="zap-me"', sc.PAGE)
        self.assertIn("document.title = 'script ran'", sc.PAGE)


if __name__ == "__main__":
    unittest.main()
