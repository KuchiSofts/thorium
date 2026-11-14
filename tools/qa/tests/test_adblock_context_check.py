# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "Block element..." in the context menu: the offline check (ROADMAP P5.41)."""
import unittest

from tools.qa import adblock_context_check as cc


class RuleTests(unittest.TestCase):
    def test_a_rule_for_the_clicked_element_and_it_hidden(self):
        self.assertEqual(cc.rule_problems(f"{cc.PAGE_HOST}###promo-box\n", "hidden"), [])

    def test_no_rule_or_still_shown(self):
        found = cc.rule_problems("", "shown")
        self.assertEqual(len(found), 2)
        self.assertEqual(cc.rule_problems("other.test###promo-box\n", "hidden")[0][:7], "no rule")

    def test_the_page_has_the_element_and_the_item_is_named(self):
        self.assertIn('id="promo-box"', cc.PAGE)
        self.assertIn(cc.ITEM, cc.INVOKE)



class NewItemsTests(unittest.TestCase):
    def test_subscribe(self):
        asked = {"shown": True, "url": cc.LIST_URL}
        self.assertEqual(cc.subscribe_problems(["Back", "Subscribe to filter list…"], asked), [])
        self.assertEqual(len(cc.subscribe_problems(["Back"], asked)), 1)
        self.assertEqual(len(cc.subscribe_problems(["Subscribe to filter list"], {"shown": False})), 1)

    def test_frame(self):
        self.assertEqual(cc.frame_problems(f"{cc.FRAME_HOST}###in-frame\n"), [])
        self.assertEqual(len(cc.frame_problems(f"{cc.PAGE_HOST}###in-frame\n")), 1)

    def test_the_page_has_the_link_and_the_frame(self):
        self.assertIn('href="abp:subscribe?location=https%3A%2F%2Flists.example%2Fcheck.txt', cc.PAGE)
        self.assertIn(f'src="http://{cc.FRAME_HOST}/frame.html"', cc.PAGE)
        self.assertIn('id="in-frame"', cc.FRAME)
        self.assertIn("StartsWith('Subscribe to filter list')", cc.invoke_script(cc.SUBSCRIBE))


class LargeMediaTests(unittest.TestCase):
    def test_the_item_lets_the_video_through(self):
        names = ["Back", "Temporarily allow large media elements"]
        self.assertEqual(cc.large_media_problems(names, (1, 0), ([False, True], [False, True, False])), [])
        self.assertEqual(len(cc.large_media_problems(["Back"], (1, 0), ([], []))), 1)
        self.assertEqual(len(cc.large_media_problems(names, (1, 1), ([False, True], [False, True]))), 2)
        self.assertIn('src="/big.mp4"', cc.PAGE)


if __name__ == "__main__":
    unittest.main()
