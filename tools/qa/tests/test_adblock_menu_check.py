# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the toolbar menu and the element picker: the offline check (ROADMAP P5.31)."""
import struct
import unittest

from tools.qa import adblock_menu_check as mc

LISTS = """! thoron-list: easylist
||xxxads.example^
||ads.example^
##.adsbygoogle
##.promo-card
"""


class SetupTests(unittest.TestCase):
    def test_the_ad_host_and_a_generic_rule_come_from_easylist(self):
        self.assertEqual(mc.ad_host(LISTS), "ads.example")
        self.assertEqual(mc.generic_class(LISTS), "adsbygoogle")
        self.assertIsNone(mc.generic_class("! thoron-list: easylist\n##.x:has(y)\n"))

    def test_the_page_has_everything_the_steps_need(self):
        html = mc.page_html("ads.example", "adsbygoogle")
        for part in ['id="pick-target"', 'id="zap-me"', 'class="adsbygoogle"', "http://ads.example/banner.gif",
                     "/font.css", "/sound.wav", "window.report"]:
            self.assertIn(part, html)

    def test_the_sound_is_a_real_wav_larger_than_the_media_limit(self):
        data = mc.wav_bytes()
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:16], b"WAVEfmt ")
        self.assertEqual(struct.unpack("<I", data[4:8])[0], len(data) - 8)
        self.assertGreater(len(data), mc.MEDIA_LIMIT)


class ProblemsTests(unittest.TestCase):
    GOOD_MENU = {"site": mc.PAGE_HOST, "power": "true", "pageCount": 1, "sites": [["ads.example", 1]],
                 "share": "(25%)", "domains": "1 of 2"}

    def test_the_menu_must_name_the_site_and_count_the_ad(self):
        self.assertEqual(mc.menu_problems(self.GOOD_MENU, "ads.example"), [])
        found = mc.menu_problems(dict(self.GOOD_MENU, pageCount=0, sites=[]), "ads.example")
        self.assertEqual(len(found), 2)
        found = mc.menu_problems(dict(self.GOOD_MENU, site="other.test"), "ads.example")
        self.assertIn("names", found[0])
        found = mc.menu_problems(dict(self.GOOD_MENU, share="", domains="2 of 2"), "ads.example")
        self.assertEqual(len(found), 2)

    def test_each_switch_has_its_effect_and_only_while_on(self):
        on = {"fonts": {"font": False}, "media": {"sound": "error"}, "cosmetic": {"generic": "shown"},
              "power": {"ad": True}}
        off = {"fonts": {"font": True}, "media": {"sound": "loaded"}, "cosmetic": {"generic": "hidden"},
               "power": {"ad": False}}
        for name in on:
            self.assertEqual(mc.switch_problems(name, True, on[name]), [], name)
            self.assertEqual(mc.switch_problems(name, False, off[name]), [], name)
            self.assertTrue(mc.switch_problems(name, True, off[name]), name)
            self.assertTrue(mc.switch_problems(name, False, on[name]), name)

    def test_the_picker_must_add_a_rule_for_the_site_that_hides_the_element(self):
        self.assertEqual(mc.picker_problems(f"! mine\n{mc.PAGE_HOST}##.promo-card\n", "hidden"), [])
        found = mc.picker_problems("", "shown")
        self.assertEqual(len(found), 2)
        found = mc.picker_problems("other.test##.promo-card\n", "hidden")
        self.assertIn("no rule", found[0])

    def test_blocked_ads_must_take_no_space(self):
        self.assertEqual(mc.collapse_problems({"box": 0, "frame": 0}), [])
        self.assertEqual(len(mc.collapse_problems({"box": 300, "frame": 0})), 1)
        self.assertEqual(len(mc.collapse_problems({})), 2)

    def test_the_zapper_must_take_the_element_out(self):
        self.assertEqual(mc.zapper_problems({"zapped": True, "kept": True}), [])
        self.assertEqual(len(mc.zapper_problems({"zapped": False, "kept": True})), 1)
        self.assertEqual(len(mc.zapper_problems({"zapped": True, "kept": False})), 1)


if __name__ == "__main__":
    unittest.main()
