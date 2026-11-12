# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, `$uritransform`: the offline check (ROADMAP P5.26)."""
import unittest

from tools.qa import adblock_uritransform_check as uc

LISTS = r"""! thoron-list: ublock-filters
! ||commented.example/*adblock%3Dtrue$doc,uritransform=/adblock%3Dtrue/adblock%3Dfalse/
||regex.example/*x$doc,uritransform=/\/ref=[^\/?#]+//
||validate.example/*adblock%3Dtrue$doc,uritransform=/adblock%3Dtrue/adblock%3Dfalse/
||other.example/*check%3Dtrue$doc,uritransform=/check%3Dtrue/check%3Dfalse/
||news.example/_media/video.aspx$script,uritransform=/reklama=1/reklama=0/
"""


class CasesTests(unittest.TestCase):
    def test_the_first_plain_rule_of_each_kind_is_taken(self):
        found = uc.cases(LISTS)
        self.assertEqual(found["page"], {"host": "validate.example", "path": "/check", "from": "adblock%3Dtrue",
                                         "to": "adblock%3Dfalse"})
        self.assertEqual(found["script"], {"host": "news.example", "path": "/_media/video.aspx", "from": "reklama=1",
                                           "to": "reklama=0"})

    def test_a_rule_whose_pattern_differs_from_what_it_replaces_is_not_used(self):
        self.assertEqual(uc.cases("||x.example/*abc$doc,uritransform=/abd/abe/\n"), {})
        self.assertEqual(uc.cases("||ads.example^\n"), {})

    def test_the_addresses(self):
        found = uc.cases(LISTS)
        self.assertEqual(uc.address(found["page"], "from"), "http://validate.example/check?q=adblock%3Dtrue")
        self.assertEqual(uc.address(found["script"], "to"), "http://news.example/_media/video.aspx?reklama=0")
        self.assertEqual(uc.hosts(found), sorted(["validate.example", "news.example", uc.PAGE_HOST]))


class ProblemsTests(unittest.TestCase):
    def setUp(self):
        self.found = uc.cases(LISTS)
        self.page = self.found["page"]

    def test_a_page_whose_address_was_changed(self):
        seen = [("validate.example", "/check?q=adblock%3Dfalse")]
        self.assertEqual(uc.problems("page", self.page, True, seen, "http://validate.example/check?q=adblock%3Dfalse"), [])

    def test_a_page_that_was_asked_for_as_it_was(self):
        seen = [("validate.example", "/check?q=adblock%3Dtrue")]
        found = uc.problems("page", self.page, True, seen, "http://validate.example/check?q=adblock%3Dtrue")
        self.assertEqual(len(found), 3)
        self.assertIn("asked for as it was", found[0])
        self.assertEqual(uc.problems("page", self.page, False, seen, "http://validate.example/check?q=adblock%3Dtrue"), [])

    def test_with_blocking_off_nothing_may_change(self):
        seen = [("validate.example", "/check?q=adblock%3Dfalse")]
        found = uc.problems("page", self.page, False, seen, "http://validate.example/check?q=adblock%3Dfalse")
        self.assertEqual(len(found), 3)

    def test_a_script_must_also_have_run(self):
        script = self.found["script"]
        seen = [(uc.PAGE_HOST, "/page.html"), ("news.example", "/_media/video.aspx?reklama=0")]
        self.assertEqual(uc.problems("script", script, True, seen, "loaded"), [])
        self.assertEqual(uc.problems("script", script, True, seen, "blocked"), ["the script did not run"])

    def test_no_request_at_all(self):
        found = uc.problems("script", self.found["script"], True, [], None)
        self.assertEqual(len(found), 2)
        self.assertIn("never asked for", found[0])
        self.assertEqual(found[1], "the script did not run")


if __name__ == "__main__":
    unittest.main()
