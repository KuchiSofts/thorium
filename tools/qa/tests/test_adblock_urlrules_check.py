# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's dynamic URL filtering: the offline check (ROADMAP P5.60)."""
import unittest

from tools.qa import adblock_urlrules_check as uc


class StepTests(unittest.TestCase):
    def test_steps(self):
        self.assertEqual(uc.step_problems("block", {"/lib/keep.js"}, {"/lib/keep.js"}), [])
        self.assertEqual(len(uc.step_problems("block", {"/lib/keep.js", "/extra/more.js"}, {"/lib/keep.js"})), 1)

    def test_every_step_lets_one_script_through(self):
        for step, (rules, want) in uc.STEPS.items():
            self.assertEqual(len(want), 1, step)
            self.assertTrue(rules.endswith("\n"), step)

    def test_why_and_problems(self):
        self.assertEqual(uc.why_problems({"myRule": f"* http://{uc.LIB_HOST}/extra/ * block"}), [])
        self.assertEqual(len(uc.why_problems({"myRule": f"* {uc.LIB_HOST} * block"})), 1)
        self.assertEqual(uc.bad_problems(uc.BAD.splitlines()), [])
        self.assertEqual(len(uc.bad_problems([])), 1)

    def test_the_page_loads_both_scripts(self):
        self.assertIn(f'src="{uc.KEEP}"', uc.PAGE)
        self.assertIn(f'src="{uc.DROP}"', uc.PAGE)


if __name__ == "__main__":
    unittest.main()
