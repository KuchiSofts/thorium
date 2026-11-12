# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the Settings section: the offline check (ROADMAP P5.38)."""
import unittest

from tools.qa import adblock_options_check as oc


class PageTests(unittest.TestCase):
    def test_the_page_has_what_each_setting_acts_on(self):
        html = oc.page_html("ad-banner")
        self.assertIn('<div class="ad-banner" id="generic">', html)
        self.assertIn("url(/check.woff2)", html)
        self.assertIn('<img src="/forbidden.png"', html)
        self.assertIn("document.title = 'script ran'", html)
        self.assertIn("report-uri /csp-report", oc.POLICY)


class SettingsTests(unittest.TestCase):
    def test_every_setting_as_wanted(self):
        got = {name: name == "badge" for name in oc.OPTIONS}
        self.assertEqual(oc.settings_problems("defaults", got, {"badge"}), [])

    def test_a_setting_that_reads_wrong_or_is_missing(self):
        got = {name: False for name in oc.OPTIONS if name != "webrtc"}
        got["prefetch"] = True
        found = oc.settings_problems("x", got, {"badge"})
        self.assertEqual(found, ["x: badge reads off", "x: prefetch reads on", "x: the setting webrtc is not on the page"])


class PageProblemsTests(unittest.TestCase):
    def test_as_wanted(self):
        seen = {"generic": "hidden", "font": True, "report": True}
        self.assertEqual(oc.page_problems("d", seen, hidden=True, font=True, report=True), [])

    def test_each_difference_is_named(self):
        seen = {"generic": "hidden", "font": True, "report": True}
        found = oc.page_problems("on", seen, hidden=False, font=False, report=False)
        self.assertEqual(found, ["on: the element of the generic rule is hidden, not shown",
                                 "on: the font was asked for", "on: the CSP report was sent"])


if __name__ == "__main__":
    unittest.main()
