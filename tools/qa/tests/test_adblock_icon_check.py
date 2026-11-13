# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the address bar's icon opens the blocker's menu: the offline check (ROADMAP P5.52)."""
import unittest

from tools.qa import adblock_icon_check as ic


class StepTests(unittest.TestCase):
    def test_the_menu_opened(self):
        self.assertEqual(ic.menu_problems("icon", "clicked", ["http://a.test/", ic.MENU_URL]), [])

    def test_what_went_wrong_is_named(self):
        self.assertIn("icon:", ic.menu_problems("no icon", "", [])[0])
        self.assertIn("could not be clicked", ic.menu_problems("icon", "", [])[0])
        self.assertIn("did not open", ic.menu_problems("icon", "clicked", ["http://a.test/"])[0])

    def test_the_ad_image(self):
        self.assertIn("http://ads.example/ad.png", ic.ad_image("ads.example"))


if __name__ == "__main__":
    unittest.main()
