# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, per-site switch: the offline check (ROADMAP P5.16)."""
import json
import unittest

from tools.qa import adblock_site_switch_check as sc


class SettingTests(unittest.TestCase):
    def test_site_mode_allows_ads_on_the_test_host_through_the_settings_handler(self):
        js = sc.settings_call("site")
        self.assertTrue(js.startswith("chrome.send('setCategoryPermissionForPattern', "))
        args = json.loads(js[js.index("["):js.rindex("]") + 1])
        self.assertEqual(args, [sc.SITE_PATTERN, "", "ads", "allow", False])

    def test_everywhere_mode_sets_the_default(self):
        js = sc.settings_call("everywhere")
        self.assertEqual(json.loads(js[js.index("["):js.rindex("]") + 1]), ["ads", "allow"])
        self.assertIn("setDefaultValueForContentType", js)

    def test_none_and_restart_change_nothing(self):
        self.assertIsNone(sc.settings_call("none"))
        self.assertIsNone(sc.settings_call("restart"))

    def test_the_site_pattern_covers_every_port_of_the_test_host(self):
        # the restart run gets a new server port, so the choice must not be tied to one
        self.assertEqual(sc.SITE_PATTERN, "127.0.0.1")


class LabelTests(unittest.TestCase):
    def test_settings_page_says_what_the_switch_does(self):
        text = "Ads and trackers\nAds and many trackers are blocked before they load\nBlock ads and trackers\n"
        self.assertEqual(sc.label_problems(text), [])

    def test_upstream_intrusive_ads_wording_is_a_problem(self):
        text = "Intrusive ads\nAds are blocked on sites known to show intrusive or misleading ads\n"
        found = sc.label_problems(text)
        self.assertTrue(found)
        self.assertTrue(any("Intrusive ads" in p for p in found))


class VerdictTests(unittest.TestCase):
    def run_result(self, loaded, errors):
        return {"ok": True, "page": {"attempts": 10, "loaded": loaded, "errors": errors}}

    def test_blocked_and_allowed_runs(self):
        self.assertEqual(sc.problems("none", self.run_result(0, 10)), [])
        self.assertTrue(sc.problems("none", self.run_result(10, 0)))
        for mode in ("site", "everywhere", "restart"):
            self.assertEqual(sc.problems(mode, self.run_result(10, 0)), [], mode)
            self.assertTrue(sc.problems(mode, self.run_result(0, 10)), mode)

    def test_a_run_without_a_page_result_fails(self):
        self.assertTrue(sc.problems("site", {"ok": False, "error": "timed out"}))


if __name__ == "__main__":
    unittest.main()
