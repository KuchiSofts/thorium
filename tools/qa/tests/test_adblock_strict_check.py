# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, strict blocking: the offline check (ROADMAP P5.37)."""
import unittest

from tools.qa import adblock_strict_check as sc

LISTS = """! thoron-list: easylist
||early.example^$doc
! thoron-list: ublock-badware
||bad.example^$script
||malware.example^$doc
||second.example^$document
||harm.example^$all
"""
HOSTS = {"host": "ads.example", "doc": "malware.example", "all": "harm.example"}


class HostsTests(unittest.TestCase):
    def test_the_first_doc_and_all_rules_of_the_badware_list(self):
        self.assertEqual(sc.page_hosts(LISTS), {"doc": "malware.example", "all": "harm.example"})
        self.assertEqual(sc.page_hosts("! thoron-list: easylist\n||x.example^$doc\n"), {})

    def test_the_addresses(self):
        urls = sc.cases(HOSTS)
        self.assertEqual(urls["doc"], "http://malware.example/page")
        self.assertEqual(urls["redirect"], f"http://{sc.PLAIN_HOST}/go")
        self.assertEqual(urls["onward"], f"http://ads.example/click?url=http%3A%2F%2F{sc.PLAIN_HOST}%2Flanding")


class ProblemsTests(unittest.TestCase):
    def good(self) -> dict:
        blocked = {"title": sc.BLOCKED_TITLE, "text": "the sites ads.example malware.example harm.example",
                   "links": []}
        return {"host": dict(blocked), "doc": dict(blocked), "all": dict(blocked), "plain": {"title": "plain"},
                "redirect": dict(blocked),
                "onward": dict(blocked, links=[f"http://{sc.PLAIN_HOST}/landing"]),
                "asked": [(sc.PLAIN_HOST, "/page"), (sc.PLAIN_HOST, "/go"), (sc.PLAIN_HOST, "/landing")]}

    def test_everything_as_it_should_be(self):
        self.assertEqual(sc.native_problems(self.good(), HOSTS), [])

    def test_an_opened_page_and_an_asked_host(self):
        seen = self.good()
        seen["doc"] = {"title": "plain"}
        seen["asked"].append(("harm.example", "/page"))
        found = sc.native_problems(seen, HOSTS)
        self.assertEqual(found, ["the doc page was opened (title 'plain')", "the all host was asked"])

    def test_the_blocked_page_must_name_the_site(self):
        seen = self.good()
        seen["host"]["text"] = "something else"
        self.assertEqual(sc.native_problems(seen, HOSTS),
                         ["the blocked host page does not name its site ads.example"])

    def test_redirects_and_the_onward_link(self):
        seen = self.good()
        seen["redirect"] = {"title": "plain"}
        seen["onward"]["links"] = []
        found = sc.native_problems(seen, HOSTS)
        self.assertIn("a redirect to a blocked host was followed", found)
        self.assertIn("the blocked redirector's page does not offer where it sends on to", found)
        seen = self.good()
        seen["asked"] = [(sc.PLAIN_HOST, "/page")]
        self.assertEqual(sc.native_problems(seen, HOSTS),
                         ["the link to where the redirector sends on to did not open it"])

    def test_with_blocking_off_every_page_opens(self):
        seen = {kind: {"title": "plain"} for kind in ("host", "doc", "all", "plain")}
        self.assertEqual(sc.opened_problems(seen, ("host", "doc", "all", "plain")), [])
        seen["all"] = {"title": sc.BLOCKED_TITLE}
        self.assertEqual(len(sc.opened_problems(seen, ("host", "doc", "all", "plain"))), 1)


if __name__ == "__main__":
    unittest.main()
