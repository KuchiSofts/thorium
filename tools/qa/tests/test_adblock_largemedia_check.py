# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "Temporarily allow large media": the offline check (ROADMAP P5.62)."""
import unittest

from tools.qa import adblock_largemedia_check as mc


class StepTests(unittest.TestCase):
    def test_blocked(self):
        self.assertEqual(mc.blocked_problems({"bar": True, "next": True}, [True, False]), [])
        self.assertEqual(len(mc.blocked_problems({"bar": False}, [False])), 2)

    def test_script(self):
        self.assertEqual(mc.script_problems("undefined", [True, False], [True, False]), [])
        self.assertEqual(len(mc.script_problems("function", [True], [False, True])), 2)

    def test_click(self):
        self.assertEqual(mc.click_problems([True, False], [False, True, False], {"bar": False}), [])
        self.assertEqual(len(mc.click_problems([True, False], [True, False], {"bar": True})), 2)
        self.assertEqual(len(mc.click_problems([True, False], [True, False, True, False], {})), 1)

    def test_the_video_is_over_the_size(self):
        self.assertGreater(mc.VIDEO_BYTES, 50 * 1024)
        self.assertIn('src="/big.mp4"', mc.PAGE)


if __name__ == "__main__":
    unittest.main()
