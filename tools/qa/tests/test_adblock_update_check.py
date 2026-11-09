# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad-blocking list updates: the offline end-to-end check (ROADMAP P5.15)."""
import unittest

from tools.qa import adblock_update_check as uc

BUNDLED = ("! thoron-list: easylist\n[Adblock Plus 2.0]\n||ads.example^\n||more.example^\n"
           "! thoron-list: ublock-filters\n||ub.example^\n")


class SplitTests(unittest.TestCase):
    def test_lists_are_split_at_their_markers(self):
        lists = uc.split_lists(BUNDLED)
        self.assertEqual(sorted(lists), ["easylist", "ublock-filters"])
        self.assertEqual(lists["easylist"], "[Adblock Plus 2.0]\n||ads.example^\n||more.example^\n")
        self.assertNotIn("thoron-list", lists["ublock-filters"])

    def test_text_before_the_first_marker_is_ignored(self):
        self.assertEqual(uc.split_lists("junk\n! thoron-list: a\nx\n"), {"a": "x\n"})


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.bundled = uc.split_lists(BUNDLED)

    def test_good_update_adds_the_probe_rule_to_easylist_only(self):
        served = uc.served_lists(self.bundled, "good")
        self.assertIn(uc.PROBE_RULE, served["easylist"])
        self.assertTrue(served["easylist"].startswith(self.bundled["easylist"]))
        self.assertEqual(served["ublock-filters"], self.bundled["ublock-filters"])

    def test_shrunk_easylist_keeps_far_less_than_half(self):
        served = uc.served_lists(self.bundled, "shrunk")
        self.assertEqual(served["easylist"].strip(), uc.PROBE_RULE)

    def test_allow_all_list_holds_the_probe_rule_and_an_allow_everything_rule(self):
        served = uc.served_lists(self.bundled, "allow-all")
        self.assertIn(uc.PROBE_RULE, served["easylist"])
        self.assertIn("\n@@*\n", served["easylist"])

    def test_web_page_instead_of_a_list(self):
        served = uc.served_lists(self.bundled, "web-page")
        self.assertTrue(served["easylist"].lstrip().startswith("<"))

    def test_unblocks_drops_every_probe_rule_from_every_list(self):
        bundled = {"easylist": "||ads.example^\n||google-analytics.com^\n/analytics.js\n",
                   "ublock-filters": "||doubleclick.net^\n||ub.example^\n"}
        served = uc.served_lists(bundled, "unblocks")
        self.assertEqual(served["easylist"], f"||ads.example^\n{uc.PROBE_RULE}\n")
        self.assertEqual(served["ublock-filters"], "||ub.example^\n")

    def test_restart_serves_nothing(self):
        self.assertEqual(uc.served_lists(self.bundled, "restart"), {})


class VerdictTests(unittest.TestCase):
    def state(self, note):
        return {"version": "1", "engine": True, "lists": {"easylist": {"note": note}},
                "result": f"easylist: {note}\n"}

    def test_good_update_must_block_the_probe_afterwards(self):
        self.assertEqual(uc.problems("good", self.state("updated"), probe_blocked=True, list_requests=8), [])
        self.assertTrue(uc.problems("good", self.state("updated"), probe_blocked=False, list_requests=8))
        self.assertTrue(uc.problems("good", self.state("kept: download failed"), probe_blocked=True,
                                    list_requests=8))

    def test_refused_lists_keep_the_previous_engine(self):
        for scenario, reason in (("shrunk", "shrank from"), ("allow-all", "allows every request"),
                                 ("web-page", "a web page")):
            ok = self.state(f"kept: {reason} x")
            self.assertEqual(uc.problems(scenario, ok, probe_blocked=False, list_requests=8), [], scenario)
            self.assertTrue(uc.problems(scenario, ok, probe_blocked=True, list_requests=8), scenario)
            self.assertTrue(uc.problems(scenario, self.state("updated"), probe_blocked=False,
                                        list_requests=8), scenario)

    def test_an_update_that_unblocks_probes_is_refused_whole(self):
        refused = dict(self.state("updated"), result="all kept: the new engine no longer blocks https://x/\n")
        self.assertEqual(uc.problems("unblocks", refused, probe_blocked=False, list_requests=8), [])
        self.assertTrue(uc.problems("unblocks", refused, probe_blocked=True, list_requests=8))
        self.assertTrue(uc.problems("unblocks", self.state("updated"), probe_blocked=False, list_requests=8))

    def test_restart_uses_the_saved_engine_without_downloading(self):
        self.assertEqual(uc.problems("restart", self.state("updated"), probe_blocked=True, list_requests=0), [])
        self.assertTrue(uc.problems("restart", self.state("updated"), probe_blocked=True, list_requests=8))
        self.assertTrue(uc.problems("restart", self.state("updated"), probe_blocked=False, list_requests=0))

    def test_no_state_file_is_a_failure(self):
        self.assertTrue(uc.problems("good", None, probe_blocked=True, list_requests=8))


class ProbeTests(unittest.TestCase):
    def test_probe_is_blocked_when_the_last_attempts_never_arrived(self):
        # attempts 0..9 were made; the server saw 0..5 (before the update), so 6..9 were blocked
        self.assertTrue(uc.probe_blocked(seen=[0, 1, 2, 3, 4, 5], made=10, last=3))
        self.assertFalse(uc.probe_blocked(seen=[0, 1, 2, 3, 9], made=10, last=3))
        self.assertFalse(uc.probe_blocked(seen=[], made=2, last=3))  # too few attempts to tell


if __name__ == "__main__":
    unittest.main()
