#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Vendor Thoron's Rust crates into a Chromium tree with Chromium's own gnrt tool (ROADMAP P5.14).

`other/ks-native-adblock-crates.patch` adds adblock-rust to Chromium's crate list (Cargo.toml, the pinned
and checksummed Cargo.lock, gnrt_config.toml and two crate patches). The crate sources and their
BUILD.gn files are too large for a patch, so this tool produces them:
  1. `gnrt vendor` downloads exactly the locked versions (Cargo checks every checksum);
  2. Thoron's crate patches are applied with forward slashes (gnrt passes Windows paths with
     backslashes, which git rejects as invalid);
  3. `gnrt gen` writes the BUILD.gn files;
  4. files gnrt rewrites by mistake (Chromium's hand-written README notes) are put back.
    py -3 -I tools/build/rust_crates.py --src J:\\thoron-build\\chromium158\\src
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

CRATES_IO = "third_party/rust/chromium_crates_io"
PATCHED_CRATES = ("seahash-v4", "flatbuffers-v25")          # Thoron's patches in <CRATES_IO>/patches
RESTORE_AFTER_GEN = ("third_party/rust/zune_jpeg/v0_5/README.chromium",)


def git_apply_args(crate_dir: str) -> list[str]:
    rel = crate_dir.replace("\\", "/").strip("/")
    return ["apply", f"-p{len(rel.split('/')) + 1}", f"--directory={rel}"]


def vendor_args() -> list[str]:
    return ["vendor"] + [f"--no-patches={c}" for c in PATCHED_CRATES]


def _env(src: Path) -> dict:
    env = dict(os.environ)
    # gn must be found too: without it gnrt cannot format the BUILD.gn files it writes
    buildtools = src / "buildtools" / ("win" if os.name == "nt" else "linux64")
    env["PATH"] = os.pathsep.join([str(src / "third_party" / "rust-toolchain" / "bin"), str(buildtools),
                                   env.get("PATH", "")])
    env.setdefault("DEPOT_TOOLS_WIN_TOOLCHAIN", "0")
    return env


def run(src: Path) -> None:
    env = _env(src)
    import shutil
    gn = shutil.which("gn", path=env["PATH"])
    if not gn:
        raise OSError("gn not found in buildtools or PATH; gnrt needs it to format BUILD.gn files")
    gnrt = src / "out" / "gnrt" / "target" / "release" / ("gnrt.exe" if os.name == "nt" else "gnrt")
    if not gnrt.is_file():
        subprocess.run([sys.executable, "tools/crates/run_gnrt.py", "--", "help"], cwd=src, env=env, check=True,
                       capture_output=True)
    subprocess.run([str(gnrt), *vendor_args()], cwd=src, env=env, check=True)
    for crate in PATCHED_CRATES:
        for patch in sorted((src / CRATES_IO / "patches" / crate).glob("*.patch")):
            crate_dir = f"{CRATES_IO}/vendor/{crate}"
            check = subprocess.run(["git", *git_apply_args(crate_dir), "--check", "--reverse"],
                                   cwd=src, input=patch.read_bytes(), capture_output=True)
            if check.returncode == 0:
                continue                                     # already applied
            subprocess.run(["git", *git_apply_args(crate_dir)], cwd=src, input=patch.read_bytes(), check=True)
    subprocess.run([str(gnrt), "vendor"], cwd=src, env=env, check=True)   # README files, now that licences exist
    subprocess.run([str(gnrt), "gen"], cwd=src, env=env, check=True)
    format_build_files(src, gn)
    subprocess.run(["git", "checkout", "--", *RESTORE_AFTER_GEN], cwd=src, check=True)


def changed_rust_build_files(porcelain: str) -> list[str]:
    """BUILD.gn files under third_party/rust that `git status --porcelain -uall` lists as changed or new."""
    out = []
    for line in porcelain.splitlines():
        path = line[3:].strip().replace("\\", "/")
        if path.startswith("third_party/rust/") and path.endswith("/BUILD.gn"):
            out.append(path)
    return sorted(set(out))


def format_build_files(src: Path, gn: str) -> None:
    """gnrt passes gn format paths with mixed separators on Windows, which gn rejects; format here."""
    porcelain = subprocess.run(["git", "status", "--porcelain", "-uall", "--", "third_party/rust"], cwd=src,
                               capture_output=True, text=True, encoding="utf-8", check=True).stdout
    files = changed_rust_build_files(porcelain)
    for i in range(0, len(files), 50):
        # the full path: on Windows a bare name is looked up in this process's PATH, not the child's
        subprocess.run([gn, "format", *files[i:i + 50]], cwd=src, check=True, capture_output=True)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        run(a.src)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"rust_crates: {exc}", file=sys.stderr)
        return 1
    print("rust crates: vendored and generated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
