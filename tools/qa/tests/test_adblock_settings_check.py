# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import unittest

from tools.qa import adblock_settings_check as sc


class PureTests(unittest.TestCase):
    def test_the_served_easylist_gains_the_probe_rule_and_keeps_its_rules(self):
        served = sc.served_lists({"easylist": "||ads.example^\n", "easyprivacy": "||track.example^\n"})
        self.assertEqual(served["easylist"], "||ads.example^\n||easy-host.test^\n")
        self.assertEqual(served["easyprivacy"], "||track.example^\n")

    def test_the_extra_list_has_a_title_a_rule_and_a_rule_that_asks_for_trust(self):
        text = sc.EXTRA_LIST
        self.assertIn("! Title: Extra test list\n", text)
        self.assertIn("||list-host.test^\n", text)
        self.assertIn("##+js(trusted-set-cookie,", text)

    def test_the_page_asks_every_probe_host(self):
        page = sc.page_html(8123)
        for host in sc.HOSTS.values():
            self.assertIn(host, page)
        self.assertIn(":8123/probe.js", page)

    def test_blocked_reads_the_pages_results(self):
        results = {"easy-host.test": "blocked", "list-host.test": "loaded"}
        self.assertEqual(sc.blocked(results), {"easy": True, "list": False, "mine": None})

    def test_a_step_that_matches_has_no_problems(self):
        got = {"blocked": {"easy": True, "list": False, "mine": True}, "message": "Your filters were saved and are in use.",
               "bad": False, "rows": 8, "custom": 0, "cookie": ""}
        want = {"blocked": {"easy": True, "list": False, "mine": True}, "message": "saved", "bad": False, "rows": 8}
        self.assertEqual(sc.step_problems("my filters", want, got), [])

    def test_each_difference_is_named(self):
        got = {"blocked": {"easy": False, "list": None, "mine": True}, "message": "Working...", "bad": True, "rows": 9,
               "custom": 1, "cookie": "thoron_trusted=yes", "checked": {"easylist": True}, "not_applied": False}
        want = {"blocked": {"easy": True, "list": False, "mine": True}, "message": "saved", "bad": False, "rows": 8,
                "custom": 0, "no_cookie": "thoron_trusted", "checked": {"easylist": False}, "not_applied": True}
        problems = sc.step_problems("s", want, got)
        text = "\n".join(problems)
        for word in ("easy", "list", "message", "error", "rows", "added", "cookie", "easylist", "not in use"):
            self.assertIn(word, text)
        self.assertNotIn("mine", text)
        self.assertTrue(all(p.startswith("s: ") for p in problems))

    def test_an_undecided_probe_is_a_problem_not_a_pass(self):
        got = {"blocked": {"easy": None}, "message": "", "bad": False, "rows": 8}
        self.assertEqual(len(sc.step_problems("s", {"blocked": {"easy": False}}, got)), 1)

    def test_an_interrupted_state_names_the_settings_as_being_read(self):
        state = {"version": "1", "engine": True, "settings": "abc123", "result": "x", "lists": {}}
        faked = sc.interrupted(state)
        self.assertEqual(faked["building"], "abc123")
        self.assertNotEqual(faked["settings"], "abc123")
        self.assertEqual(state["settings"], "abc123")            # the original is left alone
        self.assertTrue(faked["engine"])

    def test_a_state_of_another_version_keeps_everything_but_its_version(self):
        state = {"version": "158.0.1.2", "engine": True, "settings": "abc", "lists": {"easylist": {}}}
        other = sc.other_version(state)
        self.assertNotEqual(other["version"], state["version"])
        self.assertEqual({k: v for k, v in other.items() if k != "version"},
                         {k: v for k, v in state.items() if k != "version"})

    def test_the_steps_cover_what_a_person_can_do(self):
        names = [s["name"] for s in sc.STEPS]
        for name in ("default", "my filters", "refused rule", "add a list", "refused list", "not https",
                     "list off", "after a restart", "list on", "after an update", "remove the list", "no filters",
                     "after an interruption", "change after it"):
            self.assertIn(name, names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
