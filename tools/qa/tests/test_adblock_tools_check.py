# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the tools of chrome://adblock: the offline check (ROADMAP P5.54)."""
import unittest

from tools.qa import adblock_tools_check as tc


def row(name: str, kind: str = "allowed", type_: str = "image") -> dict:
    return {"kind": kind, "type": type_, "url": f"http://{tc.PLAIN_HOST}/{name}"}


class FiltersTests(unittest.TestCase):
    def test_the_bad_line_alone_is_named(self):
        head = "These lines are not filters this blocker can use: "
        self.assertEqual(tc.filters_problems(f"{head}{tc.BAD_FILTER} (unrecognised option)"), [])
        self.assertEqual(len(tc.filters_problems("Your filters were saved and are in use.")), 1)
        found = tc.filters_problems(f"{head}{tc.GOOD_FILTER} (x) | {tc.BAD_FILTER} (y)")
        self.assertEqual(len(found), 1)
        self.assertIn("good filter", found[0])


class HiddenTests(unittest.TestCase):
    def test_the_hide_rules_that_hid_something(self):
        rows = [{"kind": "blocked", "type": "cosmetic", "url": u, "shown": "hidden"} for u in sorted(tc.HIDDEN)]
        self.assertEqual(tc.hidden_problems(rows + [row("pic.png")]), [])
        self.assertEqual(len(tc.hidden_problems(rows[:1])), 1)
        rows[0]["shown"] = "blocked"
        self.assertEqual(len(tc.hidden_problems(rows)), 1)
        self.assertIn('class="thoron-promo"', tc.page_html())


class LoggerTests(unittest.TestCase):
    def test_types(self):
        rows = [{"kind": "blocked", "type": "image", "url": f"http://{tc.BLOCKED_HOST}/ad.png"},
                row("pic.png"), row("plain.js", type_="script")]
        self.assertEqual(tc.types_problems(["image", "script"], rows, [rows[2]]), [])
        self.assertEqual(len(tc.types_problems(["image"], rows, [rows[2]])), 1)
        self.assertEqual(len(tc.types_problems(["image", "script"], rows, rows)), 1)
        self.assertEqual(len(tc.types_problems(["image", "script"], rows[1:], [rows[2]])), 1)

    def test_pause_and_clear(self):
        self.assertEqual(tc.pause_problems([row("pic.png")], [row("while-paused.png")], "Resume"), [])
        self.assertEqual(len(tc.pause_problems([row("while-paused.png")], [], "Pause")), 3)
        self.assertEqual(tc.clear_problems([], [row("after-clear.png")]), [])
        self.assertEqual(len(tc.clear_problems([row("x.png")], [row("while-paused.png")])), 3)

    def test_export(self):
        rows = [row("after-clear.png")]
        text = f"2026-01-01T00:00:00.000Z\tlet through\timage\t3p\t{rows[0]['url']}\n"
        self.assertEqual(tc.export_problems(text, rows), [])
        self.assertEqual(len(tc.export_problems("", rows)), 2)
        self.assertEqual(len(tc.export_problems(f"a\tb\tc\t{rows[0]['url']}\n", rows)), 1)


class FilesTests(unittest.TestCase):
    def test_sites(self):
        exported = "\n".join(tc.WANTED_SITES) + "\n"
        self.assertEqual(tc.sites_problems("3 sites were allowed.", list(tc.WANTED_SITES), exported), [])
        self.assertEqual(len(tc.sites_problems("0 sites were allowed.", [], "")), 7)

    def test_the_import_file_has_each_kind_of_line(self):
        lines = tc.IMPORTED_SITES.splitlines()
        self.assertIn("imported-one.test", lines)
        self.assertTrue(any(line.startswith("[*.]") for line in lines))
        self.assertTrue(any(line.startswith("https://") for line in lines))
        self.assertTrue(any(line.startswith("#") for line in lines))

    def test_rules(self):
        box = "* a.test * noop\n" + tc.IMPORTED_RULES
        self.assertEqual(tc.rules_problems(box, box), [])
        self.assertEqual(len(tc.rules_problems("", "x")), 2)


class LookTests(unittest.TestCase):
    def test_colorblind(self):
        self.assertEqual(tc.colorblind_problems(True, {"class": True, "allow": "#1a73e8"}), [])
        self.assertEqual(tc.colorblind_problems(False, {"class": False, "allow": "#1e8e3e"}), [])
        self.assertEqual(len(tc.colorblind_problems(True, {"class": True, "allow": "#1e8e3e"})), 1)
        self.assertEqual(len(tc.colorblind_problems(False, {"class": False, "allow": "#1a73e8"})), 1)

    def test_info(self):
        text = ("Thoron 158.0.8127.3006\nLists in use:\n  EasyList (100 rules)\nMy filters: 1 rules\n"
                "My rules: 1 lines\nAllowed sites: 3, sites with switches: 0\nSettings changed: colorblind: true\n"
                "Last looked for updates: never\n")
        self.assertEqual(tc.info_problems(text), [])
        self.assertEqual(len(tc.info_problems(text + f"http://{tc.PAGE_HOST}/\n")), 1)
        self.assertEqual(len(tc.info_problems("")), 7)


class PageTests(unittest.TestCase):
    def test_the_page(self):
        html = tc.page_html()
        self.assertIn(f'src="http://{tc.BLOCKED_HOST}/ad.png"', html)
        self.assertIn(f'src="http://{tc.PLAIN_HOST}/plain.js"', html)
        self.assertIn(tc.TITLE, html)
        self.assertIn(f"//{tc.PLAIN_HOST}/x.png", tc.request("x"))


if __name__ == "__main__":
    unittest.main()
