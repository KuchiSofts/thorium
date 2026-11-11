# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, redirects: the offline check (ROADMAP P5.25)."""
import unittest

from tools.qa import adblock_redirect_check as rc

NAME = "gbraid"
DIRTY = "gbraid=abc&keep=1"


def seen(ad=(), page=None):
    """A server log in which every hop was asked for."""
    log = {"/hop": [f"to={to}" for to in rc.HOPS]}
    log.update(page or {})
    return {"ad": sorted(ad), "page": log}


class TargetTests(unittest.TestCase):
    def test_every_hop_has_a_target(self):
        for to in rc.HOPS:
            self.assertTrue(rc.hop_target(to, NAME), to)
        with self.assertRaises(KeyError):
            rc.hop_target("nowhere", NAME)

    def test_hops_to_the_ad_host_name_it(self):
        for to in ("far-script", "far-image", "far-data", "far-frame"):
            self.assertTrue(rc.hop_target(to, NAME).startswith(f"http://{rc.AD_HOST}/"), to)
        # a chain takes one more hop before it gets there
        self.assertEqual(rc.hop_target("chain", NAME), "/hop?to=far-chain")
        self.assertTrue(rc.hop_target("far-chain", NAME).startswith(f"http://{rc.AD_HOST}/"))

    def test_hops_to_an_address_with_the_parameter(self):
        self.assertEqual(rc.hop_target("clean-data", NAME), f"/data.json?{DIRTY}")
        self.assertEqual(rc.hop_target("clean-frame", NAME), f"/inner.html?{DIRTY}")
        self.assertEqual(rc.hop_target("landing", NAME), f"/landing.html?{DIRTY}")

    def test_every_ad_path_is_reached_by_a_hop(self):
        reached = {rc.hop_target(to, NAME).removeprefix(f"http://{rc.AD_HOST}") for to in rc.HOPS
                   if rc.hop_target(to, NAME).startswith(f"http://{rc.AD_HOST}/")}
        self.assertEqual(reached, set(rc.AD_PATHS))


class PageTests(unittest.TestCase):
    def test_the_page_asks_through_a_hop_in_every_way(self):
        html = rc.page_html()
        for to in ("far-script", "far-image", "far-data", "far-frame", "chain", "clean-data", "clean-frame",
                   "ok-script", "ok-image"):
            self.assertIn(f"/hop?to={to}", html, to)
        self.assertIn("/result/page", html)

    def test_the_landing_pages_report_their_address(self):
        for name in ("landing", "insist"):
            html = rc.report_html(name)
            self.assertIn(f"/result/{name}", html)
            self.assertIn("location.search", html)


class ProblemTests(unittest.TestCase):
    def blocked(self):
        results = {"page": {"okScript": True, "okImage": True, "adScript": False},
                   "landing": {"search": "?keep=1"}, "insist": {"search": "?" + DIRTY}}
        log = seen(page={"/data.json": ["keep=1"], "/inner.html": ["keep=1"], "/landing.html": ["keep=1"],
                         "/insist.html": [DIRTY, "keep=1", DIRTY]})
        return results, log

    def untouched(self):
        results = {"page": {"okScript": True, "okImage": True, "adScript": True},
                   "landing": {"search": "?" + DIRTY}, "insist": {"search": "?" + DIRTY}}
        log = seen(ad=rc.AD_PATHS, page={"/data.json": [DIRTY], "/inner.html": [DIRTY], "/landing.html": [DIRTY],
                                         "/insist.html": [DIRTY]})
        return results, log

    def test_with_blocking_on_every_redirect_was_judged(self):
        results, log = self.blocked()
        self.assertEqual(rc.problems("native", NAME, results, log), [])
        results, log = self.untouched()
        self.assertGreaterEqual(len(rc.problems("native", NAME, results, log)), 5)

    def test_with_blocking_off_every_redirect_is_followed(self):
        for mode in ("control", "site-off"):
            results, log = self.untouched()
            self.assertEqual(rc.problems(mode, NAME, results, log), [], mode)
            results, log = self.blocked()
            self.assertTrue(rc.problems(mode, NAME, results, log), mode)

    def test_one_request_that_reached_the_ad_host_is_named(self):
        results, log = self.blocked()
        log["ad"] = ["/ad2.js"]
        found = rc.problems("native", NAME, results, log)
        self.assertEqual(len(found), 1)
        self.assertIn("/ad2.js", found[0])

    def test_a_redirect_that_must_work_is_checked_in_every_mode(self):
        for mode, case in (("native", self.blocked()), ("control", self.untouched())):
            results, log = case
            results["page"]["okScript"] = False
            found = rc.problems(mode, NAME, results, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("harmless", found[0])

    def test_a_parameter_that_reached_the_server_after_a_redirect_is_named(self):
        results, log = self.blocked()
        log["page"]["/inner.html"] = [DIRTY]
        found = rc.problems("native", NAME, results, log)
        self.assertEqual(len(found), 1)
        self.assertIn("/inner.html", found[0])
        # not asked for at all is a problem too
        results, log = self.blocked()
        del log["page"]["/data.json"]
        self.assertEqual(len(rc.problems("native", NAME, results, log)), 1)

    def test_the_page_must_see_the_clean_address_after_a_redirect(self):
        results, log = self.blocked()
        results["landing"]["search"] = "?" + DIRTY
        self.assertEqual(len(rc.problems("native", NAME, results, log)), 1)

    def test_a_site_that_insists_still_loads(self):
        # the browser cleaned once, the site sent it back, the page loaded with the parameter
        results, log = self.blocked()
        self.assertEqual(rc.problems("native", NAME, results, log), [])
        # it must have tried
        log["page"]["/insist.html"] = [DIRTY]
        found = rc.problems("native", NAME, results, log)
        self.assertEqual(len(found), 1)
        self.assertIn("insist", found[0])
        # and it must not hang or fail
        results, log = self.blocked()
        del results["insist"]
        found = rc.problems("native", NAME, results, log)
        self.assertEqual(len(found), 1)
        self.assertIn("insist", found[0])

    def test_a_hop_that_was_never_asked_for_proves_nothing(self):
        # a request blocked before its redirect would look like a blocked redirect
        for mode, case in (("native", self.blocked()), ("control", self.untouched())):
            results, log = case
            log["page"]["/hop"].remove("to=far-script")
            found = rc.problems(mode, NAME, results, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("far-script", found[0])

    def test_no_result_is_a_problem(self):
        self.assertEqual(rc.problems("native", NAME, {}, seen()), ["the page gave no result"])

    def test_an_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            rc.problems("other", NAME, {}, seen())


if __name__ == "__main__":
    unittest.main()
