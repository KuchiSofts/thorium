# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Offline benchmark harness (ROADMAP Q.1)."""
import json
import time
import unittest
import urllib.request

from tools.qa import bench

PROCS = [
    {"pid": 1, "ppid": 0, "ws": 100, "cpu": 5.0},
    {"pid": 10, "ppid": 1, "ws": 1000, "cpu": 1.0},     # browser
    {"pid": 11, "ppid": 10, "ws": 200, "cpu": 0.5},     # renderer
    {"pid": 12, "ppid": 10, "ws": 300, "cpu": 0.25},    # gpu
    {"pid": 13, "ppid": 11, "ws": 50, "cpu": 0.25},     # grandchild
    {"pid": 20, "ppid": 1, "ws": 9999, "cpu": 9.0},     # unrelated
]


class TreeTests(unittest.TestCase):
    def test_tree_includes_every_descendant_and_nothing_else(self):
        self.assertEqual(sorted(p["pid"] for p in bench.tree(PROCS, 10)), [10, 11, 12, 13])

    def test_totals(self):
        self.assertEqual(bench.total(PROCS, 10, "ws"), 1550)
        self.assertEqual(bench.total(PROCS, 10, "cpu"), 2.0)

    def test_missing_root_is_an_error(self):
        with self.assertRaises(bench.BenchError):
            bench.tree(PROCS, 99)


class StatsTests(unittest.TestCase):
    def test_median_and_spread(self):
        s = bench.summarise([100.0, 102.0, 98.0, 101.0, 99.0])
        self.assertEqual(s["median"], 100.0)
        self.assertAlmostEqual(s["spread_pct"], 4.0)
        self.assertEqual(s["runs"], 5)
        self.assertFalse(s["repeatable"])           # 4 % > 3 %

    def test_repeatable_within_three_percent(self):
        self.assertTrue(bench.summarise([100.0, 101.0, 99.5])["repeatable"])

    def test_needs_three_runs(self):
        with self.assertRaises(bench.BenchError):
            bench.summarise([1.0, 2.0])


class PingServerTests(unittest.TestCase):
    def test_records_the_first_ping_and_serves_the_page(self):
        with bench.PingServer() as server:
            page = urllib.request.urlopen(server.url("page"), timeout=5).read().decode("utf-8")
            self.assertIn("/ping", page)
            self.assertNotIn("http://", page.replace(server.base, ""))   # nothing outside the local server
            t0 = time.monotonic()
            urllib.request.urlopen(server.url("ping"), timeout=5).read()
            self.assertTrue(server.wait(5))
            self.assertGreaterEqual(server.first_ping, t0)

    def test_listens_on_loopback_only(self):
        with bench.PingServer() as server:
            self.assertTrue(server.base.startswith("http://127.0.0.1:"))


class ReportTests(unittest.TestCase):
    def test_markdown_and_json(self):
        results = {"browser": "thoron.exe", "version": "158.0.8127.30",
                   "startup_ms": bench.summarise([500.0, 505.0, 495.0])}
        md = bench.to_markdown(results)
        self.assertIn("| startup_ms | 500.0 | 2.0 % | 3 | yes |", md)
        json.loads(json.dumps(results))


if __name__ == "__main__":
    unittest.main()
