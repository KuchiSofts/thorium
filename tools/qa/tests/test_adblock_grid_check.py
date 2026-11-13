# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the menu's grid of rules: the offline check (ROADMAP P5.45)."""
import unittest

from tools.qa import adblock_grid_check as gc

AD = "ads.example"


def grid(rows, changed=False):
    return {"hidden": False, "changed": changed, "rows": rows}


TYPES = [{"name": f"t{i}", "n": "", "type": True, "global": "", "local": ""} for i in range(gc.TYPE_ROWS)]


def host_row(name, n):
    return {"name": name, "n": n, "type": False, "global": "", "local": ""}


class RowsTests(unittest.TestCase):
    def test_a_good_grid(self):
        g = grid(TYPES + [host_row(gc.PAGE_HOST, ""), host_row(gc.OTHER_HOST, "1"), host_row(AD, "1/1")])
        self.assertEqual(gc.rows_problems(g, AD), [])

    def test_what_is_missing_is_named(self):
        g = grid(TYPES[:3] + [host_row(gc.OTHER_HOST, "1"), host_row(AD, "1")], changed=True)
        found = gc.rows_problems(g, AD)
        self.assertEqual(len(found), 4, found)
        self.assertEqual(gc.rows_problems({"hidden": True}, AD), ["rows: the grid is not shown"])


class StepTests(unittest.TestCase):
    def test_each_step_as_wanted(self):
        block = gc.saved_rule(gc.PAGE_HOST, gc.OTHER_HOST, "block")
        cases = {
            "block": {"other": False, "ad": False, "changed": True, "saved": "", "local": "block set"},
            "save": {"changed": False, "saved": block + "\n", "local": "block set"},
            "allow": {"other": False, "ad": True, "changed": True, "saved": block + "\n", "local": "allow set"},
            "revert": {"other": False, "ad": False, "changed": False, "saved": block + "\n", "local": ""},
            "inherit": {"changed": True, "local": "block inherited", "global": "block set"},
            "cleared": {"other": True, "changed": False, "saved": "# mine\n", "local": ""},
        }
        for step, seen in cases.items():
            self.assertEqual(gc.step_problems(step, seen, AD), [], step)

    def test_what_differs_is_named(self):
        found = gc.step_problems("block", {"other": True, "ad": False, "changed": False,
                                           "saved": gc.saved_rule(gc.PAGE_HOST, gc.OTHER_HOST, "block"),
                                           "local": "block inherited"}, AD)
        self.assertEqual(len(found), 4, found)
        found = gc.step_problems("cleared", {"other": True, "changed": False,
                                             "saved": f"* {gc.OTHER_HOST} * block\n", "local": ""}, AD)
        self.assertEqual(len(found), 1, found)

    def test_the_page(self):
        html = gc.page_html(AD)
        self.assertIn(f'src="http://{AD}/ad.png"', html)
        self.assertIn(f'src="http://{gc.OTHER_HOST}/lib.js"', html)


if __name__ == "__main__":
    unittest.main()
