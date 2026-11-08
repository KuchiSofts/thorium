#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Apply Thoron's Windows identity to a Chromium tree that already has the upstream Thorium overlay
and patch series (ROADMAP P2.3).

It changes what makes the browser a separate product, so it installs and runs side by side with
Thorium and keeps its own profile:
  - the product name in the UI strings and their translations (only the name: URLs, paths,
    identifiers and lowercase `thorium` stay untouched);
  - `chromium_install_modes.h`: install and profile folder name (`%LOCALAPPDATA%\\Thoron`), app GUID,
    app ID, ProgIDs, URL scheme, Active Setup GUID, COM class IDs (notifications, elevation,
    tracing), the sandbox AppContainer SID prefix, and the list of old IDs the installer cleans up;
  - `BRANDING` (name, company, copyright with the original credits kept);
  - the icons, from `branding/thoron/`.
The COM *interface* IDs stay as upstream's: they are compiled into the checked-in MIDL output and
are only registered by system-level installs (ROADMAP P2.19).

Every edit is anchored: a missing anchor stops the tool before any file is written. Running it again
is a no-op.
    py -3 -I tools/build/thoron_identity.py --src J:\\thoron-build\\chromium\\src [--dry-run]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

INSTALL_MODES_PATH = "chrome/install_static/chromium_install_modes.h"
BRANDING_PATH = "chrome/app/theme/chromium/BRANDING"

# Generated once for Thoron (2026-11-08) and fixed here so every build is identical.
THORON_IDS = {
    "app_guid": "{9EAA393A-6525-4F1A-86B5-B14908403A85}",
    "active_setup_guid": "{C11EF3BA-7841-46B8-8709-A6A46AD4A917}",
    "toast_activator_clsid": "5F7AE246-B5EB-4BE2-8E25-762A896E0A5D",
    "elevator_clsid": "262D272B-85DD-42A9-9DB0-479774CF1ADC",
    "tracing_service_clsid": "AE5771C0-8CDA-4982-BABC-4080F3C0D2E5",
    "old_tracing_iid": "054AF894-044A-42BE-BE37-C8414D146382",
    "sandbox_sid_prefix": "S-1-15-2-410603446-659394758-2458910261-1759236400-866594459-1279508806-",
}

BRANDING_VALUES = {
    "COMPANY_FULLNAME": "KuchiSofts",
    "COMPANY_SHORTNAME": "KuchiSofts",
    "PRODUCT_FULLNAME": "Thoron",
    "PRODUCT_SHORTNAME": "Thoron",
    "PRODUCT_INSTALLER_FULLNAME": "Thoron Installer",
    "PRODUCT_INSTALLER_SHORTNAME": "Thoron Installer",
    "COPYRIGHT": "Copyright @LASTCHANGE_YEAR@ The Chromium Authors, Alex313031 and KuchiSofts.",
    "MAC_BUNDLE_ID": "org.kuchisofts.Thoron",
}

_THEME = "chrome/app/theme"
_PNG = "branding/thoron/png/thoron_{}.png"
ICON_MAP = [
    ("branding/thoron/thoron.ico", f"{_THEME}/chromium/win/chromium.ico"),
    ("branding/thoron/thoron.ico", f"{_THEME}/chromium/win/chromium_doc.ico"),
    ("branding/thoron/thoron.ico", f"{_THEME}/chromium/win/chromium_pdf.ico"),
    (_PNG.format(150), f"{_THEME}/chromium/win/tiles/Logo.png"),
    (_PNG.format(70), f"{_THEME}/chromium/win/tiles/SmallLogo.png"),
    ("branding/thoron/thoron-logo.svg", f"{_THEME}/chromium/product_logo.svg"),
    ("branding/thoron/thoron-logo.svg", f"{_THEME}/chromium/product_logo_animation.svg"),
] + [(_PNG.format(s), f"{_THEME}/chromium/product_logo_{s}.png") for s in (16, 24, 48, 64, 128, 256)] \
  + [(_PNG.format(s), f"{_THEME}/chromium/linux/product_logo_{s}.png") for s in (24, 48, 64, 128, 256)] \
  + [(_PNG.format(s), f"{_THEME}/default_100_percent/chromium/product_logo_{s}.png") for s in (16, 32)] \
  + [(_PNG.format(s), f"{_THEME}/default_100_percent/chromium/linux/product_logo_{s}.png") for s in (16, 32)] \
  + [(_PNG.format(2 * s), f"{_THEME}/default_200_percent/chromium/product_logo_{s}.png") for s in (16, 32)]

# The product name only: not inside URLs, paths or identifiers, not part of a longer word.
NAME_RE = re.compile(r"(?<![\w/\\.\-@%])Thorium(?![\w\-/\\])(?!\.\w)")
_STRUCT = r"\{0x[0-9A-Fa-f]+,\s*0x[0-9A-Fa-f]+,\s*0x[0-9A-Fa-f]+,\s*\{(?:0x[0-9A-Fa-f]+,\s*){7}0x[0-9A-Fa-f]+\}\}"
_GUID = r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}"


class IdentityError(RuntimeError):
    pass


def guid_struct(guid: str) -> str:
    """`5F7AE246-B5EB-...` as a C GUID initialiser: {0x5F7AE246, 0xB5EB, 0x4BE2, {0x8E, ...}}."""
    h = guid.strip("{}").replace("-", "")
    tail = ", ".join(f"0x{h[i:i + 2]}" for i in range(16, 32, 2))
    return f"{{0x{h[0:8]}, 0x{h[8:12]}, 0x{h[12:16]}, {{{tail}}}}}"


def rename_product(text: str) -> tuple[str, int]:
    return NAME_RE.subn("Thoron", text)


def _install_mode_edits() -> list[tuple[str, str, str]]:
    ids = THORON_IDS
    old_iid = (f"\n    // Thoron: a placeholder no product ever registered, so the installer cleans up nothing of"
               f"\n    // Thorium's. {{{ids['old_tracing_iid']}}}\n    {guid_struct(ids['old_tracing_iid'])},")
    return [
        ("product path name", r'(kProductPathName\[\] = L")(?:Thorium|Thoron)(")', r"\g<1>Thoron\g<2>"),
        ("safe browsing name", r'(kSafeBrowsingName\[\] = ")(?:thorium|thoron)(")', r"\g<1>thoron\g<2>"),
        ("app_guid", r'(\.app_guid = L")' + _GUID + r'(")', rf"\g<1>{ids['app_guid']}\g<2>"),
        ("base_app_name", r'(\.base_app_name = L")(?:Thorium|Thoron)(")', r"\g<1>Thoron\g<2>"),
        ("base_app_id", r'(\.base_app_id = L")(?:Thorium|Thoron)(")', r"\g<1>Thoron\g<2>"),
        ("browser ProgID prefix", r'(\.browser_prog_id_prefix = L")(?:Thorium|Thoron)(HTM")', r"\g<1>Thoron\g<2>"),
        ("browser ProgID description", r'(L")(?:Thorium|Thoron)( HTML Document")', r"\g<1>Thoron\g<2>"),
        ("URL scheme", r'(\.direct_launch_url_scheme = ")(?:chromium|thoron)(")', r"\g<1>thoron\g<2>"),
        ("PDF ProgID prefix", r'(\.pdf_prog_id_prefix = L")(?:Thorium|Thoron)(PDF")', r"\g<1>Thoron\g<2>"),
        ("PDF ProgID description", r'(L")(?:Thorium|Thoron)( PDF Document")', r"\g<1>Thoron\g<2>"),
        ("active_setup_guid", r'(\.active_setup_guid =\s*L")' + _GUID + r'(")', rf"\g<1>{ids['active_setup_guid']}\g<2>"),
        ("toast_activator_clsid", r"(\.toast_activator_clsid = )" + _STRUCT,
         r"\g<1>" + guid_struct(ids["toast_activator_clsid"])),
        ("elevator_clsid", r"(\.elevator_clsid = )" + _STRUCT, r"\g<1>" + guid_struct(ids["elevator_clsid"])),
        ("tracing_service_clsid", r"(\.tracing_service_clsid = )" + _STRUCT,
         r"\g<1>" + guid_struct(ids["tracing_service_clsid"])),
        ("old tracing IIDs", r"(kOldTracingServiceIids = std::to_array<IID>\(\{)(?:\s*//[^\n]*)*\s*" + _STRUCT + r"\s*,?",
         lambda m: m.group(1) + old_iid),
        ("sandbox_sid_prefix", r'(\.sandbox_sid_prefix =\s*)(?:L"[^"]*"\s*)+(?=,)',
         rf'\g<1>L"{ids["sandbox_sid_prefix"]}"'),
    ]


def edit_install_modes(text: str) -> str:
    missing = []
    for name, pattern, repl in _install_mode_edits():
        text, n = re.subn(pattern, repl, text)
        if n != 1:
            missing.append(f"{name} ({n} matches)")
    if missing:
        raise IdentityError(f"{INSTALL_MODES_PATH}: anchors not found exactly once: {', '.join(missing)}")
    return text


def edit_branding(text: str) -> str:
    lines = text.split("\n")
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0]
        if "=" in line and key in BRANDING_VALUES:
            lines[i] = f"{key}={BRANDING_VALUES[key]}"
            seen.add(key)
    missing = sorted(set(BRANDING_VALUES) - seen)
    if missing:
        raise IdentityError(f"{BRANDING_PATH}: keys not found: {', '.join(missing)}")
    return "\n".join(lines)


def find_string_files(src: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(src), "grep", "-l", "-I", "-e", "Thorium", "--", "*.grd", "*.grdp", "*.xtb"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode not in (0, 1):
        raise IdentityError(f"git grep failed in {src}: {out.stderr.strip()}")
    return [l for l in out.stdout.splitlines() if l]


def apply(src: Path, repo: Path, string_files: list[str] | None = None, dry_run: bool = False) -> dict:
    """Plan every change in memory, stop on any problem, then write. Returns a summary."""
    src, repo = Path(src), Path(repo)
    planned: dict[Path, bytes] = {}
    problems: list[str] = []
    replacements = string_changes = 0
    for rel in (string_files if string_files is not None else find_string_files(src)):
        path = src / rel
        text = path.read_bytes().decode("utf-8")
        new, n = rename_product(text)
        if n:
            planned[path] = new.encode("utf-8")
            replacements += n
            string_changes += 1
    for rel, editor in ((INSTALL_MODES_PATH, edit_install_modes), (BRANDING_PATH, edit_branding)):
        path = src / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
            continue
        text = path.read_bytes().decode("utf-8")
        try:
            new = editor(text)
        except IdentityError as exc:
            problems.append(str(exc))
            continue
        if new != text:
            planned[path] = new.encode("utf-8")
    icons = 0
    for source, dest in ICON_MAP:
        s, d = repo / source, src / dest
        if not s.is_file():
            problems.append(f"missing icon source {source}")
        elif not d.is_file():
            problems.append(f"missing icon target {dest} (unexpected tree)")
        elif d.read_bytes() != s.read_bytes():
            planned[d] = s.read_bytes()
            icons += 1
    if problems:
        raise IdentityError("nothing was changed:\n  " + "\n  ".join(problems))
    if not dry_run:
        for path, data in planned.items():
            path.write_bytes(data)
    return {"strings": {"files": string_changes, "replacements": replacements}, "icons": icons,
            "files_changed": len(planned), "dry_run": dry_run}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", required=True, type=Path, help="Chromium src with the Thorium overlay applied")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--dry-run", action="store_true")
    a = parser.parse_args(argv)
    try:
        summary = apply(a.src, a.repo, dry_run=a.dry_run)
    except IdentityError as exc:
        print(exc)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
