# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, pop-ups: the offline check (ROADMAP P5.36)."""
import unittest

from tools.qa import adblock_popup_check as pc

LISTS = """! thoron-list: ublock-filters
||early.example^$popup
! thoron-list: easylist
||ads.example^
||script.example^$popup,third-party
||pop.example^$popup
||second.example^$popup
"""


class HostTests(unittest.TestCase):
    def test_the_first_plain_popup_host_rule_of_easylist(self):
        self.assertEqual(pc.popup_host(LISTS), "pop.example")
        self.assertIsNone(pc.popup_host("! thoron-list: easylist\n||x.example^\n"))

    def test_the_page_opens_the_ad_and_the_plain_host(self):
        html = pc.page_html("pop.example")
        self.assertIn("window.open('http://pop.example/window')", html)
        self.assertIn("w.location.href = 'http://pop.example/later'", html)
        self.assertIn('href="http://pop.example/link" target="_blank"', html)
        self.assertIn(f"window.open('http://{pc.PLAIN_HOST}/window.html')", html)
        self.assertNotIn("AD/", html)
        self.assertNotIn("PLAIN/", html)


class ProblemsTests(unittest.TestCase):
    def good(self) -> dict:
        return {"ad": "null", "blank": "opened", "leftover": [], "count": 3, "plain": "opened",
                "switch_plain": "null", "asked": [(pc.PLAIN_HOST, "/window.html")]}

    def test_everything_as_it_should_be(self):
        self.assertEqual(pc.native_problems(self.good(), "pop.example"), [])

    def test_each_way_to_the_ad_host_is_named(self):
        seen = self.good()
        seen["asked"] += [("pop.example", "/window"), ("pop.example", "/link"), ("pop.example", "/later")]
        found = pc.native_problems(seen, "pop.example")
        self.assertEqual(len(found), 3)
        self.assertIn("the ad window reached the ad host", found)
        self.assertIn("the blank window sent to the ad reached the ad host", found)

    def test_a_window_left_open_and_a_short_count(self):
        seen = self.good()
        seen["leftover"] = ["about:blank"]
        seen["count"] = 2
        found = pc.native_problems(seen, "pop.example")
        self.assertEqual(found, ["windows left open: ['about:blank']", "the menu counts 2 blocked on the page, not 3"])

    def test_the_plain_window_and_the_switch(self):
        seen = self.good()
        seen["plain"] = "null"
        seen["switch_plain"] = "opened"
        seen["asked"] = [(pc.PLAIN_HOST, "/link.html")]
        found = pc.native_problems(seen, "pop.example")
        self.assertEqual(len(found), 3)
        self.assertIn("the plain window did not open", found)
        self.assertIn("with no pop-ups on, the plain link opened a window", found)

    def test_with_blocking_off_or_ads_allowed_the_ad_window_opens(self):
        self.assertEqual(pc.opened_problems({"ad": "opened", "asked": [("pop.example", "/window")]}, "pop.example"), [])
        self.assertEqual(len(pc.opened_problems({"ad": "null", "asked": []}, "pop.example")), 1)
        self.assertEqual(len(pc.opened_problems({"ad": "opened", "asked": []}, "pop.example")), 1)


if __name__ == "__main__":
    unittest.main()
