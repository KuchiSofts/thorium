# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.branding import export_icons as ei


class ExtraSizesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.ico = self.tmp / "thoron.ico"
        self.ico.write_bytes(b"existing icon")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_custom_sizes_render_only_those_and_keep_the_ico(self):
        rendered = []

        def fake_render(svg, size, out_png, browser):
            rendered.append(size)
            out_png.write_bytes(b"png")

        with mock.patch.object(ei, "render_svg", side_effect=fake_render):
            written = ei.export_all(Path("logo.svg"), self.tmp, Path("browser.exe"), sizes=(70, 150))
        self.assertEqual(rendered, [70, 150])
        self.assertEqual([p.name for p in written], ["thoron_70.png", "thoron_150.png"])
        self.assertEqual(self.ico.read_bytes(), b"existing icon")

    def test_cli_parses_sizes(self):
        with mock.patch.object(ei, "export_all", return_value=[]) as export, \
                mock.patch.object(ei, "find_browser", return_value=Path("b.exe")):
            self.assertEqual(ei.main(["--svg", "a.svg", "--out", "o", "--sizes", "70", "150"]), 0)
        self.assertEqual(export.call_args.kwargs["sizes"], (70, 150))


if __name__ == "__main__":
    unittest.main()
