#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Render the Thoron SVG logo to PNG sizes and a multi-size Windows .ico.

Rasterising uses a headless Chromium-family browser (Edge on Windows 11, or Chromium/Thoron on
Linux) with a throwaway profile, so no extra Python packages are needed and no real browser profile
is touched.
    py -3 -I tools/branding/export_icons.py --svg branding/thoron/thoron-logo.svg --out branding/thoron
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # allow running as a script with `py -3 -I`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.branding.ico import ICO_SIZES, pack_ico, png_size  # noqa: E402

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/usr/bin/thoron",
)


def find_browser() -> Path:
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("no headless-capable Chromium-family browser found; pass --browser")


def render_svg(svg: Path, size: int, out_png: Path, browser: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="thoron-icon-") as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text(
            "<!doctype html><html><body style='margin:0;background:transparent;overflow:hidden'>"
            f"<img src='{svg.resolve().as_uri()}' width='{size}' height='{size}' style='display:block'>"
            "</body></html>", encoding="utf-8")
        subprocess.run([
            str(browser), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--force-device-scale-factor=1", "--default-background-color=00000000",
            f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={size},{size}",
            f"--screenshot={out_png.resolve()}", page.as_uri(),
        ], check=True, capture_output=True, timeout=120)
    actual = png_size(out_png.read_bytes())
    if actual != (size, size):
        raise RuntimeError(f"rendered {out_png.name} is {actual}, expected {(size, size)}")


def export_all(svg: Path, out_dir: Path, browser: Path, sizes: tuple[int, ...] | None = None) -> list[Path]:
    """Render the standard PNG set and the .ico, or only `sizes` (the .ico is then left as it is)."""
    png_dir = out_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for size in sizes or PNG_SIZES:
        target = png_dir / f"thoron_{size}.png"
        render_svg(svg, size, target, browser)
        written.append(target)
    if sizes:
        return written
    ico_path = out_dir / "thoron.ico"
    ico_path.write_bytes(pack_ico({s: (png_dir / f"thoron_{s}.png").read_bytes() for s in ICO_SIZES}))
    written.append(ico_path)
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", help="render only these PNG sizes (e.g. Windows tiles: 70 150)")
    args = parser.parse_args(argv)
    browser = args.browser or find_browser()
    for path in export_all(args.svg, args.out, browser, sizes=tuple(args.sizes) if args.sizes else None):
        print(f"wrote {path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
