#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Release script (ROADMAP P2.12): checks, packages and publishes one Thoron build as a draft.

    prepare  checks the build before anything is packaged and stops on any problem:
             the release args (tools/build/release_args.py check), the version (set by
             tools/release/version.py and higher than the previous release) and the installer
             contents (tools/release/package_audit.py); then copies the installer and BUILDINFO into
             the release folder with Thoron names, writes SHA256SUMS and the release notes, and signs
             SHA256SUMS with minisign when a key is given.
    publish  creates the GitHub release, always as a draft, and only with a signed SHA256SUMS. A
             person reviews and publishes it (design: releases stay drafts).

    py -3 -I tools/release/release.py prepare --src <chromium src> --out <out dir> --platform win
        --variant win-x64-avx2 --previous <last release> --buildinfo BUILDINFO.json --dist <folder>
        --repo . --since <last release tag> --chromium-old <version> [--sevenzip 7za.exe]
        [--minisign-key <key file>]
    py -3 -I tools/release/release.py publish --dist <folder> --version <version> --gh-repo KuchiSofts/thoron
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.build import release_args  # noqa: E402
from tools.release import changelog, package_audit, version as ver  # noqa: E402

_VARIANT = re.compile(r"^(win|linux)-(x64|arm64)-[a-z0-9]+$")
INSTALLERS = {"win": "mini_installer.exe"}


class ReleaseError(Exception):
    pass


def read_version(src: Path) -> tuple[str, bool]:
    values = dict(l.split("=", 1) for l in (src / "chrome" / "VERSION").read_text(encoding="utf-8").splitlines()
                  if "=" in l)
    v = ".".join(values[k].strip() for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    return v, "THORON_REBUILD" in values


def preflight(src: Path, out: Path, platform: str, previous: str, lister) -> tuple[str, list[str]]:
    problems = [f"release args: {p}" for p in release_args.check((out / "args.gn").read_text(encoding="utf-8"),
                                                                   platform)]
    version, converted = read_version(src)
    if not converted:
        problems.append("chrome/VERSION is not a Thoron version: run tools/release/version.py set first")
    problems += [f"version: {p}" for p in ver.check_new(version, previous)]
    if platform == "win":
        archive = out / "chrome.7z"
        if not archive.is_file():
            problems.append(f"missing {archive.name}")
        else:
            problems += [f"package: {p}" for p in package_audit.audit(lister(archive), platform)]
    return version, problems


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def assemble(out: Path, dist: Path, version: str, variant: str, buildinfo: Path) -> list[Path]:
    if not _VARIANT.match(variant):
        raise ReleaseError(f"variant must look like win-x64-avx2, got {variant!r}")
    if dist.exists() and any(dist.iterdir()):
        raise ReleaseError(f"{dist} is not empty; a release folder is never overwritten")
    dist.mkdir(parents=True, exist_ok=True)
    platform = variant.split("-")[0]
    files = []
    installer = INSTALLERS.get(platform)
    if installer:
        target = dist / f"thoron-{version}-{variant}-installer.exe"
        shutil.copy2(out / installer, target)
        files.append(target)
    info = dist / f"BUILDINFO-{version}-{variant}.json"
    shutil.copy2(buildinfo, info)
    files.append(info)
    sums = dist / "SHA256SUMS"
    sums.write_text("".join(f"{_sha256(p)}  {p.name}\n" for p in sorted(files)), encoding="utf-8", newline="\n")
    return files + [sums]


def sign(dist: Path, key: Path, run=subprocess.run) -> Path:
    sig = dist / "SHA256SUMS.minisig"
    run(["minisign", "-S", "-s", str(key), "-m", str(dist / "SHA256SUMS"), "-x", str(sig)], check=True)
    return sig


def publish(dist: Path, version: str, gh_repo: str, run=None) -> None:
    for need, why in (("SHA256SUMS", "checksums"), ("SHA256SUMS.minisig", "signature"), ("NOTES.md", "notes")):
        if not (dist / need).is_file():
            raise ReleaseError(f"no {why} ({need}) in {dist}; nothing is published without it")
    files = [str(p) for p in sorted(dist.iterdir()) if p.name != "NOTES.md"]
    cmd = ["gh", "release", "create", f"v{version}", "--draft", "--repo", gh_repo,
           "--title", f"Thoron {version}", "--notes-file", str(dist / "NOTES.md"), *files]
    if run is None:
        subprocess.run(cmd, check=True)
    else:
        run(cmd)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("prepare")
    for name in ("--src", "--out", "--buildinfo", "--dist", "--repo"):
        a_.add_argument(name, type=Path, required=True)
    for name in ("--platform", "--variant", "--previous", "--since", "--chromium-old"):
        a_.add_argument(name, required=True)
    a_.add_argument("--sevenzip", default="7z")
    a_.add_argument("--minisign-key", type=Path)
    b_ = sub.add_parser("publish")
    b_.add_argument("--dist", type=Path, required=True)
    b_.add_argument("--version", required=True)
    b_.add_argument("--gh-repo", required=True)
    a = p.parse_args(argv)
    try:
        if a.cmd == "publish":
            publish(a.dist, a.version, a.gh_repo)
            print(f"draft release v{a.version} created; review it on GitHub and publish it by hand")
            return 0
        version, problems = preflight(a.src, a.out, a.platform, a.previous,
                                      lambda archive: package_audit.list_archive(archive, a.sevenzip))
        if problems:
            for prob in problems:
                print(f"release: {prob}", file=sys.stderr)
            print(f"release: {len(problems)} problem(s); nothing was packaged")
            return 1
        files = assemble(a.out, a.dist, version, a.variant, a.buildinfo)
        chromium_new, _ = ver.split(version)
        notes = changelog.render(version, a.chromium_old, chromium_new, a.repo, a.since,
                                 artifacts=(a.dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
        (a.dist / "NOTES.md").write_text(notes, encoding="utf-8", newline="\n")
        if a.minisign_key:
            files.append(sign(a.dist, a.minisign_key))
        else:
            print("release: SHA256SUMS is not signed (no --minisign-key); publish will refuse it")
    except (ReleaseError, ver.VersionError, changelog.NotesError, OSError, ValueError,
            subprocess.CalledProcessError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 2
    print(f"release {version}: {len(files)} file(s) in {a.dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
