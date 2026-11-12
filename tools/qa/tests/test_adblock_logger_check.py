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

    def test_the_page(self):
        html = lc.page_html("ads.example")
        self.assertIn('src="http://ads.example/ad.png"', html)
        self.assertIn(f'src="http://{lc.PLAIN_HOST}/pic.png"', html)


if __name__ == "__main__":
    unittest.main()
