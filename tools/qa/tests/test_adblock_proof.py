# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, proof measurements: the offline comparison (ROADMAP P5.17)."""
import json
import unittest
import urllib.error
import urllib.request

from tools.qa import adblock_proof as ap


def get(port: int, host: str, path: str) -> tuple[int, bytes]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": host})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read()


class PageTests(unittest.TestCase):
    def test_every_resource_id_is_unique_and_every_child_exists(self):
        ids = [r["id"] for r in ap.RESOURCES]
        self.assertEqual(len(ids), len(set(ids)))
        for r in ap.RESOURCES:
            for child in r.get("children", []):
                self.assertIn(child, ids)

    def test_every_page_has_ads_trackers_and_needed_resources(self):
        for name in ap.PAGES:
            groups = {ap.BY_ID[i]["group"] for i in ap.expected(name)}
            self.assertEqual(groups, {"ad", "tracker", "needed"}, name)

    def test_expected_includes_the_resources_that_ad_scripts_load_themselves(self):
        self.assertIn("gpt", ap.PAGES["news"])
        self.assertNotIn("dc-pixel", ap.PAGES["news"])
        self.assertIn("dc-pixel", ap.expected("news"))

    def test_the_page_asks_for_its_resources_with_the_run_id_and_never_for_children(self):
        html = ap.page_html("news", "run7", 4321)
        self.assertIn("http://securepubads.g.doubleclick.net/tag/js/gpt.js?r=run7", html)
        self.assertNotIn("ad.doubleclick.net", html)
        self.assertIn("/result", html)

    def test_only_the_test_hosts_resolve_and_all_go_to_the_local_server(self):
        rules = ap.resolver_rules(4321)
        self.assertIn("MAP securepubads.g.doubleclick.net 127.0.0.1:4321", rules)
        self.assertIn("MAP * ~NOTFOUND", rules)
        self.assertTrue(rules.endswith("EXCLUDE 127.0.0.1"))


class ServerTests(unittest.TestCase):
    def test_requests_are_recorded_per_run_and_scripts_ask_for_their_children(self):
        with ap.ProofServer(remote_delay_ms=0) as s:
            code, body = get(s.port, "securepubads.g.doubleclick.net", "/tag/js/gpt.js?r=a")
            self.assertEqual(code, 200)
            self.assertIn(b"http://ad.doubleclick.net/ddm/ad/x.gif?r=a", body)
            get(s.port, "ad.doubleclick.net", "/ddm/ad/x.gif?r=a")
            get(s.port, "cdn.jsdelivr.net", "/npm/lib@1/lib.min.js?r=b")
            self.assertEqual(s.hits["a"], {"gpt", "dc-pixel"})
            self.assertEqual(s.hits["b"], {"jsdelivr"})

    def test_the_page_result_is_kept_per_run(self):
        with ap.ProofServer(remote_delay_ms=0) as s:
            req = urllib.request.Request(f"http://127.0.0.1:{s.port}/result", method="POST",
                                         data=json.dumps({"run": "a", "load": 123.4}).encode())
            urllib.request.urlopen(req, timeout=10).read()
            self.assertEqual(s.results["a"]["load"], 123.4)

    def test_the_ublock_probe_is_ready_after_three_sockets_in_a_row_did_not_arrive(self):
        def tick(s, n):
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{s.port}/tick?n={n}", method="POST",
                                                          data=b""), timeout=10).read()
        with ap.ProofServer(remote_delay_ms=0) as s:
            with self.assertRaises(urllib.error.HTTPError):
                get(s.port, "pagead2.googlesyndication.com", "/ws?n=0")
            for n in (0, 1, 2):          # 0 arrived: the count starts again
                tick(s, n)
            self.assertFalse(s.ready.is_set())
            tick(s, 3)
            self.assertTrue(s.ready.is_set())

    def test_run_names_in_urls_have_no_plus(self):
        self.assertNotIn("+", ap.page_html("news", "native-ubo-news-0", 1).split("?r=")[1][:20])

    def test_pages_are_served_only_on_the_local_host_name(self):
        with ap.ProofServer(remote_delay_ms=0) as s:
            code, body = get(s.port, f"127.0.0.1:{s.port}", "/page/recipe?r=x")
            self.assertIn(b"<title>recipe</title>", body)
            with self.assertRaises(urllib.error.HTTPError):
                get(s.port, "cdn.jsdelivr.net", "/page/recipe?r=x")


class StandInTests(unittest.TestCase):
    def test_page_scripts_report_how_they_ended(self):
        html = ap.page_html("news", "run7", 4321)
        self.assertIn("__ok('chartbeat')", html)
        self.assertIn("__er('chartbeat')", html)
        self.assertLess(html.index("window.__ok"), html.index("<script src="))   # before any script loads
        self.assertIn("ok: window.__okl", html)

    def test_a_real_ad_script_marks_itself(self):
        with ap.ProofServer(remote_delay_ms=0) as s:
            _, body = get(s.port, "static.chartbeat.com", "/js/chartbeat.js?r=a")
            self.assertIn(b'window.__real || []).push("chartbeat")', body)

    def test_stand_ins_are_scripts_that_loaded_without_reaching_the_server(self):
        result = {"ok": ["jquery", "chartbeat", "gpt"], "er": ["taboola"], "real": ["jquery"]}
        self.assertEqual(ap.stand_ins(result, hits={"jquery"}), ["chartbeat", "gpt"])
        self.assertEqual(ap.stand_ins({}, hits=set()), [])
        # a script the server answered is never a stand-in, even when its marker is missing
        self.assertEqual(ap.stand_ins({"ok": ["gpt"], "real": []}, hits={"gpt"}), [])
        # only scripts are judged this way
        self.assertEqual(ap.stand_ins({"ok": ["ytimg", "nonsense"], "real": []}, hits=set()), [])


class CountTests(unittest.TestCase):
    def test_no_test_host_is_one_the_browser_forces_to_https(self):
        preloaded = ("google-analytics.com", "facebook.com", "facebook.net", "bing.com", "cloudflare.com",
                     "unpkg.com", "stats.g.doubleclick.net")
        for r in ap.RESOURCES:
            self.assertFalse(r["host"].endswith(preloaded), r["host"])

    def test_reached_counts_split_ads_trackers_and_missing_needed(self):
        hits = set(ap.expected("blog")) - {"gtm", "jsdelivr"}
        c = ap.count("blog", hits)
        want = ap.expected("blog")
        ads = sum(1 for i in want if ap.BY_ID[i]["group"] != "needed")
        self.assertEqual(c["possible"], ads)
        self.assertEqual(c["reached"], ads - 1)
        self.assertEqual(c["needed_missing"], ["jsdelivr"])


class SettleTests(unittest.TestCase):
    def test_quiet_needs_three_small_steps_in_a_row(self):
        self.assertFalse(ap.quiet([1.0, 1.05, 1.1]))
        self.assertTrue(ap.quiet([1.0, 3.0, 3.05, 3.1, 3.12]))
        self.assertFalse(ap.quiet([1.0, 1.05, 1.1, 2.0]))


class VerdictTests(unittest.TestCase):
    def mode(self, reached, load, cpu, mem1, mem20, missing=0):
        return {"valid": True, "reached": reached, "possible": 40, "needed_missing": missing, "load_ms": load,
                "cpu_s_per_load": cpu, "memory_mb_1": mem1, "memory_mb_20": mem20}

    def test_all_targets_met(self):
        v = ap.verdict(self.mode(2, 80.0, 0.20, 300.0, 900.0), self.mode(2, 100.0, 0.30, 400.0, 1000.0))
        self.assertTrue(all(t["met"] for t in v))
        self.assertEqual([t["target"] for t in v], ["blocking", "load time", "cpu", "memory, 1 tab",
                                                    "memory, 20 tabs", "breakage (test pages)", "stand-ins"])

    def test_load_time_needs_ten_percent(self):
        v = {t["target"]: t["met"] for t in
             ap.verdict(self.mode(2, 95.0, 0.20, 300.0, 900.0), self.mode(2, 100.0, 0.30, 400.0, 1000.0))}
        self.assertFalse(v["load time"])
        self.assertTrue(v["blocking"])

    def test_more_ads_through_more_memory_or_new_breakage_fail(self):
        v = {t["target"]: t["met"] for t in
             ap.verdict(self.mode(3, 80.0, 0.20, 401.0, 900.0, missing=1),
                        self.mode(2, 100.0, 0.30, 400.0, 1000.0))}
        self.assertFalse(v["blocking"])
        self.assertFalse(v["memory, 1 tab"])
        self.assertTrue(v["memory, 20 tabs"])
        self.assertFalse(v["breakage (test pages)"])

    def test_fewer_stand_ins_than_ublock_origin_fail(self):
        ubo = dict(self.mode(2, 100.0, 0.30, 400.0, 1000.0), stand_ins=5)
        fewer = dict(self.mode(2, 80.0, 0.20, 300.0, 900.0), stand_ins=3)
        same = dict(self.mode(2, 80.0, 0.20, 300.0, 900.0), stand_ins=5)
        self.assertFalse({t["target"]: t["met"] for t in ap.verdict(fewer, ubo)}["stand-ins"])
        self.assertTrue({t["target"]: t["met"] for t in ap.verdict(same, ubo)}["stand-ins"])

    def test_an_invalid_run_meets_nothing(self):
        bad = dict(self.mode(2, 80.0, 0.20, 300.0, 900.0), valid=False)
        self.assertFalse(any(t["met"] for t in ap.verdict(bad, self.mode(2, 100.0, 0.30, 400.0, 1000.0))))


class ReportTests(unittest.TestCase):
    def test_markdown_names_every_mode_and_target_and_uses_only_short_dashes(self):
        m = {"valid": True, "reached": 2, "possible": 40, "needed_missing": 0, "load_ms": 80.0,
             "load_spread_pct": 4.0, "cpu_s_per_load": 0.2, "memory_mb_1": 300.0, "memory_mb_20": 900.0}
        results = {"browser_version": "158.0.0.0", "runs": 5, "remote_delay_ms": 40,
                   "modes": {k: dict(m) for k in ap.MODES},
                   "verdicts": {"native": ap.verdict(m, m), "native+ubo": ap.verdict(m, m)}}
        md = ap.to_markdown(results)
        for k in ap.MODES:
            self.assertIn(f"| {k} |", md)
        self.assertIn("load time", md)
        for dash in (chr(0x2013), chr(0x2014)):
            self.assertNotIn(dash, md)


if __name__ == "__main__":
    unittest.main()
