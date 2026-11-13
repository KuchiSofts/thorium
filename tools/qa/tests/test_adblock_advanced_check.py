# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the last of uBlock Origin's settings: the offline check (ROADMAP P5.46)."""
import unittest

from tools.qa import adblock_advanced_check as ac


class StepTests(unittest.TestCase):
    def test_each_step_as_wanted(self):
        self.assertEqual(ac.autoupdate_problems(0, False, 3), [])
        self.assertEqual(ac.grid_problems([True, False, True]), [])
        self.assertEqual(ac.media_problems("error", "loaded"), [])
        self.assertEqual(ac.saved_problems({"auto-update": False, "media-kb": 200}), [])

    def test_what_differs_is_named(self):
        self.assertEqual(len(ac.autoupdate_problems(2, True, 0)), 3)
        self.assertEqual(len(ac.grid_problems([True, True, True])), 1)
        self.assertEqual(len(ac.media_problems("loaded", "error")), 2)
        self.assertEqual(len(ac.saved_problems({"auto-update": True})), 2)

    def test_the_sound_is_between_the_two_sizes(self):
        self.assertTrue(50 < ac.SOUND_KB < 200, ac.SOUND_KB)
        self.assertIn('src="/sound.wav"', ac.page_html())


if __name__ == "__main__":
    unittest.main()
