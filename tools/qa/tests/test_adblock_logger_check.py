# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the logger: the offline check (ROADMAP P5.42)."""
import unittest

from tools.qa import adblock_logger_check as lc


class RowsTests(unittest.TestCase):
    def test_both_images_in_their_kind(self):
        rows = [{"kind": "blocked", "url": "http://ads.example/ad.png", "button": "Allow"},
                {"kind": "allowed", "url": f"http://{lc.PLAIN_HOST}/pic.png", "button": "Block"}]
        self.assertEqual(lc.rows_problems(rows, "ads.example"), [])

    def test_a_missing_or_wrong_kind_is_named(self):
        rows = [{"kind": "allowed", "url": "http://ads.example/ad.png", "button": "Block"}]
        self.assertEqual(len(lc.rows_problems(rows, "ads.example")), 2)

    def test_the_filter_shows_one_kind(self):
        self.assertEqual(lc.filter_problems([{"kind": "allowed"}]), [])
        self.assertEqual(len(lc.filter_problems([{"kind": "allowed"}, {"kind": "blocked"}])), 1)
        self.assertEqual(len(lc.filter_problems([])), 1)

    def test_why_names_the_rule(self):
        self.assertEqual(lc.why_problems("blocked", "Blocked by ||ads.example^ (EasyList)", "ads.example"), [])
        allowed = f"Let through by @@||ads.example^$domain={lc.PAGE_HOST} (My filters)"
        self.assertEqual(lc.why_problems("allowed", allowed, "ads.example"), [])
        self.assertEqual(lc.why_problems("allowed", allowed + ", which wins over ||ads.example^ (EasyList)",
                                         "ads.example"), [])
        for step, text in (("blocked", "Looking it up..."), ("blocked", "Blocked by a rule that is not in the lists"),
                           ("allowed", "No rule matched")):
            self.assertEqual(len(lc.why_problems(step, text, "ads.example")), 1, text)

    def test_the_page(self):
        html = lc.page_html("ads.example")
        self.assertIn('src="http://ads.example/ad.png"', html)
        self.assertIn(f'src="http://{lc.PLAIN_HOST}/pic.png"', html)
        self.assertIn('src="/first.png"', html)


class PartyAndWordsTests(unittest.TestCase):
    def rows(self, *urls_and_parties):
        return [{"kind": "allowed", "url": u, "party": p, "button": ""} for u, p in urls_and_parties]

    def test_party(self):
        ad, plain = ("http://ads.example/ad.png", "3p"), (f"http://{lc.PLAIN_HOST}/pic.png", "3p")
        first = (lc.FIRST, "")
        self.assertEqual(lc.party_problems(self.rows(ad, plain), self.rows(first), "ads.example"), [])
        self.assertEqual(len(lc.party_problems(self.rows(ad), self.rows(first), "ads.example")), 1)
        self.assertEqual(len(lc.party_problems(self.rows(ad, plain, (lc.FIRST, "")), self.rows(first),
                                               "ads.example")), 1)
        self.assertEqual(len(lc.party_problems(self.rows(ad, plain), self.rows(ad), "ads.example")), 1)

    def test_words(self):
        ad, plain, first = ("http://ads.example/ad.png", "3p"), (f"http://{lc.PLAIN_HOST}/pic.png", "3p"), (lc.FIRST, "")
        self.assertEqual(lc.words_problems(self.rows(ad, first), self.rows(first), "ads.example"), [])
        self.assertEqual(len(lc.words_problems(self.rows(ad, first, plain), self.rows(first), "ads.example")), 1)
        self.assertEqual(len(lc.words_problems(self.rows(ad), self.rows(ad), "ads.example")), 2)

    def test_the_scripts(self):
        self.assertIn("new Event(\"input\")", lc.show("log-filter", "png"))
        self.assertIn("new Event(\"change\")", lc.show("log-party", "third"))


if __name__ == "__main__":
    unittest.main()
