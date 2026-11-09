#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Check what a Thoron package contains (ROADMAP P2.6, P2.20, P2.21).

A package (the files of the Windows installer's chrome.7z, or of a Linux .deb/.rpm or portable
folder) must contain the Thoron program and must not contain:
  - Google's Widevine module (it may not be redistributed; Chromium downloads it on demand);
  - any file or folder named after Thorium (licence and credit texts excepted);
  - upstream-only extras: the thor_ver marker of Thorium's updater, the prebuilt pak tool and the
    developer test shell.
    py -3 -I tools/release/package_audit.py --dir <extracted package> --platform win
    py -3 -I tools/release/package_audit.py --list <file with one path per line> --platform linux
    py -3 -I tools/release/package_audit.py --archive out/<dir>/chrome.7z --sevenzip <7za.exe> --platform win
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PLATFORMS = ("win", "linux")
_WIDEVINE = re.compile(r"(?i)widevine")
_THORIUM = re.compile(r"(?i)thorium")
_TEXT_OK = re.compile(r"(?i)(credits|licen[cs]e|notice|copying)[^/]*$")
_UPSTREAM_ONLY = re.compile(r"(?i)(^|/)(thor_ver|pak|pak\.exe|content_shell\.pak|shell_resources\.pak)$")
_PROGRAM = {"win": re.compile(r"(?i)(^|/)thoron\.exe$"), "linux": re.compile(r"(^|/)opt/kuchisofts/thoron/thoron$")}


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def audit(names: list[str], platform: str) -> list[str]:
    """Problems with a package's file list (empty when it is fine)."""
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}")
    problems = []
    paths = [_norm(n) for n in names if n.strip()]
    for p in paths:
        if _WIDEVINE.search(p):
            problems.append(f"Widevine must not be bundled: {p}")
        elif _UPSTREAM_ONLY.search(p):
            problems.append(f"upstream-only file: {p}")
        elif _THORIUM.search(p) and not _TEXT_OK.search(p):
            problems.append(f"named after Thorium: {p}")
    if not any(_PROGRAM[platform].search(p) for p in paths):
        want = "thoron.exe" if platform == "win" else "opt/kuchisofts/thoron/thoron"
        problems.append(f"the program {want} is missing")
    return problems


def parse_7z_listing(text: str) -> list[str]:
    """Paths from `7z l -slt` output (the archive's own header block comes before the ---------- line)."""
    _, sep, body = text.replace("\r\n", "\n").partition("\n----------\n")
    if not sep:
        raise ValueError("not a 7z technical listing")
    return [l[len("Path = "):].strip().replace("\\", "/") for l in body.splitlines() if l.startswith("Path = ")]


def list_archive(archive: Path, sevenzip: str) -> list[str]:
    out = subprocess.run([sevenzip, "l", "-slt", str(archive)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise ValueError(f"7-Zip could not list {archive}: {out.stderr.strip()[:200]}")
    return parse_7z_listing(out.stdout)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", type=Path, help="an extracted package")
    src.add_argument("--list", type=Path, help="a text file with one packaged path per line")
    src.add_argument("--archive", type=Path, help="a .7z archive (the Windows installer's chrome.7z)")
    parser.add_argument("--sevenzip", default="7z", help="7-Zip program for --archive")
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    a = parser.parse_args(argv)
    if a.dir:
        names = [str(p.relative_to(a.dir)) for p in a.dir.rglob("*")]
    elif a.archive:
        try:
            names = list_archive(a.archive, a.sevenzip)
        except (ValueError, OSError) as exc:
            print(f"package_audit: {exc}", file=sys.stderr)
            return 2
    else:
        names = a.list.read_text(encoding="utf-8").splitlines()
    problems = audit(names, a.platform)
    for p in problems:
        print(f"package_audit: {p}", file=sys.stderr)
    print(f"package audit: {'OK' if not problems else f'{len(problems)} problem(s)'} ({len(names)} entries)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
