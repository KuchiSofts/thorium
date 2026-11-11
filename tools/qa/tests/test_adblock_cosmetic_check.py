# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, scriptlets and hide rules: the offline check (ROADMAP P5.20)."""
import unittest

from tools.qa import adblock_cosmetic_check as cc

LISTS = """! thoron-list: easylist
##.a-adhesion
##.above-header-advert
###top-ad
##.x > .y
news.example##.ad-box
shop.example###promo
shop.example##.x > .y
! thoron-list: ublock-filters
shop.example##+js(set, adsOff, true)
video.example##+js(set-constant, canRunAds, false)
video.example##.banner
blog.example##+js(set, a.b.c, true)
blog.example##.side
other.example##+js(nowoif)
xxxtube.example##+js(set, ads, true)
xxxtube.example##.ad
"""


class CandidateTests(unittest.TestCase):
    def test_a_candidate_has_a_simple_scriptlet_rule_and_a_simple_hide_rule(self):
        found = cc.candidates(LISTS)
        self.assertEqual([c["host"] for c in found], ["shop.example", "video.example"])
        self.assertEqual(found[0], {"host": "shop.example", "property": "adsOff", "value": "true",
                                    "selector": "#promo", "generic": "a-adhesion", "late": "above-header-advert"})
        self.assertEqual(found[1]["selector"], ".banner")
        self.assertEqual(found[1]["value"], "false")

    def test_hosts_not_fit_for_a_report_are_skipped(self):
        self.assertNotIn("xxxtube.example", [c["host"] for c in cc.candidates(LISTS)])

    def test_lists_without_a_pair_give_nothing(self):
        self.assertEqual(cc.candidates("news.example##.ad-box\n"), [])

    def test_two_generic_class_rules_are_needed(self):
        one = "##.a-adhesion\nshop.example###promo\nshop.example##+js(set, adsOff, true)\n"
        self.assertEqual(cc.candidates(one), [])
        self.assertEqual(cc.generic_classes(LISTS), ["a-adhesion", "above-header-advert"])


class PageTests(unittest.TestCase):
    def test_the_page_reads_the_property_before_anything_else_and_holds_the_element(self):
        html = cc.page_html({"host": "shop.example", "property": "adsOff", "value": "true", "selector": "#promo",
                             "generic": "a-adhesion", "late": "above-header-advert"})
        self.assertLess(html.index("window.__early"), html.index('id="promo"'))
        self.assertIn('class="a-adhesion"', html)                 # there from the start
        self.assertNotIn('class="above-header-advert"', html)     # added by the page later
        self.assertIn('"above-header-advert"', html)
        self.assertIn('String(window["adsOff"])', html)
        self.assertIn('document.querySelector("#promo")', html)
        html = cc.page_html({"host": "v.example", "property": "p", "value": "false", "selector": ".banner",
                             "generic": "g", "late": "l"})
        self.assertIn('class="banner"', html)

    def test_the_parent_page_frames_the_candidate_host(self):
        self.assertIn('<iframe src="http://shop.example/check.html?frame=1"', cc.parent_html("shop.example"))


class WarmUpTests(unittest.TestCase):
    def test_the_warm_up_page_reports_nothing_and_frames_nothing(self):
        self.assertNotIn("/result", cc.WARM_HTML)
        self.assertNotIn("iframe", cc.WARM_HTML)
        self.assertNotIn("script", cc.WARM_HTML)


class LaunchTests(unittest.TestCase):
    def test_both_https_first_features_are_off_for_the_plain_http_test_page(self):
        self.assertIn("HttpsUpgrades", cc.NO_HTTPS_FIRST.split(","))
        self.assertIn("HttpsFirstBalancedModeAutoEnable", cc.NO_HTTPS_FIRST.split(","))


class VerdictTests(unittest.TestCase):
    C = {"host": "shop.example", "property": "adsOff", "value": "true", "selector": "#promo",
         "generic": "a-adhesion", "late": "above-header-advert"}
    ON = {"early": "true", "hidden": True, "generic": True, "late": True}
    OFF = {"early": "undefined", "hidden": False, "generic": False, "late": False}

    def test_with_blocking_on_the_scriptlet_ran_first_and_the_elements_are_hidden(self):
        self.assertEqual(cc.problems("native", self.C, self.ON), [])
        self.assertEqual(cc.problems("frame", self.C, self.ON), [])
        self.assertIn("scriptlet", cc.problems("native", self.C, dict(self.ON, early="undefined"))[0])
        self.assertIn("not hidden", cc.problems("native", self.C, dict(self.ON, hidden=False))[0])
        self.assertIn("generic", cc.problems("native", self.C, dict(self.ON, generic=False))[0])
        self.assertIn("added later", cc.problems("native", self.C, dict(self.ON, late=False))[0])

    def test_without_blocking_nothing_is_touched(self):
        for mode in ("control", "site-off"):
            self.assertEqual(cc.problems(mode, self.C, self.OFF), [], mode)
            for key, value in (("early", "true"), ("hidden", True), ("generic", True), ("late", True)):
                self.assertTrue(cc.problems(mode, self.C, dict(self.OFF, **{key: value})), (mode, key))

    def test_no_result_is_a_failure(self):
        self.assertTrue(cc.problems("native", self.C, None))


if __name__ == "__main__":
    unittest.main()
