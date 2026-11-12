# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import base64
import unittest
import urllib.parse

from tools.qa import adblock_urlskip_check as uc

LISTS = """! thoron-list: ublock-privacy
! ||commented.example^$urlskip=?url
||far.example/*^u=http$doc,urlskip=?u
/^https?:\\/\\/x\\.example\\//$doc,urlskip=?u
||plain.example^$urlskip=?url
||second.example^$urlskip=?to
||coded.example/out/go?link=$urlskip=?link -base64
||other.example/r?t=$doc,urlskip=?x -base64
"""


class CasesTests(unittest.TestCase):
    def test_the_first_simple_rule_of_each_kind_is_taken(self):
        found = uc.cases(LISTS)
        self.assertEqual(found["param"], {"host": "plain.example", "path": "/", "name": "url", "base64": False})
        self.assertEqual(found["base64"], {"host": "coded.example", "path": "/out/go", "name": "link", "base64": True})

    def test_lists_without_such_rules_give_no_case(self):
        self.assertEqual(uc.cases("||ads.example^\n||x.example^$doc\n"), {})

    def test_the_redirector_address_carries_the_destination(self):
        found = uc.cases(LISTS)
        url = uc.redirector_url(found["param"], "http://dest.test/landed.html?case=param")
        self.assertEqual(url, "http://plain.example/?url=http%3A%2F%2Fdest.test%2Flanded.html%3Fcase%3Dparam")
        url = uc.redirector_url(found["base64"], "http://dest.test/landed.html?case=base64")
        parts = urllib.parse.urlsplit(url)
        self.assertEqual((parts.netloc, parts.path), ("coded.example", "/out/go"))
        value = urllib.parse.parse_qs(parts.query)["link"][0]
        self.assertEqual(base64.b64decode(value).decode(), "http://dest.test/landed.html?case=base64")

    def test_the_hosts_to_send_to_the_local_server(self):
        self.assertEqual(uc.hosts(uc.cases(LISTS)), ["coded.example", "dest.test", "plain.example"])


class ProblemsTests(unittest.TestCase):
    SKIPPED = [("dest.test", "/landed.html?case=param", "GET")]
    VISITED = [("plain.example", "/?url=http%3A%2F%2Fdest.test%2Flanded.html%3Fcase%3Dparam", "GET")]

    def test_a_skip_that_happened(self):
        self.assertEqual(uc.problems("param", True, "plain.example", self.SKIPPED), [])

    def test_a_skip_that_did_not_happen(self):
        found = uc.problems("param", True, "plain.example", self.VISITED)
        self.assertEqual(len(found), 2)
        self.assertIn("redirector was asked", found[0])
        self.assertIn("not reached", found[1])

    def test_a_navigation_that_must_stay(self):
        self.assertEqual(uc.problems("param", False, "plain.example", self.VISITED), [])
        found = uc.problems("param", False, "plain.example", self.SKIPPED)
        self.assertEqual(len(found), 2)
        self.assertIn("was not asked", found[0])
        self.assertIn("sent on", found[1])

    def test_only_this_cases_own_landing_counts(self):
        other = [("dest.test", "/landed.html?case=base64", "GET")]
        self.assertEqual(len(uc.problems("param", True, "plain.example", other)), 1)

    def test_a_post_is_told_from_a_get(self):
        posted = [("plain.example", "/?url=x", "POST")]
        self.assertEqual(uc.problems("post", False, "plain.example", posted, method="POST"), [])
        self.assertEqual(len(uc.problems("post", False, "plain.example", self.VISITED, method="POST")), 1)

    def test_the_scenarios(self):
        self.assertEqual([s["name"] for s in uc.SCENARIOS], ["param", "base64", "post", "frame"])
        self.assertEqual([s["skipped"] for s in uc.SCENARIOS], [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
