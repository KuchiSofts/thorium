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
"""
import argparse
import re
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", type=Path, help="an extracted package")
    src.add_argument("--list", type=Path, help="a text file with one packaged path per line")
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    a = parser.parse_args(argv)
    if a.dir:
        names = [str(p.relative_to(a.dir)) for p in a.dir.rglob("*")]
    else:
        names = a.list.read_text(encoding="utf-8").splitlines()
    problems = audit(names, a.platform)
    for p in problems:
        print(f"package_audit: {p}", file=sys.stderr)
    print(f"package audit: {'OK' if not problems else f'{len(problems)} problem(s)'} ({len(names)} entries)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
