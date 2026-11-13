# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, its pages in the browser's language: the offline check (ROADMAP P5.51)."""
import unittest

from tools.qa import adblock_i18n_check as ic

ENGLISH = {"Save", "Block element", "JavaScript", "Sites", "Allow: example.com on this site", "Thoron"}


class TextTests(unittest.TestCase):
    def test_names_and_rules_are_not_words(self):
        for text in ("JavaScript", "uBlock Origin", "Ctrl+Alt+Z", "12 KB", "||ads.example^", "Thoron"):
            self.assertFalse(ic.has_words(text), text)
        self.assertTrue(ic.has_words("Save now"))

    def test_english_left(self):
        texts = ["Guardar", "Block element", "JavaScript", "Sites", "Permitir: example.com en este sitio"]
        self.assertEqual(ic.english_left(texts, ENGLISH), ["Block element"])

    def test_the_steps(self):
        good = {"lang": "es", "dir": "ltr", "texts": ["Guardar", "uBlock Origin"]}
        self.assertEqual(ic.lang_problems("es", "menu", good, ENGLISH), [])
        bad = {"lang": "en-US", "dir": "ltr", "texts": ["Save"]}
        self.assertEqual(len(ic.lang_problems("es", "menu", bad, ENGLISH)), 2)
        self.assertEqual(ic.english_problems("menu", {"lang": "en-US", "dir": "ltr", "texts": ["x"] * 30}), [])
        self.assertEqual(len(ic.english_problems("menu", {"lang": "es", "dir": "ltr", "texts": []})), 2)


if __name__ == "__main__":
    unittest.main()
