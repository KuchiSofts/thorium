# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's switch lines in My rules: the offline check (ROADMAP P5.58)."""
import unittest

from tools.qa import adblock_switchlines_check as sc


class StepTests(unittest.TestCase):
    def test_apply(self):
        ok = "Your rules are saved and in use. 10 switch lines were applied to the sites and the settings."
        self.assertEqual(sc.apply_problems(ok, sc.RULES), [])
        self.assertEqual(len(sc.apply_problems("Your rules are saved and in use.", sc.RULES + sc.SWITCHES)), 2)

    def test_sites(self):
        sites = {"switches": [{"host": h, "names": n} for h, n in sc.WANT_SWITCHES.items()],
                 "javascript": [sc.JS_HOST]}
        settings = {"block-csp-reports": True, "default-cosmetic": True}
        self.assertEqual(sc.sites_problems(sites, settings), [])
        self.assertEqual(len(sc.sites_problems({"switches": [], "javascript": []}, {})), 8)
        sites["switches"].append({"host": "behind-the-scene", "names": ["-media"]})
        self.assertEqual(len(sc.sites_problems(sites, settings)), 1)

    def test_unknown(self):
        message = ("These lines are not rules and are not used: no-popups: * true (here only for one site at a "
                   "time) | no-csp-reports: csp-site.test true (here for every site only)")
        self.assertEqual(sc.unknown_problems(message), [])
        self.assertEqual(len(sc.unknown_problems("Your rules are saved and in use.")), 1)

    def test_script_and_menu(self):
        self.assertEqual(sc.script_problems({sc.JS_HOST: "still", sc.SUB_HOST: "still"}), [])
        self.assertEqual(len(sc.script_problems({sc.JS_HOST: "ran", sc.SUB_HOST: "still"})), 1)
        self.assertEqual(sc.menu_problems("ran"), [])
        self.assertEqual(len(sc.menu_problems("still")), 1)

    def test_export(self):
        text = sc.RULES + "\n".join(sc.WANT_EXPORT) + "\n"
        self.assertEqual(sc.export_problems(text), [])
        self.assertEqual(len(sc.export_problems(sc.RULES)), len(sc.WANT_EXPORT))
        self.assertEqual(len(sc.export_problems(text + "no-scripting: behind-the-scene false\n")), 1)

    def test_the_text_is_as_ublock_origin_writes_it(self):
        for line in sc.SWITCHES.splitlines():
            name, host, value = line.replace(":", "").split()
            self.assertTrue(name.startswith("no-") and value in ("true", "false"), line)


if __name__ == "__main__":
    unittest.main()
