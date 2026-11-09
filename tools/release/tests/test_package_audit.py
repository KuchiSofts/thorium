# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""What a Thoron package may contain (ROADMAP P2.6, P2.20, P2.21)."""
import tempfile
import unittest
from pathlib import Path

from tools.release import package_audit as pa

GOOD_WIN = ["Chrome-bin/thoron.exe", "Chrome-bin/chrome_proxy.exe", "Chrome-bin/158.0.8127.3000/chrome.dll",
            "Chrome-bin/158.0.8127.3000/Installer/setup.exe", "Chrome-bin/158.0.8127.3000/Locales/en-US.pak",
            "Chrome-bin/158.0.8127.3000/resources.pak", "Chrome-bin/158.0.8127.3000/chrome_elf.dll"]
GOOD_LINUX = ["opt/kuchisofts/thoron/thoron", "opt/kuchisofts/thoron/thoron-browser",
              "usr/bin/thoron-browser", "usr/share/applications/thoron-browser.desktop",
              "opt/kuchisofts/thoron/chromedriver", "opt/kuchisofts/thoron/locales/en-US.pak"]


class AuditTests(unittest.TestCase):
    def test_clean_packages_pass(self):
        self.assertEqual(pa.audit(GOOD_WIN, "win"), [])
        self.assertEqual(pa.audit(GOOD_LINUX, "linux"), [])

    def test_bundled_widevine_is_refused(self):
        for name in ("Chrome-bin/158.0.8127.3000/WidevineCdm/_platform_specific/win_x64/widevinecdm.dll",
                     "opt/kuchisofts/thoron/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so"):
            problems = pa.audit(GOOD_WIN + [name], "win")
            self.assertTrue([p for p in problems if "Widevine" in p], name)

    def test_names_after_thorium_are_refused(self):
        for name in ("Chrome-bin/thorium.exe", "Chrome-bin/158.0.8127.3000/thorium.ico",
                     "usr/bin/thorium-browser", "opt/chromium.org/thorium/thorium"):
            self.assertTrue(pa.audit([name], "win"), name)

    def test_upstream_only_tools_are_refused(self):
        for name in ("Chrome-bin/thor_ver", "usr/bin/pak", "opt/kuchisofts/thoron/pak",
                     "usr/bin/thorium-shell", "Chrome-bin/158.0.8127.3000/thorium_shell.exe",
                     "opt/kuchisofts/thoron/content_shell.pak"):
            self.assertTrue(pa.audit([name], "linux"), name)

    def test_the_program_must_be_there(self):
        self.assertTrue([p for p in pa.audit(GOOD_WIN[1:], "win") if "thoron.exe" in p])
        self.assertTrue([p for p in pa.audit(GOOD_LINUX[1:], "linux") if "thoron" in p])

    def test_credit_text_files_are_allowed(self):
        # licence and credits files may name Thorium; they are text, not product names
        self.assertEqual(pa.audit(GOOD_WIN + ["Chrome-bin/158.0.8127.3000/credits_thorium.html"], "win"), [])

    def test_7z_listing_is_parsed(self):
        listing = ("7-Zip 25.01\n\nListing archive: chrome.7z\n\n--\nPath = chrome.7z\nType = 7z\n\n----------\n"
                   "Path = Chrome-bin\nFolder = +\n\nPath = Chrome-bin\\thoron.exe\nFolder = -\nSize = 10\n\n"
                   "Path = Chrome-bin\\158.0.8127.3000\\chrome.dll\nFolder = -\n")
        self.assertEqual(pa.parse_7z_listing(listing),
                         ["Chrome-bin", "Chrome-bin/thoron.exe", "Chrome-bin/158.0.8127.3000/chrome.dll"])

    def test_cli_on_a_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in GOOD_WIN:
                (root / n).parent.mkdir(parents=True, exist_ok=True)
                (root / n).write_bytes(b"x")
            self.assertEqual(pa.main(["--dir", str(root), "--platform", "win"]), 0)
            (root / "Chrome-bin/thor_ver").write_bytes(b"x")
            self.assertEqual(pa.main(["--dir", str(root), "--platform", "win"]), 1)


if __name__ == "__main__":
    unittest.main()
