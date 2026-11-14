# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, back up, reset and restore: the offline check (ROADMAP P5.40)."""
import unittest

from tools.qa import adblock_backup_check as bc


def changed() -> dict:
    return {"disabled": [bc.LIST_OFF], "myFilters": bc.MINE, "allowed": [f"[*.]{bc.ALLOWED}"],
            "switches": {bc.SWITCH_HOST: list(bc.SWITCHES)},
            "settings": {"badge": True, "block-csp-reports": True, "default-fonts": True, "webrtc": False}}


class ChangedTests(unittest.TestCase):
    def test_the_changed_state(self):
        self.assertEqual(bc.changed_problems("x", changed()), [])

    def test_each_part_that_differs_is_named(self):
        got = changed()
        got["settings"]["default-fonts"] = False
        got["myFilters"] = ""
        got["switches"] = {}
        found = bc.changed_problems("restore", got)
        self.assertEqual(len(found), 3)
        self.assertIn("restore: the setting default-fonts is not on", found)

    def test_the_backup_file_reads_like_the_page(self):
        backup = {"format": "thoron-adblock-backup", "version": 1,
                  "lists": {"disabled": [bc.LIST_OFF], "added": []}, "myFilters": bc.MINE,
                  "allowed": [f"[*.]{bc.ALLOWED}"], "switches": {bc.SWITCH_HOST: ["popups", "-fonts"]},
                  "settings": {"badge": True, "block-csp-reports": True, "default-fonts": True}}
        self.assertEqual(bc.changed_problems("backup", bc.backup_as_read(backup)), [])


class DefaultsTests(unittest.TestCase):
    def test_the_defaults(self):
        got = {"disabled": [], "myFilters": "", "allowed": [], "switches": {},
               "settings": {"badge": True, "webrtc": False, "auto-update": True, "context-menu": True,
                            "advanced": True, "media-kb": 50, "shortcuts": {"zapper": "Ctrl+Alt+Z"},
                            "colorblind": False, "version": "158.0.8127.3006", "theme": "auto"}}
        self.assertEqual(bc.default_problems(got), [])
        got["settings"].update({"auto-update": False, "media-kb": 300, "theme": "dark"})
        self.assertEqual(len(bc.default_problems(got)), 3)

    def test_whatever_is_left_is_named(self):
        found = bc.default_problems(changed())
        self.assertEqual(len(found), 6)


if __name__ == "__main__":
    unittest.main()
