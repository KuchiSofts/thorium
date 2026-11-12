# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, `$header` rules: the offline check (ROADMAP P5.26)."""
import re
import unittest

from tools.qa import adblock_header_check as hc

LISTS = r"""! thoron-list: ublock-filters
! ||commented.example/*.min.js|$script,xhr,3p,header=x-commented
||cdn.example/*.min.js|$script,xhr,3p,header=popads-node
||cdn.example/*.min.js|$script,xhr,3p,header=x-77-pop
||cdn.example/*.min.js|$script,xhr,3p,header=link:*adsco.re*
||com/script/*.js|$script,3p,header=location:https://stg.*
/^https?:\/\/[a-z]{7,}\.com\/[+\/0-9a-zA-Z]{19,}$/$frame,3p,match-case,header=x-amz-cf-pop,to=com,from=info|me|pm|site|~edu.me|~proton.me
/^https:\/\/www\.[a-z]{8,14}\.com\/[a-z]{1,4}\.js$/$script,3p,match-case,header=x-powered-by:Express
"""


class CasesTests(unittest.TestCase):
    def setUp(self):
        self.found = hc.cases(LISTS)

    def test_the_first_rule_of_each_kind_is_taken(self):
        self.assertEqual(list(self.found), ["name", "value", "redirect", "frame"])
        name = self.found["name"]
        self.assertEqual(name["type"], "script")
        self.assertEqual(name["with"], {"host": "with-name.cdn.example", "path": "/lib.min.js",
                                        "headers": {"popads-node": "1"}})
        self.assertEqual(name["without"], {"host": "without-name.cdn.example", "path": "/lib.min.js", "headers": {}})

    def test_the_value_case_has_the_header_on_both_sides_with_another_value(self):
        value = self.found["value"]
        self.assertEqual(value["with"]["headers"], {"link": "<https://adsco.re/>;rel=preconnect"})
        self.assertEqual(list(value["without"]["headers"]), ["link"])
        self.assertNotIn("adsco.re", value["without"]["headers"]["link"])

    def test_the_redirect_case_is_judged_by_the_location_of_the_redirect(self):
        redirect = self.found["redirect"]
        self.assertEqual(redirect["type"], "script")
        for side in ("with", "without"):
            self.assertRegex(redirect[side]["host"], r"^[a-z-]+\.com$")
            self.assertEqual(redirect[side]["path"], "/script/lib.js")
            # both go on to a plain address of the same host, which the local server answers
            self.assertTrue(redirect[side]["redirect"].startswith(f"http://{redirect[side]['host']}/landed.js"))
        self.assertIn("https://stg.", redirect["with"]["redirect"])
        self.assertNotIn("https://stg.", redirect["without"]["redirect"])

    def test_the_frame_case_fits_the_rules_own_expression_and_its_sites(self):
        frame = self.found["frame"]
        self.assertEqual(frame["type"], "frame")
        rule = re.compile(r"^https?:\/\/[a-z]{7,}\.com\/[+\/0-9a-zA-Z]{19,}$")
        for side in ("with", "without"):
            self.assertRegex(f"http://{frame[side]['host']}{frame[side]['path']}", rule)
        self.assertEqual(frame["with"]["headers"], {"x-amz-cf-pop": "FRA56-P1"})
        self.assertEqual(frame["without"]["headers"], {})
        # the rule is for pages of sites under ".info" (the first it names)
        self.assertEqual(hc.page_host(self.found), "hdr-check.info")
        self.assertEqual(hc.page_host({"name": self.found["name"]}), "hdr-check.info")

    def test_lists_without_such_rules_give_no_case(self):
        self.assertEqual(hc.cases("||ads.example^\n||x.example^$script\n"), {})

    def test_the_names_to_send_to_the_local_server(self):
        names = hc.hosts(self.found)
        self.assertIn("hdr-check.info", names)
        self.assertIn("with-name.cdn.example", names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 1 + 2 * len(self.found))


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.found = hc.cases(LISTS)

    def test_a_script_is_answered_with_the_headers_of_its_side(self):
        status, headers, body = hc.answer(self.found, "with-name.cdn.example", "/lib.min.js")
        self.assertEqual((status, headers["popads-node"]), (200, "1"))
        self.assertEqual(headers["Content-Type"], "text/javascript")
        status, headers, _ = hc.answer(self.found, "without-name.cdn.example", "/lib.min.js")
        self.assertEqual(status, 200)
        self.assertNotIn("popads-node", headers)

    def test_a_redirect_carries_its_location(self):
        side = self.found["redirect"]["with"]
        status, headers, _ = hc.answer(self.found, side["host"], side["path"])
        self.assertEqual((status, headers["Location"]), (302, side["redirect"]))
        status, headers, _ = hc.answer(self.found, side["host"], "/landed.js?from=https://stg.example")
        self.assertEqual((status, headers["Content-Type"]), (200, "text/javascript"))

    def test_a_frame_tells_the_page_it_is_there(self):
        side = self.found["frame"]["with"]
        status, headers, body = hc.answer(self.found, side["host"], side["path"])
        self.assertEqual((status, headers["x-amz-cf-pop"]), (200, "FRA56-P1"))
        self.assertIn(b"postMessage", body)
        self.assertIn(b"frame:with", body)

    def test_the_page_asks_for_both_sides_of_every_case(self):
        status, headers, body = hc.answer(self.found, "hdr-check.info", "/page.html")
        self.assertEqual(status, 200)
        html = body.decode()
        for kind, case in self.found.items():
            for side in ("with", "without"):
                self.assertIn(f"http://{case[side]['host']}{case[side]['path']}", html, f"{kind} {side}")
        self.assertIn("/result", html)

    def test_anything_else_is_not_found(self):
        self.assertEqual(hc.answer(self.found, "other.example", "/lib.min.js")[0], 404)
        self.assertEqual(hc.answer(self.found, "with-name.cdn.example", "/other.js")[0], 404)


class ProblemsTests(unittest.TestCase):
    def setUp(self):
        self.found = hc.cases(LISTS)
        self.all_loaded = {f"{kind}:{side}": "loaded" for kind in self.found for side in ("with", "without")}
        self.acted = dict(self.all_loaded, **{f"{kind}:with": "blocked" for kind in self.found})

    def test_with_blocking_on_the_answer_with_the_header_ends_the_request(self):
        self.assertEqual(hc.problems("native", self.found, self.acted), [])
        found = hc.problems("native", self.found, self.all_loaded)
        self.assertEqual(len(found), len(self.found))
        self.assertIn("name: the answer with the header was let through", found)

    def test_the_answer_without_the_header_must_get_through(self):
        results = dict(self.acted, **{"value:without": "blocked"})
        self.assertEqual(hc.problems("native", self.found, results), ["value: the answer without the header was stopped"])

    def test_with_blocking_off_everything_loads(self):
        for mode in ("control", "site-off"):
            self.assertEqual(hc.problems(mode, self.found, self.all_loaded), [], mode)
            found = hc.problems(mode, self.found, self.acted)
            self.assertEqual(len(found), len(self.found), mode)
            self.assertIn("though blocking is off here", found[0])

    def test_a_missing_result_is_a_problem(self):
        results = dict(self.acted)
        del results["frame:without"]
        self.assertEqual(hc.problems("native", self.found, results), ["frame: the page did not say what became of it"])
        self.assertEqual(len(hc.problems("native", self.found, None)), len(self.found))

    def test_an_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            hc.problems("other", self.found, self.acted)


if __name__ == "__main__":
    unittest.main()
