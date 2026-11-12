# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, procedural hide rules, $removeparam and $csp: the offline check (ROADMAP P5.22)."""
import unittest

from tools.qa import adblock_syntax_check as sc

LISTS = """! thoron-list: easylist
news.example##.card:has-text(Sponsored)
news.example##.card:has-text(/regex/)
xxxtube.example##.card:has-text(Advert)
||video.example^$csp=worker-src 'none'
! thoron-list: ublock-filters
games.example###ad-top:upward(3)
far.example##.x:upward(9)
shop.example##.banner:remove()
blog.example##a.get-link.disabled:remove-class(disabled)
files.example###file:remove-attr(disabled)
locked.example###go[disabled]:remove-attr(disabled)
wall.example##.content:style(display: block !important;)
odd.example##.content:style(margin: 0 auto !important)
$removeparam=_hsenc
$removeparam=mtm_source
||msn.example^$doc,removeparam=ei
$csp=child-src 'none'; frame-src 'self' *; worker-src 'none',domain=file.example|other.example
! thoron-list: ublock-privacy
*$permissions=idle-detection=(),from=~localhost|~127.0.0.1|~[::1]|~local
*$permissions=browsing-topics=(),from=~localhost|~127.0.0.1|~[::1]|~local
*$permissions=camera=*,from=~localhost
||one.example^$permissions=keyboard-map=()
@@||xxxcams.example^$permissions=browsing-topics=()
@@||shop.example^$permissions=browsing-topics=()
@@||late.example^$permissions=idle-detection=()
"""
FEATURES = ["idle-detection", "browsing-topics"]


class SelectorTests(unittest.TestCase):
    def test_a_simple_selector_becomes_an_element(self):
        self.assertEqual(sc.parse_simple(".banner"), {"tag": "div", "id": None, "classes": ["banner"]})
        self.assertEqual(sc.parse_simple("#ad-top"), {"tag": "div", "id": "ad-top", "classes": []})
        self.assertEqual(sc.parse_simple("a.get-link.disabled"),
                         {"tag": "a", "id": None, "classes": ["get-link", "disabled"]})
        self.assertEqual(sc.parse_simple("#rewarded.is-locked"), {"tag": "div", "id": "rewarded", "classes": ["is-locked"]})

    def test_anything_else_is_not_simple(self):
        for selector in ["", "a > b", ".x .y", "#go[disabled]", ".a:not(.b)", "*", "a,b", ".x::before", "#a#b"]:
            self.assertIsNone(sc.parse_simple(selector), selector)

    def test_an_element_is_written_as_html(self):
        html = sc.element_html(".banner", "one", text="ad")
        self.assertEqual(html, '<div class="banner" data-check="one">ad</div>')
        html = sc.element_html("a.get-link.disabled", "two", attrs={"disabled": "x"}, style="display: inline")
        self.assertEqual(html, '<a class="get-link disabled" data-check="two" disabled="x" style="display: inline"></a>')
        self.assertEqual(sc.element_html("#file", "three"), '<div id="file" data-check="three"></div>')


class CaseTests(unittest.TestCase):
    def setUp(self):
        self.cases = sc.cases(LISTS)

    def test_one_rule_of_each_kind_is_picked(self):
        self.assertEqual(self.cases["has-text"], {"host": "news.example", "selector": ".card", "text": "Sponsored"})
        self.assertEqual(self.cases["upward"], {"host": "games.example", "selector": "#ad-top", "levels": 3})
        self.assertEqual(self.cases["remove"], {"host": "shop.example", "selector": ".banner"})
        self.assertEqual(self.cases["remove-class"],
                         {"host": "blog.example", "selector": "a.get-link.disabled", "name": "disabled"})
        self.assertEqual(self.cases["remove-attr"], {"host": "files.example", "selector": "#file", "name": "disabled"})
        self.assertEqual(self.cases["style"],
                         {"host": "wall.example", "selector": ".content", "property": "display", "value": "block",
                          "initial": "inline"})

    def test_removeparam_takes_the_first_rule_for_every_site(self):
        self.assertEqual(self.cases["removeparam"], {"host": sc.PARAM_HOST, "name": "_hsenc"})

    def test_csp_takes_a_rule_a_page_can_show(self):
        self.assertEqual(self.cases["csp"], {"host": "video.example", "policy": "worker-src 'none'", "by_address": True})
        only_domain = sc.cases("$csp=child-src 'none'; worker-src 'none',domain=~not.example|file.example\n")
        self.assertEqual(only_domain["csp"],
                         {"host": "file.example", "policy": "child-src 'none'; worker-src 'none'", "by_address": False})

    def test_permissions_takes_every_feature_the_lists_switch_off_everywhere(self):
        self.assertEqual(self.cases["permissions"], {"host": sc.PERMISSIONS_HOST, "features": FEATURES})

    def test_permissions_kept_takes_the_first_exception_for_one_of_them(self):
        self.assertEqual(self.cases["permissions-kept"],
                         {"host": "shop.example", "kept": "browsing-topics", "features": FEATURES})
        # an exception for a feature that no rule switches off shows nothing
        self.assertNotIn("permissions-kept",
                         sc.cases("*$permissions=idle-detection=(),from=~localhost\n"
                                  "@@||shop.example^$permissions=browsing-topics=()\n"))
        self.assertNotIn("permissions", sc.cases("@@||shop.example^$permissions=browsing-topics=()\n"))

    def test_hosts_not_fit_for_a_report_are_skipped(self):
        self.assertNotIn("xxxtube.example", [c.get("host") for c in self.cases.values()])
        self.assertNotIn("has-text", sc.cases("xxxtube.example##.card:has-text(Advert)\n"))

    def test_a_kind_without_a_usable_rule_is_left_out(self):
        self.assertEqual(sc.cases("||ads.example^\nnews.example##.ad\n"), {})

    def test_the_style_case_starts_from_another_value(self):
        found = sc.cases("wall.example##.content:style(display: inline !important)\n")["style"]
        self.assertEqual((found["value"], found["initial"]), ("inline", "block"))

    def test_hosts_of_all_cases(self):
        self.assertEqual(sc.hosts(self.cases),
                         sorted(["blog.example", "files.example", "games.example", "news.example", "shop.example",
                                 sc.PARAM_HOST, sc.PERMISSIONS_HOST, "video.example", "wall.example"]))


class PageTests(unittest.TestCase):
    def setUp(self):
        self.cases = sc.cases(LISTS)

    def test_every_case_has_a_page_that_reports(self):
        for kind, case in self.cases.items():
            html = sc.page_html(kind, case)
            self.assertIn(f"/result/{kind}", html, kind)
            self.assertTrue(html.startswith("<!doctype html>"), kind)

    def test_the_has_text_page_has_an_element_with_the_text_and_one_without(self):
        html = sc.page_html("has-text", self.cases["has-text"])
        self.assertIn('<div class="card" data-check="yes">Sponsored</div>', html)
        self.assertIn('<div class="card" data-check="no">plain words</div>', html)

    def test_the_upward_page_nests_the_element_one_level_deeper_than_the_rule_climbs(self):
        html = sc.page_html("upward", self.cases["upward"])
        self.assertEqual(html.count('data-level="'), 4)
        self.assertIn('<div id="ad-top" data-check="start">', html)

    def test_the_removeparam_page_asks_with_the_parameter_in_every_way(self):
        html = sc.page_html("removeparam", self.cases["removeparam"])
        for path in ("/data.json?_hsenc=abc&keep=1", "/shape.gif?_hsenc=abc&keep=1", "/inner.html?_hsenc=abc&keep=1"):
            self.assertIn(path, html)

    def test_the_permissions_pages_ask_about_every_feature(self):
        for kind in ("permissions", "permissions-kept"):
            html = sc.page_html(kind, self.cases[kind])
            self.assertIn('["idle-detection", "browsing-topics"]', html)
            self.assertIn("allowsFeature", html)

    def test_the_permissions_page_comes_with_the_sites_own_header(self):
        # the site says the features are its own to use: the rules must win over that
        self.assertEqual(sc.page_headers("permissions", self.cases["permissions"]),
                         {"Permissions-Policy": "idle-detection=(self), browsing-topics=(self)"})
        for kind in ("permissions-kept", "csp", "remove"):
            self.assertEqual(sc.page_headers(kind, self.cases[kind]), {}, kind)

    def test_the_parent_page_frames_what_applies_inside_a_frame(self):
        html = sc.parent_html(self.cases)
        for host in ("news.example", "games.example", "shop.example", "video.example"):
            self.assertIn(f'src="http://{host}/', html)
        self.assertNotIn(sc.PARAM_HOST, html)   # the removeparam page brings its own frame
        # the permissions rules leave pages on this PC alone, and the parent page is one
        self.assertNotIn(sc.PERMISSIONS_HOST, html)
        self.assertEqual(html.count("<iframe"), 7)
        # a csp rule that goes by the page's site does not apply to a frame of another page
        by_domain = dict(self.cases, csp={"host": "file.example", "policy": "worker-src 'none'", "by_address": False})
        self.assertNotIn("file.example", sc.parent_html(by_domain))


class ProblemTests(unittest.TestCase):
    def setUp(self):
        self.cases = sc.cases(LISTS)

    def good(self, kind):
        return {
            "has-text": {"yes": True, "no": False},
            "upward": {"target": True, "above": False},
            "remove": {"present": False},
            "remove-class": {"has": False},
            "remove-attr": {"has": False},
            "style": {"value": "block"},
            "removeparam": {"search": "?keep=1", "seen": {"/clean.html": "keep=1", "/data.json": "keep=1",
                                                         "/inner.html": "keep=1", "/shape.gif": "_hsenc=abc&keep=1"}},
            "csp": {"worker": "refused", "violations": [{"directive": "worker-src", "policy": "worker-src 'none'"}]},
            "permissions": {"known": FEATURES, "allowed": []},
            "permissions-kept": {"known": FEATURES, "allowed": ["browsing-topics"]},
        }[kind]

    def untouched(self, kind):
        dirty = "_hsenc=abc&keep=1"
        return {
            "has-text": {"yes": False, "no": False},
            "upward": {"target": False, "above": False},
            "remove": {"present": True},
            "remove-class": {"has": True},
            "remove-attr": {"has": True},
            "style": {"value": "inline"},
            "removeparam": {"search": "?" + dirty, "seen": {"/clean.html": dirty, "/data.json": dirty,
                                                           "/inner.html": dirty, "/shape.gif": dirty}},
            "csp": {"worker": "started", "violations": []},
            "permissions": {"known": FEATURES, "allowed": FEATURES},
            "permissions-kept": {"known": FEATURES, "allowed": FEATURES},
        }[kind]

    def test_with_blocking_on_every_rule_must_have_acted(self):
        for kind, case in self.cases.items():
            self.assertEqual(sc.problems("native", kind, case, self.good(kind)), [], kind)
            self.assertTrue(sc.problems("native", kind, case, self.untouched(kind)), kind)

    def test_with_blocking_off_nothing_may_be_touched(self):
        for mode in ("control", "site-off"):
            for kind, case in self.cases.items():
                self.assertEqual(sc.problems(mode, kind, case, self.untouched(kind)), [], kind)
                self.assertTrue(sc.problems(mode, kind, case, self.good(kind)), kind)

    def test_no_result_is_a_problem(self):
        for kind, case in self.cases.items():
            self.assertEqual(sc.problems("native", kind, case, None), ["the page gave no result"])

    def test_has_text_must_leave_the_element_without_the_text(self):
        found = sc.problems("native", "has-text", self.cases["has-text"], {"yes": True, "no": True})
        self.assertEqual(len(found), 1)
        self.assertIn("without the text", found[0])

    def test_upward_must_stop_at_the_level_the_rule_names(self):
        found = sc.problems("native", "upward", self.cases["upward"], {"target": True, "above": True})
        self.assertEqual(len(found), 1)

    def test_removeparam_is_judged_request_by_request(self):
        result = self.good("removeparam")
        result["seen"]["/data.json"] = "_hsenc=abc&keep=1"
        found = sc.problems("native", "removeparam", self.cases["removeparam"], result)
        self.assertEqual(len(found), 1)
        self.assertIn("/data.json", found[0])
        # an image is not a document, a frame or a fetch: its address must stay
        result = self.good("removeparam")
        result["seen"]["/shape.gif"] = "keep=1"
        self.assertEqual(len(sc.problems("native", "removeparam", self.cases["removeparam"], result)), 1)
        # the page itself must see the clean address too
        result = self.good("removeparam")
        result["search"] = "?_hsenc=abc&keep=1"
        self.assertEqual(len(sc.problems("native", "removeparam", self.cases["removeparam"], result)), 1)

    def test_csp_needs_a_violation_of_the_rules_own_policy(self):
        case = self.cases["csp"]
        other = {"worker": "refused", "violations": [{"directive": "worker-src", "policy": "worker-src 'self'"}]}
        self.assertTrue(sc.problems("native", "csp", case, other))

    def test_permissions_are_judged_feature_by_feature(self):
        case = self.cases["permissions"]
        found = sc.problems("native", "permissions", case, {"known": FEATURES, "allowed": ["idle-detection"]})
        self.assertEqual(found, ["idle-detection is still allowed"])
        found = sc.problems("control", "permissions", case, {"known": FEATURES, "allowed": ["idle-detection"]})
        self.assertEqual(len(found), 1)
        self.assertIn("browsing-topics is switched off", found[0])
        # a feature this browser does not have cannot be on or off
        only_one = {"known": ["idle-detection"], "allowed": []}
        self.assertEqual(sc.problems("native", "permissions", case, only_one), [])
        # with none of them there is nothing to see, and that is a problem
        for mode in ("native", "control"):
            found = sc.problems(mode, "permissions", case, {"known": [], "allowed": []})
            self.assertEqual(len(found), 1, mode)
            self.assertIn("knows none", found[0])

    def test_an_exception_keeps_its_feature_and_only_that(self):
        case = self.cases["permissions-kept"]
        found = sc.problems("native", "permissions-kept", case, {"known": FEATURES, "allowed": []})
        self.assertEqual(len(found), 1)
        self.assertIn("exception", found[0])
        found = sc.problems("native", "permissions-kept", case, {"known": FEATURES, "allowed": FEATURES})
        self.assertEqual(found, ["idle-detection is still allowed"])

    def test_what_the_run_with_blocking_off_cannot_show_is_not_judged(self):
        kept = self.cases["permissions-kept"]
        self.assertFalse(sc.judgeable("remove", self.cases["remove"], None))
        self.assertTrue(sc.judgeable("remove", self.cases["remove"], {"present": True}))
        self.assertTrue(sc.judgeable("permissions-kept", kept, {"known": FEATURES, "allowed": FEATURES}))
        # the browser does not have the feature the exception is about
        self.assertFalse(sc.judgeable("permissions-kept", kept, {"known": ["idle-detection"], "allowed": []}))
        # the plain permissions case stays in: a browser without any of the features fails it
        self.assertTrue(sc.judgeable("permissions", self.cases["permissions"], {"known": [], "allowed": []}))

    def test_an_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            sc.problems("other", "remove", self.cases["remove"], {"present": True})


class RunnerTests(unittest.TestCase):
    def test_comment_lines_are_taken_out_as_the_engine_does(self):
        source = "// header\n(function(filters) {\n  // inside\n  return filters.length;  // kept\n})\n"
        self.assertEqual(sc.runner_code(source), "(function(filters) {\n  return filters.length;  // kept\n})")

    def test_every_filter_of_the_battery_has_its_own_mark_and_an_expectation(self):
        marks = [f["a"][1] for f in sc.RUNNER_FILTERS if f["a"][0] == "mark"]
        self.assertEqual(len(marks), len(set(marks)))
        self.assertEqual(set(marks), set(sc.RUNNER_EXPECT) | set(sc.RUNNER_EXPECT_NOT_ONLY))
        self.assertEqual(set(sc.RUNNER_EXPECT_LATER) - set(marks), set())

    def test_a_value_comes_back_from_the_page_and_an_exception_is_an_error(self):
        class Tab:
            def __init__(self, reply):
                self.reply = reply

            def call(self, method, **params):
                return self.reply

        self.assertEqual(sc._evaluate(Tab({"result": {"type": "string", "value": "ok"}}), "1"), "ok")
        self.assertIsNone(sc._evaluate(Tab({"result": {"type": "undefined"}}), "1"))
        with self.assertRaises(RuntimeError):
            sc._evaluate(Tab({"result": {"type": "object"}, "exceptionDetails": {"text": "Uncaught"}}), "1")

    def test_marks_are_compared_as_sets(self):
        expect = {"m1": ["a", "b"], "m2": []}
        self.assertEqual(sc.runner_problems(expect, {"m1": ["b", "a"], "m2": []}), [])
        found = sc.runner_problems(expect, {"m1": ["a"], "m2": ["x"]})
        self.assertEqual(len(found), 2)
        self.assertIn("m1", found[0])
        self.assertEqual(len(sc.runner_problems(expect, {})), 1)   # m1 missing; m2 expects nothing


if __name__ == "__main__":
    unittest.main()
