#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Import a Thorium profile into Thoron by copying it (design §7.7, ROADMAP P3 import, Windows).

The whole `User Data` folder is copied, never moved, and every file is verified by SHA-256. The
source is only read: Thorium keeps working exactly as before and stays a natural backup. Saved
passwords and cookies keep working because the DPAPI-wrapped key travels inside the copied
`Local State` (same Windows user).

Refused, with nothing changed, when: the source is not a `User Data` folder; either browser is
running (`lockfile`); the folders overlap; or the destination already holds a profile (a fresh
install's empty `Crashpad` folder is fine).
    py -3 -I tools/migrate/import_profile.py --from "%LOCALAPPDATA%\\Thorium\\User Data" --to "%LOCALAPPDATA%\\Thoron\\User Data"
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path


class ImportRefused(RuntimeError):
    pass


class VerificationFailed(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_fresh(dest: Path) -> bool:
    """No profile yet: absent, or only what an installer creates (an empty Crashpad folder)."""
    if not dest.exists():
        return True
    return not any(p.is_file() and p.relative_to(dest).parts[0] != "Crashpad" for p in dest.rglob("*"))


def import_profile(source: Path, dest: Path) -> dict:
    source, dest = Path(source).resolve(), Path(dest).resolve()
    if not (source / "Local State").is_file():
        raise ImportRefused(f"{source} is not a browser 'User Data' folder (no 'Local State')")
    if (source / "lockfile").exists():
        raise ImportRefused("the source browser is running; close it completely first")
    if (dest / "lockfile").exists():
        raise ImportRefused("the destination browser is running; close it completely first")
    if dest == source or source in dest.parents or dest in source.parents:
        raise ImportRefused("the source and destination folders overlap")
    if not _is_fresh(dest):
        raise ImportRefused(f"{dest} already holds a profile; nothing was changed")
    files = [p for p in source.rglob("*") if p.is_file()]
    total = 0
    for d in [source] + [p for p in source.rglob("*") if p.is_dir()]:
        (dest / d.relative_to(source)).mkdir(parents=True, exist_ok=True)
    for p in files:
        try:
            shutil.copy2(p, dest / p.relative_to(source))
        except OSError as exc:
            raise ImportRefused(f"copying {p.relative_to(source)} failed ({exc}); the source is unchanged, and the "
                                f"partial copy in {dest} is only a copy and can be deleted before trying again") from exc
        total += p.stat().st_size
    mismatched = [p.relative_to(source).as_posix() for p in files
                  if _sha256(p) != _sha256(dest / p.relative_to(source))]
    if mismatched:
        raise VerificationFailed(f"{len(mismatched)} file(s) differ after copying (for example {mismatched[:3]}); "
                                 f"the source is unchanged and the copy is left in {dest} for inspection")
    return {"files": len(files), "bytes": total, "verified": True}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="source", required=True, type=Path, help="Thorium 'User Data' folder")
    parser.add_argument("--to", dest="dest", required=True, type=Path, help="Thoron 'User Data' folder")
    a = parser.parse_args(argv)
    try:
        report = import_profile(a.source, a.dest)
    except (ImportRefused, VerificationFailed) as exc:
        print(f"import: {exc}")
        return 1
    print(f"import: copied {report['files']} files ({report['bytes'] / 1024 ** 3:.2f} GB), every file verified")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
