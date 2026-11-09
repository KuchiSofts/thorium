# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Edits to upstream overlay files, which the patch series cannot change (ROADMAP S.4)."""
import unittest

from tools.build import thoron_identity as ti

FLAGS = "chrome/browser/thorium_flag_entries.h"
# Excerpt of upstream's overlay file (stored with Windows line endings).
FLAG_ENTRIES = (
    '    {"disable-web-security",\n     "Disable Web Security",\n'
    '     "Don\'t enforce the same-origin policy; meant for website testing only. See `https://web.dev/same-origin-policy/`",\n'
    '    {"allow-file-access-from-files",\n'
    '     "By default, file:// URIs cannot read other file:// URIs. This is an override for web developers who need this behavior for testing.",\n'
    '     "Disable encryption of cookies, passwords, and settings which normally uses a generated machine-specific encryption key. "\n'
    '     "This is used to enable portable user data directories. Enabled for Thorium Portable.",\n'
    '     "Disables use of a generated machine-specific ID to lock the user data directory to that machine. This is used to enable portable user data directories. Enabled for Thorium Portable.",\n'
    '     "Allows downloading files from mixed origin/cross origin schemes.",\n'
    '     "Choose the password store backend, instead of using the automatically detected one. "\n'
).replace("\n", "\r\n")


class OverlayEditTests(unittest.TestCase):
    def test_risky_flags_start_with_a_warning(self):
        out = ti.edit_overlay(FLAGS, FLAG_ENTRIES)
        self.assertEqual(out.count('"Warning: '), 5)
        self.assertIn("every website can read data from every other website", out)
        self.assertIn("stored unencrypted", out)
        self.assertNotIn("Thorium Portable", out)
        self.assertIn("Don't enforce the same-origin policy", out)          # the original text stays

    def test_idempotent_and_keeps_windows_line_endings(self):
        once = ti.edit_overlay(FLAGS, FLAG_ENTRIES)
        self.assertEqual(ti.edit_overlay(FLAGS, once), once)
        self.assertNotIn("\n", once.replace("\r\n", ""))

    def test_changed_upstream_text_raises(self):
        with self.assertRaisesRegex(ti.IdentityError, "thorium_flag_entries.h"):
            ti.edit_overlay(FLAGS, FLAG_ENTRIES.replace("Allows downloading files", "Allows downloads"))

    def test_apply_covers_the_overlay_file(self):
        self.assertIn(FLAGS, ti.OVERLAY_EDITS)



VERSION_HTML = "components/webui/version/resources/about_version.html"
VERSION_PAGE = ('          <div id="thor_version"><a target="_self" rel="noopener" '
                'href="chrome://resources/text/thorium_version.txt">THORIUM_VERSION.txt</a></div>\n')


class VersionPageTests(unittest.TestCase):
    def test_build_variant_link_is_not_named_after_thorium(self):
        out = ti.edit_overlay(VERSION_HTML, VERSION_PAGE)
        self.assertIn(">BUILD_VARIANT.txt</a>", out)
        self.assertNotIn("THORIUM_VERSION", out)
        self.assertIn("chrome://resources/text/thorium_version.txt", out)    # the resource path stays
        self.assertEqual(ti.edit_overlay(VERSION_HTML, out), out)

if __name__ == "__main__":
    unittest.main()
