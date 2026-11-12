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


if __name__ == "__main__":
    unittest.main()
