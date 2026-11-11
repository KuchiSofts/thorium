# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, breakage on popular sites (ROADMAP P5.17)."""
import unittest

from tools.qa import adblock_breakage as ab


class SiteTests(unittest.TestCase):
    def test_site_of_keeps_the_registrable_part(self):
        self.assertEqual(ab.site_of("www.bbc.co.uk"), "bbc.co.uk")
        self.assertEqual(ab.site_of("static.xx.fbcdn.net"), "fbcdn.net")
        self.assertEqual(ab.site_of("en.wikipedia.org"), "wikipedia.org")
        self.assertEqual(ab.site_of("WWW.Example.COM."), "example.com")
        self.assertEqual(ab.site_of("127.0.0.1"), "127.0.0.1")

    def test_tranco_csv_is_read_in_rank_order(self):
        rows = ab.read_tranco("2,b.com\n1,a.com\n\n3,c.org\n")
        self.assertEqual(rows, ["a.com", "b.com", "c.org"])

    def test_only_sites_that_serve_their_own_page_are_picked(self):
        big = 50000
        answers = {
            "a.com": ("https://www.a.com/", 200, "text/html; charset=utf-8", big, "A"),
            "cdn.net": ("https://cdn.net/", 403, "text/html", big, "Forbidden"),
            "short.ly": ("https://other.com/landing", 200, "text/html", big, "Other"),
            "api.io": ("https://api.io/", 200, "application/json", big, ""),
            "tiny.net": ("https://tiny.net/", 200, "text/html", 900, "Parked"),
            "untitled.net": ("https://untitled.net/", 200, "text/html", big, ""),
            "astrumu.io": ("https://astrumu.io/", 200, "text/html", big, "astrumu.io"),
            "b.org": ("https://b.org/home", 200, "text/html", big, "B"),
            "c.com": None,
        }
        picked = ab.pick_sites(list(answers), lambda d: answers[d], 5)
        self.assertEqual(picked, ["a.com", "b.org"])

    def test_title_is_read_and_unescaped(self):
        self.assertEqual(ab.page_title(b"<html><TITLE lang=en> Fish &amp; Chips </title>"), "Fish & Chips")
        self.assertEqual(ab.page_title(b"<html>"), "")

    def test_domains_can_be_left_out_on_request_without_being_named_in_the_list(self):
        answer = lambda d: (f"https://{d}/", 200, "text/html", 50000, d)
        picked = ab.pick_sites(["a.com", "b.com", "c.com"], answer, 5, exclude={"b.com"})
        self.assertEqual(picked, ["a.com", "c.com"])
        text = ab.site_list_text(picked, "Y895G", "2026-11-10", left_out=1)
        self.assertIn("1 more", text)
        self.assertNotIn("b.com", text)
        self.assertEqual(ab.read_site_list(text), ["a.com", "c.com"])
        self.assertNotIn("more left out", ab.site_list_text(picked, "Y895G", "2026-11-10"))

    def test_picking_stops_at_n(self):
        self.assertEqual(ab.pick_sites(["a.com", "b.com", "c.com"],
                                       lambda d: (f"https://{d}/", 200, "text/html", 50000, d), 2), ["a.com", "b.com"])

    def test_site_list_file_round_trip_ignores_comments(self):
        text = ab.site_list_text(["a.com", "b.org"], "Y895G", "2026-11-10")
        self.assertIn("Tranco", text)
        self.assertEqual(ab.read_site_list(text), ["a.com", "b.org"])


class EventTests(unittest.TestCase):
    def events(self):
        return [
            {"method": "Network.requestWillBeSent", "params": {"requestId": "1", "request": {"url": "https://www.a.com/app.js"}}},
            {"method": "Network.requestWillBeSent", "params": {"requestId": "2", "request": {"url": "https://ads.x.net/ad.js"}}},
            {"method": "Network.requestWillBeSent", "params": {"requestId": "3", "request": {"url": "https://static.a.com/ads/banner.js"}}},
            {"method": "Network.loadingFailed", "params": {"requestId": "2", "errorText": "net::ERR_BLOCKED_BY_CLIENT"}},
            {"method": "Network.loadingFailed", "params": {"requestId": "3", "errorText": "net::ERR_BLOCKED_BY_CLIENT"}},
            {"method": "Network.loadingFailed", "params": {"requestId": "1", "errorText": "net::ERR_CONNECTION_RESET"}},
            {"method": "Runtime.exceptionThrown", "params": {}},
            {"method": "Page.loadEventFired", "params": {}},
        ]

    def test_summary_counts_blocked_first_party_and_errors(self):
        s = ab.summarise("a.com", self.events(), text_length=1234)
        self.assertEqual(s["blocked"], 2)
        self.assertEqual(s["first_party_blocked"], ["static.a.com/ads/banner.js"])
        self.assertEqual(s["exceptions"], 1)
        self.assertTrue(s["loaded"])
        self.assertEqual(s["text"], 1234)

    def test_ids_in_first_party_paths_are_replaced(self):
        self.assertEqual(ab.id_free("/b/ss/store/1/JS-2.23.0/s45682505144145"), "/b/ss/store/1/JS-2.23.0/s*")
        self.assertEqual(ab.id_free("/clientlibs/v1.ACSHASHbf7b336dbb370c984e1bf.js"), "/clientlibs/v1.ACSHASH*.js")
        self.assertEqual(ab.id_free("/youtubei/v1/log_event"), "/youtubei/v1/log_event")

    def test_first_party_urls_are_kept_without_query(self):
        ev = [{"method": "Network.requestWillBeSent", "params": {"requestId": "9", "request": {
                  "url": "https://a.com/t.gif?uid=secret&x=1"}}},
              {"method": "Network.loadingFailed", "params": {"requestId": "9", "errorText": "net::ERR_BLOCKED_BY_CLIENT"}}]
        self.assertEqual(ab.summarise("a.com", ev, 0)["first_party_blocked"], ["a.com/t.gif"])


class ReadyTests(unittest.TestCase):
    def test_a_block_or_an_extension_stand_in_means_the_blocker_acted(self):
        blocked = [{"method": "Network.loadingFailed", "params": {"errorText": "net::ERR_BLOCKED_BY_CLIENT"}}]
        stand_in = [{"method": "Network.requestWillBeSent",
                     "params": {"request": {"url": "chrome-extension://abc/web_accessible_resources/noop.js"}}}]
        other = [{"method": "Network.loadingFailed", "params": {"errorText": "net::ERR_NAME_NOT_RESOLVED"}}]
        self.assertTrue(ab.blocker_acted(blocked))
        self.assertTrue(ab.blocker_acted(stand_in))
        self.assertFalse(ab.blocker_acted(other))

    def test_the_browser_is_not_started_with_a_user_agent_switch(self):
        import inspect
        self.assertNotIn("--user-agent", inspect.getsource(ab._launch))


class CompareTests(unittest.TestCase):
    def run_(self, loaded=True, blocked=10, fp=(), exc=0, text=5000):
        return {"loaded": loaded, "blocked": blocked, "first_party_blocked": list(fp), "exceptions": exc,
                "text": text, "error": None}

    def test_same_result_has_no_flag(self):
        self.assertEqual(ab.compare(self.run_(), self.run_()), [])

    def test_each_kind_of_breakage_is_flagged(self):
        ubo = self.run_()
        self.assertIn("did not load", ab.compare(self.run_(loaded=False), ubo)[0])
        self.assertIn("first-party", ab.compare(self.run_(fp=["a.com/x.js"]), ubo)[0])
        self.assertIn("script errors", ab.compare(self.run_(exc=3), ubo)[0])
        self.assertIn("less text", ab.compare(self.run_(text=2000), ubo)[0])

    def test_small_differences_are_not_breakage(self):
        ubo = self.run_(exc=2, text=5000)
        self.assertEqual(ab.compare(self.run_(exc=3, text=4000), ubo), [])
        self.assertEqual(ab.compare(self.run_(text=50), self.run_(text=150)), [])   # both nearly empty

    def test_first_party_blocks_uBlock_also_makes_are_not_new(self):
        self.assertEqual(ab.compare(self.run_(fp=["a.com/ads.js"]), self.run_(fp=["a.com/ads.js", "a.com/b.js"])), [])

    def test_a_site_that_failed_for_the_reference_is_not_judged(self):
        self.assertIsNone(ab.compare(self.run_(), dict(self.run_(loaded=False), error="timeout")))

    def test_flags_must_repeat_to_count(self):
        self.assertEqual(ab.confirmed(["less text (2000 vs 5000)"], ["less text (2100 vs 5000)", "script errors"]),
                         ["less text (2000 vs 5000)"])
        self.assertEqual(ab.confirmed(["did not load"], []), [])


class ReportTests(unittest.TestCase):
    def test_markdown_lists_flagged_sites_and_uses_short_dashes(self):
        results = {"list": "Tranco Y895G", "browser_version": "158", "sites": 2,
                   "modes": ["ubo", "native"],
                   "per_site": {"a.com": {"ubo": {"loaded": True, "blocked": 4, "exceptions": 0, "text": 900,
                                                  "first_party_blocked": [], "error": None},
                                          "native": {"loaded": True, "blocked": 6, "exceptions": 0, "text": 300,
                                                     "first_party_blocked": [], "error": None}}},
                   "flags": {"native": {"a.com": ["less text (300 vs 900)"]}},
                   "judged": {"native": 1}}
        md = ab.to_markdown(results)
        self.assertIn("a.com", md)
        self.assertIn("less text", md)
        for dash in (chr(0x2013), chr(0x2014)):
            self.assertNotIn(dash, md)


if __name__ == "__main__":
    unittest.main()
