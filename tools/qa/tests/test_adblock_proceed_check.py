# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, opening a page strict blocking stopped: the offline check (ROADMAP P5.49)."""
import unittest

from tools.qa import adblock_proceed_check as pc

HOST = "bad.example"


class StepTests(unittest.TestCase):
    def test_each_step_as_wanted(self):
        self.assertEqual(pc.step_problems("blocked", pc.BLOCKED_TITLE, True, {}, HOST), [])
        self.assertEqual(pc.step_problems("now", "plain", False, {}, HOST), [])
        self.assertEqual(pc.step_problems("other", pc.BLOCKED_TITLE, True, {}, HOST), [])
        self.assertEqual(pc.step_problems("always", "plain", False, {HOST: ["no-strict"]}, HOST), [])

    def test_what_differs_is_named(self):
        self.assertEqual(len(pc.step_problems("now", pc.BLOCKED_TITLE, True, {HOST: ["no-strict"]}, HOST)), 3)
        self.assertEqual(len(pc.step_problems("always", "plain", False, {}, HOST)), 1)
        self.assertEqual(len(pc.step_problems("blocked", "plain", None, {}, HOST)), 2)


if __name__ == "__main__":
    unittest.main()
