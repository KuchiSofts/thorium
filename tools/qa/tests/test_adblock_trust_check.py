# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, trust for My filters: the offline check (ROADMAP P5.48)."""
import unittest

from tools.qa import adblock_trust_check as tc


class StepTests(unittest.TestCase):
    def test_each_step_as_wanted(self):
        self.assertEqual(tc.step_problems("off", False, {"plain": "yes", "trusted": None}), [])
        self.assertEqual(tc.step_problems("on", True, {"plain": "yes", "trusted": "yes"}), [])

    def test_what_differs_is_named(self):
        self.assertEqual(len(tc.step_problems("off", False, {"plain": None, "trusted": "yes"})), 2)
        self.assertEqual(len(tc.step_problems("on", True, {"plain": "yes", "trusted": None})), 1)

    def test_the_filters(self):
        self.assertIn(f"{tc.PAGE_HOST}##+js(trusted-set-local-storage-item, thoron-trusted, yes)", tc.MY_FILTERS)
        self.assertIn(f"{tc.PAGE_HOST}##+js(set-local-storage-item, thoron-plain, yes)", tc.MY_FILTERS)


if __name__ == "__main__":
    unittest.main()
