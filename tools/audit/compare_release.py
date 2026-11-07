#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Compare every file of an official release ZIP with an installed or extracted copy.

Proves an installation is byte-identical to the published release (no tampering, no injected
files). Read-only; never executes anything from the ZIP.
    py -3 -I tools/audit/compare_release.py RELEASE.zip INSTALL_DIR
"""
import hashlib
import os
import sys
import zipfile


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1 << 20), b""):
        digest.update(block)
    return digest.hexdigest()


def _zip_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members = [m for m in archive.infolist() if not m.is_dir()]
    names = [m.filename.replace("\\", "/") for m in members]
    tops = {n.split("/", 1)[0] for n in names}
    strip = len(tops) == 1 and all("/" in n for n in names)
    return {(n.split("/", 1)[1] if strip else n): m for n, m in zip(names, members)}


def compare(zip_path: str, install_dir: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"identical": [], "different": [], "missing": [], "extra": []}
    installed = {}
    for root, _dirs, files in os.walk(install_dir):
        for name in files:
            full = os.path.join(root, name)
            installed[os.path.relpath(full, install_dir).replace("\\", "/")] = full
    with zipfile.ZipFile(zip_path) as archive:
        entries = _zip_entries(archive)
        for rel in sorted(entries):
            if rel not in installed:
                result["missing"].append(rel)
                continue
            with archive.open(entries[rel]) as zf, open(installed[rel], "rb") as lf:
                result["identical" if _sha256(zf) == _sha256(lf) else "different"].append(rel)
    result["extra"] = sorted(set(installed) - set(entries))
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: compare_release.py RELEASE.zip INSTALL_DIR", file=sys.stderr)
        return 2
    result = compare(argv[0], argv[1])
    print(" | ".join(f"{k}: {len(v)}" for k, v in result.items()))
    for key in ("different", "missing", "extra"):
        for rel in result[key]:
            print(f"  {key.upper()}: {rel}")
    print("RESULT: identical to release" if not result["different"] else "RESULT: MODIFIED FILES FOUND")
    return 0 if not result["different"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
