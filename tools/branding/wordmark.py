#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron wordmark (logo + "thoron") for the places Chromium shows a product wordmark, such as the
header of chrome://version (ROADMAP B.3). Built from the logo SVG, so it never drifts from it, and
rendered with the same headless browser as export_icons.py.
    py -3 -I tools/branding/wordmark.py --svg branding/thoron/thoron-logo.svg --out branding/thoron/png
writes thoron_wordmark.png (dark text) and thoron_wordmark_white.png (white text), 342 x 64 like
Chromium's product_logo.png.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # allow running as a script with `py -3 -I`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.branding.export_icons import find_browser  # noqa: E402
from tools.branding.ico import png_size  # noqa: E402

WIDTH, HEIGHT = 342, 64
_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ROOT = re.compile(r"<svg\b[^>]*>(.*)</svg>\s*$", re.S)


def wordmark_svg(logo_svg: str, colour: str) -> str:
    if not _COLOUR.match(colour):
        raise ValueError(f"colour must be #rrggbb, got {colour!r}")
    if 'viewBox="0 0 512 512"' not in logo_svg:
        raise ValueError("the logo SVG must have viewBox 0 0 512 512")
    m = _ROOT.search(logo_svg)
    if not m:
        raise ValueError("not an SVG document")
    inner = m.group(1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}">\n'
            f'  <svg x="2" y="2" width="60" height="60" viewBox="0 0 512 512">{inner}</svg>\n'
            f'  <text x="76" y="47" font-family="Segoe UI, Roboto, Arial, sans-serif" font-size="44" '
            f'fill="{colour}">thoron</text>\n</svg>\n')


def render(svg_text: str, out_png: Path, browser: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="thoron-wordmark-") as tmp:
        svg = Path(tmp) / "w.svg"
        svg.write_text(svg_text, encoding="utf-8")
        page = Path(tmp) / "page.html"
        page.write_text("<!doctype html><html><body style='margin:0;background:transparent;overflow:hidden'>"
                        f"<img src='{svg.as_uri()}' width='{WIDTH}' height='{HEIGHT}' style='display:block'>"
                        "</body></html>", encoding="utf-8")
        subprocess.run([str(browser), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--force-device-scale-factor=1", "--default-background-color=00000000", f"--user-data-dir={Path(tmp) / 'profile'}",
                        f"--window-size={WIDTH},{HEIGHT}", f"--screenshot={out_png.resolve()}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    if png_size(out_png.read_bytes()) != (WIDTH, HEIGHT):
        raise RuntimeError(f"{out_png.name} is not {WIDTH}x{HEIGHT}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args(argv)
    browser = find_browser()
    logo = a.svg.read_text(encoding="utf-8")
    a.out.mkdir(parents=True, exist_ok=True)
    for name, colour in (("thoron_wordmark.png", "#202124"), ("thoron_wordmark_white.png", "#ffffff")):
        render(wordmark_svg(logo, colour), a.out / name, browser)
        print("wrote", a.out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
