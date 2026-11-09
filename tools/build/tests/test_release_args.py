# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron's release build configuration (ROADMAP P2.17)."""
import tempfile
import unittest
from pathlib import Path

from tools.build import release_args as ra

# Excerpt of upstream Thorium's other/AVX2/win_AVX2_args.gn (gz83 efc0fff).
UPSTREAM_WIN = """thorium_x86_profile = "avx2_fma"
target_os = "win"
is_official_build = true
disable_fieldtrial_testing_config = true
enable_reporting = false
enable_widevine = true
bundle_widevine_cdm = true
enable_cdm_storage_id = true
enable_rlz = true # promo
enable_hangout_services_extension = false
chrome_pgo_phase = 2
"""
UPSTREAM_LINUX = """thorium_x86_profile = "avx2_fma"
target_os = "linux"
enable_reporting = false
enable_widevine = true
bundle_widevine_cdm = true
enable_hangout_services_extension = false
disable_fieldtrial_testing_config = true
"""


class ComposeTests(unittest.TestCase):
    def test_privacy_overrides_win(self):
        args = ra.parse(ra.compose(UPSTREAM_WIN, "win", "upstream win_AVX2_args.gn"))
        self.assertEqual(args["enable_rlz"], "false")
        self.assertEqual(args["enable_cdm_storage_id"], "false")
        self.assertEqual(args["bundle_widevine_cdm"], "false")
        self.assertEqual(args["use_official_google_api_keys"], "false")   # added: upstream does not set it
        self.assertEqual(args["enable_widevine"], "true")
        self.assertEqual(args["enable_reporting"], "false")

    def test_other_upstream_args_are_kept_unchanged_and_in_order(self):
        out = ra.compose(UPSTREAM_WIN, "win", "upstream")
        lines = [l for l in out.splitlines() if l and not l.startswith("#")]
        self.assertEqual(lines[0], 'thorium_x86_profile = "avx2_fma"')
        self.assertIn("chrome_pgo_phase = 2", lines)
        self.assertLess(lines.index('target_os = "win"'), lines.index("chrome_pgo_phase = 2"))

    def test_every_decision_carries_its_reason_on_its_line(self):
        out = ra.compose(UPSTREAM_WIN, "win", "upstream")
        for d in ra.decisions("win"):
            line = next(l for l in out.splitlines() if l.startswith(d.name + " = "))
            self.assertIn("# Thoron: ", line, d.name)
            self.assertIn(d.reason[:30], line, d.name)

    def test_linux_gets_the_same_privacy_values(self):
        args = ra.parse(ra.compose(UPSTREAM_LINUX, "linux", "upstream AVX2_args.gn"))
        self.assertEqual(args["bundle_widevine_cdm"], "false")
        self.assertEqual(args["enable_rlz"], "false")
        self.assertEqual(args["use_official_google_api_keys"], "false")

    def test_idempotent(self):
        once = ra.compose(UPSTREAM_WIN, "win", "upstream")
        self.assertEqual(ra.compose(once, "win", "upstream"), once)

    def test_header_names_the_source_and_the_tool(self):
        out = ra.compose(UPSTREAM_WIN, "win", "gz83 efc0fff other/AVX2/win_AVX2_args.gn")
        self.assertIn("gz83 efc0fff other/AVX2/win_AVX2_args.gn", out.splitlines()[0])
        self.assertIn("tools/build/release_args.py", out.splitlines()[0])

    def test_unknown_platform_raises(self):
        with self.assertRaises(ra.ArgsError):
            ra.compose(UPSTREAM_WIN, "mac", "upstream")

    def test_duplicate_upstream_arg_raises(self):
        with self.assertRaisesRegex(ra.ArgsError, "enable_rlz"):
            ra.compose(UPSTREAM_WIN + "enable_rlz = true\n", "win", "upstream")


class CheckTests(unittest.TestCase):
    def test_composed_args_pass(self):
        self.assertEqual(ra.check(ra.compose(UPSTREAM_WIN, "win", "u"), "win"), [])
        self.assertEqual(ra.check(ra.compose(UPSTREAM_LINUX, "linux", "u"), "linux"), [])

    def test_upstream_args_fail_with_named_problems(self):
        problems = "\n".join(ra.check(UPSTREAM_WIN, "win"))
        for name in ("enable_rlz", "enable_cdm_storage_id", "bundle_widevine_cdm", "use_official_google_api_keys"):
            self.assertIn(name, problems)

    def test_google_api_keys_are_refused(self):
        args = ra.compose(UPSTREAM_WIN, "win", "u") + 'google_api_key = "AIzaSyExample"\n'
        self.assertTrue([p for p in ra.check(args, "win") if "google_api_key" in p])

    def test_empty_google_api_key_is_fine(self):
        args = ra.compose(UPSTREAM_WIN, "win", "u") + 'google_default_client_id = ""\n'
        self.assertEqual(ra.check(args, "win"), [])

    def test_cli_compose_then_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            up, out = Path(tmp) / "win_AVX2_args.gn", Path(tmp) / "args.gn"
            up.write_text(UPSTREAM_WIN, encoding="utf-8")
            self.assertEqual(ra.main(["compose", "--upstream", str(up), "--platform", "win", "--source", "u",
                                      "--out", str(out)]), 0)
            self.assertEqual(ra.main(["check", "--args", str(out), "--platform", "win"]), 0)
            self.assertEqual(ra.main(["check", "--args", str(up), "--platform", "win"]), 1)


class DecisionTableTests(unittest.TestCase):
    def test_reasons_are_plain_and_house_style(self):
        for d in ra.DECISIONS:
            self.assertTrue(d.reason and d.reason[0].isupper(), d.name)
            self.assertNotIn(chr(0x2014), d.reason)
            self.assertNotIn(chr(0x2013), d.reason)
            self.assertNotIn("\n", d.reason)

    def test_no_decision_is_listed_twice_per_platform(self):
        for platform in ra.PLATFORMS:
            names = [d.name for d in ra.decisions(platform)]
            self.assertEqual(len(names), len(set(names)), platform)


if __name__ == "__main__":
    unittest.main()
