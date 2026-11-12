#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron's version numbers (ROADMAP P2.14).

A Thoron version is Chromium's four numbers with the last one widened:
    PATCH = Chromium patch * 100 + rebuild      (rebuild 0-99)
so Thoron 158.0.8127.3000 is the first build of Chromium 158.0.8127.30, 158.0.8127.3001 its first
rebuild, and a newer Chromium (158.0.8127.4500) always sorts above every rebuild of an older one. Each
part stays within the Windows version resource limit (65535), so the installer and the updater compare
versions as usual. The older plain numbers (Thoron 156.0.8078.28) sort below the new ones.

That four-part number is the build number: websites, extensions, the installer and the updater compare
it. People see Thoron's own version instead (THORON_VERSION, three numbers, "0.1.1"): the About page,
chrome://version, chrome://flags, the Windows list of apps and the files' product version. Every release
published raises it.
    py -3 -I tools/release/version.py set --src <chromium src> --rebuild 0
    py -3 -I tools/release/version.py rebuild --src <chromium src> --to 1
    py -3 -I tools/release/version.py thoron --src <chromium src> --to 0.1.1
    py -3 -I tools/release/version.py check --new-thoron 0.1.2 --previous-thoron 0.1.1
    py -3 -I tools/release/version.py check --new 158.0.8127.3001 --previous 158.0.8127.3000
"""
import argparse
import re
import sys
from pathlib import Path

MAX_PART = 65535
REBUILDS = 100
_VERSION = re.compile(r"^(\d{1,5})\.(\d{1,5})\.(\d{1,5})\.(\d{1,5})$")
_THORON = re.compile(r"^(\d{1,4})\.(\d{1,4})\.(\d{1,4})$")


class VersionError(Exception):
    pass


def key(version: str) -> tuple[int, int, int, int]:
    m = _VERSION.match(version or "")
    if not m:
        raise VersionError(f"not a four-part version: {version!r}")
    parts = tuple(int(x) for x in m.groups())
    if any(p > MAX_PART for p in parts):
        raise VersionError(f"{version}: each part must be at most {MAX_PART}")
    return parts


def thoron_version(chromium: str, rebuild: int) -> str:
    major, minor, build, patch = key(chromium)
    if not 0 <= rebuild < REBUILDS:
        raise VersionError(f"rebuild must be 0-{REBUILDS - 1}, got {rebuild}")
    wide = patch * REBUILDS + rebuild
    if wide > MAX_PART:
        raise VersionError(f"Chromium patch {patch} is too high: {wide} exceeds {MAX_PART}")
    return f"{major}.{minor}.{build}.{wide}"


def split(thoron: str) -> tuple[str, int]:
    """(Chromium version, rebuild) of a Thoron version."""
    major, minor, build, wide = key(thoron)
    return f"{major}.{minor}.{build}.{wide // REBUILDS}", wide % REBUILDS


def thoron_key(version: str) -> tuple[int, int, int]:
    m = _THORON.match(version or "")
    if not m:
        raise VersionError(f"not a Thoron version of three numbers: {version!r}")
    return tuple(int(x) for x in m.groups())


def check_thoron(new: str, previous: str) -> list[str]:
    """Problems with publishing Thoron `new` after `previous` (empty when it is fine)."""
    try:
        if thoron_key(new) <= thoron_key(previous):
            return [f"Thoron {new} is not higher than the previous release {previous}"]
    except VersionError as exc:
        return [str(exc)]
    return []


def thoron_version_file(text: str, version: str) -> str:
    """Write Thoron's own version into a converted chrome/VERSION; it may only go up."""
    nl = "\r\n" if "\r\n" in text else "\n"
    values = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    if "THORON_REBUILD" not in values:
        raise VersionError("chrome/VERSION is not converted yet: use `set` first")
    thoron_key(version)
    if "THORON_VERSION" in values:
        problems = check_thoron(version, values["THORON_VERSION"])
        if problems:
            raise VersionError(problems[0])
        lines = [f"THORON_VERSION={version}" if l.startswith("THORON_VERSION=") else l for l in text.splitlines()]
    else:
        lines = text.splitlines() + [f"THORON_VERSION={version}"]
    return nl.join(lines) + nl


def check_new(new: str, previous: str) -> list[str]:
    """Problems with releasing `new` after `previous` (empty when it is fine)."""
    try:
        if key(new) <= key(previous):
            return [f"{new} is not higher than the previous release {previous}"]
    except VersionError as exc:
        return [str(exc)]
    return []


def set_version_file(text: str, rebuild: int) -> str:
    """Rewrite chrome/VERSION for a Thoron build; refuses a file that is already converted."""
    nl = "\r\n" if "\r\n" in text else "\n"
    values = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    if "THORON_REBUILD" in values:
        raise VersionError("chrome/VERSION already carries a Thoron version (THORON_REBUILD is set)")
    try:
        chromium = ".".join(values[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    except KeyError as exc:
        raise VersionError(f"chrome/VERSION has no {exc.args[0]}") from None
    wide = thoron_version(chromium, rebuild).rsplit(".", 1)[1]
    lines = [f"PATCH={wide}" if l.startswith("PATCH=") else l for l in text.splitlines()]
    lines.append(f"THORON_REBUILD={rebuild}")
    return nl.join(lines) + nl


def rebuild_version_file(text: str, rebuild: int) -> str:
    """Move a converted chrome/VERSION on to a later rebuild of the same Chromium; never back."""
    nl = "\r\n" if "\r\n" in text else "\n"
    values = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    if "THORON_REBUILD" not in values:
        raise VersionError("chrome/VERSION is not converted yet: use `set` first")
    try:
        wide = int(values["PATCH"])
        current = int(values["THORON_REBUILD"])
    except (KeyError, ValueError):
        raise VersionError("chrome/VERSION has no readable PATCH and THORON_REBUILD") from None
    if wide % REBUILDS != current:
        raise VersionError(f"PATCH={wide} and THORON_REBUILD={current} disagree; the file was changed by hand")
    if not 0 <= rebuild < REBUILDS:
        raise VersionError(f"rebuild must be 0-{REBUILDS - 1}, got {rebuild}")
    if rebuild <= current:
        raise VersionError(f"rebuild {rebuild} is not higher than the current one ({current})")
    new_wide = wide - current + rebuild
    lines = [f"PATCH={new_wide}" if l.startswith("PATCH=") else
             f"THORON_REBUILD={rebuild}" if l.startswith("THORON_REBUILD=") else l for l in text.splitlines()]
    return nl.join(lines) + nl


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="convert chrome/VERSION of a Chromium tree to the Thoron version")
    s.add_argument("--src", type=Path, required=True)
    s.add_argument("--rebuild", type=int, required=True)
    r = sub.add_parser("rebuild", help="move a converted chrome/VERSION on to a later rebuild")
    r.add_argument("--src", type=Path, required=True)
    r.add_argument("--to", type=int, required=True)
    t = sub.add_parser("thoron", help="set Thoron's own version (three numbers) in a converted chrome/VERSION")
    t.add_argument("--src", type=Path, required=True)
    t.add_argument("--to", required=True)
    c = sub.add_parser("check", help="a new release must be higher than the previous one")
    c.add_argument("--new")
    c.add_argument("--previous")
    c.add_argument("--new-thoron")
    c.add_argument("--previous-thoron")
    a = parser.parse_args(argv)
    try:
        if a.cmd in ("set", "rebuild", "thoron"):
            path = a.src / "chrome" / "VERSION"
            text = path.read_bytes().decode("utf-8")
            if a.cmd == "set":
                new = set_version_file(text, a.rebuild)
            elif a.cmd == "rebuild":
                new = rebuild_version_file(text, a.to)
            else:
                new = thoron_version_file(text, a.to)
            path.write_bytes(new.encode("utf-8"))
            values = dict(l.split("=", 1) for l in new.splitlines() if "=" in l)
            build = ".".join(values[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
            print(f"Thoron {values['THORON_VERSION']} (build {build})" if "THORON_VERSION" in values
                  else f"Thoron {build}")
            return 0
        problems = []
        if a.new or a.previous:
            if not (a.new and a.previous):
                raise VersionError("--new and --previous go together")
            problems += check_new(a.new, a.previous)
        if a.new_thoron or a.previous_thoron:
            if not (a.new_thoron and a.previous_thoron):
                raise VersionError("--new-thoron and --previous-thoron go together")
            problems += check_thoron(a.new_thoron, a.previous_thoron)
    except (VersionError, OSError) as exc:
        print(f"version: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"version: {p}", file=sys.stderr)
    print("version: OK" if not problems else "version: refused")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
