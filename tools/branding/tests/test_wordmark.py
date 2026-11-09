# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron wordmark (logo + name) for the places Chromium shows a product wordmark (ROADMAP B.3)."""
import unittest
import xml.etree.ElementTree as ET

from tools.branding import wordmark as wm

LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">\n'
        '  <!-- Thoron logo (c) 2026 KuchiSofts, CC BY 4.0 -->\n'
        '  <defs><linearGradient id="a-bg"><stop offset="0" stop-color="#7B2FF7"/></linearGradient></defs>\n'
        '  <circle cx="256" cy="256" r="200" fill="url(#a-bg)"/>\n</svg>\n')


class WordmarkTests(unittest.TestCase):
    def test_size_logo_and_name(self):
        svg = wm.wordmark_svg(LOGO, "#202124")
        root = ET.fromstring(svg)
        self.assertEqual((root.get("width"), root.get("height")), ("342", "64"))
        self.assertIn('fill="url(#a-bg)"', svg)          # the logo is inlined, not linked
        self.assertNotIn("href=", svg)
        text = root.find("{http://www.w3.org/2000/svg}text")
        self.assertEqual(text.text, "thoron")
        self.assertEqual(text.get("fill"), "#202124")

    def test_white_variant(self):
        self.assertIn('fill="#ffffff"', wm.wordmark_svg(LOGO, "#ffffff"))

    def test_keeps_the_logo_credit(self):
        self.assertIn("CC BY 4.0", wm.wordmark_svg(LOGO, "#202124"))

    def test_refuses_a_logo_without_a_512_viewbox(self):
        with self.assertRaises(ValueError):
            wm.wordmark_svg(LOGO.replace("0 0 512 512", "0 0 100 100"), "#202124")

    def test_refuses_bad_colours(self):
        with self.assertRaises(ValueError):
            wm.wordmark_svg(LOGO, "red;onload=x")


if __name__ == "__main__":
    unittest.main()
