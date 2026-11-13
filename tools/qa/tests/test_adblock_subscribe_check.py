# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, subscribe links: the offline check (ROADMAP P5.53)."""
import unittest

from tools.qa import adblock_subscribe_check as sc


class PageTests(unittest.TestCase):
    def test_the_links(self):
        html = sc.page_html(8123)
        self.assertIn('href="abp:subscribe?location=http%3A%2F%2F127.0.0.1%3A8123%2Flists%2Fcheck.txt'
                      '&title=Check%20list"', html)
        self.assertIn('href="https://subscribe.adblockplus.org/?location=', html)


class AskTests(unittest.TestCase):
    def test_the_question(self):
        url = sc.list_url(8123, "check")
        seen = {"shown": True, "title": 'Add the filter list "Check list"?', "url": url}
        self.assertEqual(sc.ask_problems("abp", seen, "Check list", url), [])

    def test_what_differs_is_named(self):
        self.assertEqual(len(sc.ask_problems("abp", {"shown": False}, "Check list", "x")), 1)
        seen = {"shown": True, "title": "Add this filter list?", "url": "y"}
        self.assertEqual(len(sc.ask_problems("abp", seen, "Check list", "x")), 2)


if __name__ == "__main__":
    unittest.main()
