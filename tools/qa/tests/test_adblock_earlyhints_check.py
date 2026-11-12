# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, preloads announced by "103 Early Hints": the offline check (ROADMAP P5.28)."""
import unittest

from tools.qa import adblock_earlyhints_check as ec

LISTS = """! thoron-list: easylist
||xxxads.example^
||ads.example/path^
||track.example^$image
||ads.example^
||second.example^
! thoron-list: ublock-filters
||other.example^
"""


class CasesTests(unittest.TestCase):
    def test_the_first_plain_host_rule_of_easylist_is_the_ad_host(self):
        self.assertEqual(ec.ad_host(LISTS), "ads.example")
        self.assertIsNone(ec.ad_host("! thoron-list: easylist\n||x.example^$script\n"))

    def test_the_hint_names_both_preloads(self):
        hint = ec.early_hints(f"http://ads.example{ec.AD_PATH}", f"http://{ec.PLAIN_HOST}{ec.PLAIN_PATH}")
        self.assertTrue(hint.startswith(b"HTTP/1.1 103 Early Hints\r\n"))
        self.assertIn(b"Link: <http://ads.example/early.js>; rel=preload; as=script\r\n", hint)
        self.assertIn(f"Link: <http://{ec.PLAIN_HOST}/early.css>; rel=preload; as=style\r\n".encode(), hint)
        self.assertTrue(hint.endswith(b"\r\n\r\n"))


class ProblemsTests(unittest.TestCase):
    def test_with_blocking_on_only_the_ad_preload_is_not_made(self):
        self.assertEqual(ec.problems(True, {"ads.example": False, ec.PLAIN_HOST: True, "page": True}, "ads.example"), [])
        found = ec.problems(True, {"ads.example": True, ec.PLAIN_HOST: True, "page": True}, "ads.example")
        self.assertEqual(found, ["the preload from the ad host was made"])
        found = ec.problems(True, {"ads.example": False, ec.PLAIN_HOST: False, "page": True}, "ads.example")
        self.assertEqual(found, ["the plain preload was not made"])

    def test_with_blocking_off_both_are_made(self):
        self.assertEqual(ec.problems(False, {"ads.example": True, ec.PLAIN_HOST: True, "page": True}, "ads.example"), [])
        found = ec.problems(False, {"ads.example": False, ec.PLAIN_HOST: True, "page": True}, "ads.example")
        self.assertEqual(found, ["the preload from the ad host was not made, though blocking is off"])

    def test_the_page_must_have_loaded(self):
        found = ec.problems(True, {"ads.example": False, ec.PLAIN_HOST: True, "page": False}, "ads.example")
        self.assertEqual(found, ["the page itself did not load"])


if __name__ == "__main__":
    unittest.main()
