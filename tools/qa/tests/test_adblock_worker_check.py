# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, worker scripts, prefetches and WebSockets: the offline check (ROADMAP P5.27, P5.29)."""
import unittest

from tools.qa import adblock_worker_check as wc

LISTS = """! thoron-list: easylist
||ads.example^
/banner/*/img^
/track.js$third-party
/tools/pgout.js
/other/second.js
news.example##.ad
"""
PATH = "/tools/pgout.js"


def seen(ad=(), page=None):
    return {"ad": sorted(ad), "page": page or {}}


class PathTests(unittest.TestCase):
    def test_the_first_plain_rule_for_a_script_path_is_taken(self):
        self.assertEqual(wc.blocked_path(LISTS), PATH)

    def test_rules_with_options_wildcards_or_hosts_are_not_plain(self):
        self.assertIsNone(wc.blocked_path("||ads.example^\n/track.js$third-party\n/a*b.js\n/x.js^\n"))
        self.assertIsNone(wc.blocked_path(""))


class PageTests(unittest.TestCase):
    def test_the_page_starts_every_kind_of_worker_and_a_prefetch(self):
        html = wc.page_html(PATH)
        self.assertIn("new Worker('/plain-worker.js')", html)
        self.assertIn("new Worker('/module-worker.js', {type: 'module'})", html)
        self.assertIn(f"new Worker('{PATH}?kind=worker')", html)
        self.assertIn(f"new SharedWorker('{PATH}?kind=shared')", html)
        self.assertIn("serviceWorker.register('/service.js')", html)
        self.assertIn(f'<link rel="prefetch" href="http://{wc.AD_HOST}/prefetch.js"', html)
        self.assertIn(f"new WebSocket('ws://{wc.AD_HOST}/ad-socket')", html)
        self.assertIn("new WebSocket('ws://' + location.host + '/plain-socket')", html)
        self.assertIn("/result/page", html)

    def test_the_service_worker_imports_from_the_ad_host_and_survives_a_refusal(self):
        script = wc.service_worker_js()
        self.assertIn(f"importScripts('http://{wc.AD_HOST}/sw-import.js')", script)
        self.assertIn("catch", script)


class ProblemTests(unittest.TestCase):
    def blocked(self):
        result = {"plainWorker": True, "moduleWorker": True, "registered": True, "blockedWorker": "failed",
                  "blockedShared": "failed", "plainSocket": "open", "adSocket": "failed"}
        log = seen(page={"/plain-worker.js": [""], "/service.js": [""]})
        return result, log

    def untouched(self):
        result = {"plainWorker": True, "moduleWorker": True, "registered": True, "blockedWorker": "ran",
                  "blockedShared": "ran", "plainSocket": "open", "adSocket": "open"}
        log = seen(ad=["/ad-socket", "/prefetch.js", "/sw-import.js"],
                   page={"/plain-worker.js": [""], "/service.js": [""], PATH: ["kind=worker", "kind=shared"]})
        return result, log

    def test_with_blocking_on_nothing_blocked_is_fetched(self):
        result, log = self.blocked()
        self.assertEqual(wc.problems("native", PATH, result, log), [])
        result, log = self.untouched()
        self.assertEqual(len(wc.problems("native", PATH, result, log)), 5)

    def test_with_blocking_off_everything_runs(self):
        for mode in ("control", "site-off"):
            result, log = self.untouched()
            self.assertEqual(wc.problems(mode, PATH, result, log), [], mode)
            result, log = self.blocked()
            self.assertEqual(len(wc.problems(mode, PATH, result, log)), 5, mode)

    def test_each_kind_is_named(self):
        result, log = self.blocked()
        log["page"][PATH] = ["kind=shared"]
        result["blockedShared"] = "ran"
        found = wc.problems("native", PATH, result, log)
        self.assertEqual(len(found), 1)
        self.assertIn("shared worker", found[0])
        result, log = self.blocked()
        log["ad"] = ["/sw-import.js"]
        found = wc.problems("native", PATH, result, log)
        self.assertEqual(len(found), 1)
        self.assertIn("service worker", found[0])
        result, log = self.blocked()
        log["ad"] = ["/prefetch.js"]
        found = wc.problems("native", PATH, result, log)
        self.assertEqual(len(found), 1)
        self.assertIn("prefetch", found[0])

    def test_what_is_not_blocked_must_work_in_every_mode(self):
        for mode, case in (("native", self.blocked()), ("control", self.untouched())):
            result, log = case
            result["plainWorker"] = False
            found = wc.problems(mode, PATH, result, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("plain worker", found[0])
            result["plainWorker"], result["moduleWorker"] = True, False
            found = wc.problems(mode, PATH, result, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("module worker", found[0])
            result["moduleWorker"], result["registered"] = True, False
            found = wc.problems(mode, PATH, result, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("service worker", found[0])

    def test_a_socket_to_the_ad_host_is_named(self):
        result, log = self.blocked()
        log["ad"] = ["/ad-socket"]
        result["adSocket"] = "open"
        found = wc.problems("native", PATH, result, log)
        self.assertEqual(len(found), 1)
        self.assertIn("WebSocket", found[0])

    def test_a_plain_socket_must_open_in_every_mode(self):
        for mode, case in (("native", self.blocked()), ("control", self.untouched())):
            result, log = case
            result["plainSocket"] = "failed"
            found = wc.problems(mode, PATH, result, log)
            self.assertEqual(len(found), 1, mode)
            self.assertIn("plain WebSocket", found[0])

    def test_the_server_answers_a_websocket_handshake(self):
        # RFC 6455, section 1.3: the example key and its accept value
        self.assertEqual(wc.websocket_accept("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    def test_no_result_is_a_problem(self):
        self.assertEqual(wc.problems("native", PATH, None, seen()), ["the page gave no result"])

    def test_an_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            wc.problems("other", PATH, {}, seen())


if __name__ == "__main__":
    unittest.main()
