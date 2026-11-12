# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "My rules": the offline check (ROADMAP P5.44)."""
import unittest

from tools.qa import adblock_rules_check as rc


class PageTests(unittest.TestCase):
    def test_the_page_and_the_rules(self):
        html = rc.page_html("ads.example")
        self.assertIn('src="http://ads.example/ad.png"', html)
        self.assertIn(f'src="http://{rc.OTHER_HOST}/lib.js"', html)
        self.assertIn("window.inline = 'ran'", html)
        text = rc.rules_text("ads.example", noop=False)
        self.assertIn(f"{rc.PAGE_HOST} ads.example * allow\n", text)
        self.assertNotIn("noop", text)
        self.assertIn(f"{rc.PAGE_HOST} * 3p-script noop\n", rc.rules_text("ads.example", noop=True))
        self.assertNotIn(rc.OTHER_HOST, rc.rules_text("ads.example", noop=True))
        self.assertIn(f"{rc.PAGE_HOST} {rc.OTHER_HOST} * allow\n",
                      rc.rules_text("ads.example", noop=True, allow=True))


class ProblemsTests(unittest.TestCase):
    def test_each_step_as_wanted(self):
        self.assertEqual(rc.problems_for("none", {"other": True, "ad": False, "inline": True, "own": True},
                                         "ads.example"), [])
        self.assertEqual(rc.problems_for("rules", {"other": False, "ad": True, "inline": False, "own": True},
                                         "ads.example"), [])
        self.assertEqual(rc.problems_for("noop", {"other": True, "ad": True, "inline": False, "own": True},
                                         "ads.example"), [])
        self.assertEqual(rc.problems_for("switch", {"other": False, "ad": True, "inline": False, "own": True},
                                         "ads.example"), [])
        self.assertEqual(rc.problems_for("allow", {"other": True, "ad": True, "inline": False, "own": True},
                                         "ads.example"), [])

    def test_what_differs_is_named(self):
        found = rc.problems_for("rules", {"other": True, "ad": False, "inline": True, "own": False}, "ads.example")
        self.assertEqual(len(found), 4)
        self.assertIn("rules: the page's own script ran", found)


if __name__ == "__main__":
    unittest.main()
