#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Repository binary policy (ROADMAP L.6).

The repository carries no prebuilt executables, libraries, packages or archives unless
`tools/audit/binary_allowlist.txt` records the file's SHA-256, licence and source. Proprietary
blobs that may not be redistributed (the Widevine CDM, Flash Player) are never allowed, listed or
not. Binaries are recognised by their content, so a renamed executable is still caught. Only
tracked files are checked; build output is ignored.

Allowlist format, one file per line, tab-separated:  <sha256>  <path>  <licence>  <source>
    py -3 -I tools/audit/binary_policy.py [--root .] [--allowlist tools/audit/binary_allowlist.txt]
Exit status 1 on any problem.
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

HEAD_BYTES = 512
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAGIC = (
    (b"\x7fELF", "ELF binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O binary"),
    (b"\xca\xfe\xba\xbe", "Mach-O universal binary or Java class"),
    (b"\x00asm", "WebAssembly module"),
    (b"Cr24", "CRX package"),
    (b"!<arch>\n", "ar archive"),
    (b"PK\x03\x04", "zip archive"),
    (b"7z\xbc\xaf\x27\x1c", "7z archive"),
    (b"Rar!\x1a\x07", "rar archive"),
    (b"\x1f\x8b\x08", "gzip archive"),
    (b"\xfd7zXZ\x00", "xz archive"),
    (b"\x28\xb5\x2f\xfd", "zstd archive"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "OLE file (MSI or similar)"),
)
BZIP2_RE = re.compile(rb"^BZh[1-9]1AY&SY")
FORBIDDEN = (
    (re.compile(r"(?i)(^|/)(lib)?widevinecdm[^/]*\.(dll|so|dylib|lib|sig)$"),
     "Widevine CDM, Google proprietary software that may not be redistributed"),
    (re.compile(r"(?i)(^|/)[^/]*flashplayer[^/]*\.(dll|so|dylib|exe)$"),
     "Adobe Flash Player, proprietary and end-of-life since 2020"),
)


def classify(head: bytes) -> str | None:
    """The kind of binary the first bytes of a file reveal, or None for text, images and the like."""
    if head.startswith(b"MZ"):  # a DOS/PE header is full of zero bytes; text that starts with "MZ" is not
        return "PE executable" if b"\x00" in head[:HEAD_BYTES] else None
    if BZIP2_RE.match(head):
        return "bzip2 archive"
    return next((kind for magic, kind in MAGIC if head.startswith(magic)), None)


def forbidden_reason(path: str) -> str | None:
    return next((reason for rx, reason in FORBIDDEN if rx.search(path)), None)


def load_allowlist(text: str) -> dict[str, dict]:
    allow = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = [f.strip() for f in line.split("\t")]
        if len(fields) != 4 or not all(fields):
            raise ValueError(f"allowlist line {number}: expected 4 tab-separated fields (sha256, path, licence, source)")
        sha, path, licence, source = fields
        if not SHA256_RE.match(sha):
            raise ValueError(f"allowlist line {number}: '{sha}' is not a lower-case SHA-256")
        allow[path] = {"sha256": sha, "license": licence, "source": source}
    return allow


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True).stdout
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(root: Path, allowlist: dict[str, dict]) -> list[str]:
    root = Path(root)
    problems, seen = [], set()
    for rel in tracked_files(root):
        full = root / rel
        if not full.is_file():
            continue
        reason = forbidden_reason(rel)
        if reason:
            seen.add(rel)
            problems.append(f"{rel}: {reason}; never allowed in the repository")
            continue
        with open(full, "rb") as f:
            kind = classify(f.read(HEAD_BYTES))
        if kind is None:
            continue
        entry = allowlist.get(rel)
        if entry is None:
            problems.append(f"{rel}: prebuilt {kind} with no binary allowlist entry (licence and source)")
            continue
        seen.add(rel)
        digest = _sha256(full)
        if digest != entry["sha256"]:
            problems.append(f"{rel}: changed since it was allowlisted (sha256 now {digest[:16]}...)")
    for rel in sorted(set(allowlist) - seen):
        problems.append(f"{rel}: allowlisted but not a tracked binary; remove the allowlist entry")
    return problems


def main(argv: list[str]) -> int:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--allowlist", type=Path)
    a = parser.parse_args(argv)
    allowlist_path = a.allowlist or a.root / "tools" / "audit" / "binary_allowlist.txt"
    text = allowlist_path.read_text(encoding="utf-8") if allowlist_path.is_file() else ""
    allowlist = load_allowlist(text)
    problems = check(a.root, allowlist)
    for p in problems:
        print(p)
    print(f"binary policy: {len(problems)} problem(s)" if problems
          else f"binary policy: OK ({len(allowlist)} allowlisted binaries)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
