#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Apply Thoron's identity (Windows and Linux) to a Chromium tree that already has the upstream Thorium overlay
and patch series (ROADMAP P2.3).

It changes what makes the browser a separate product, so it installs and runs side by side with
Thorium and keeps its own profile:
  - the product name in the UI strings and their translations (only the name: URLs, paths,
    identifiers and lowercase `thorium` stay untouched);
  - `chromium_install_modes.h`: install and profile folder name (`%LOCALAPPDATA%\\Thoron`), app GUID,
    app ID, ProgIDs, URL scheme, Active Setup GUID, COM class IDs (notifications, elevation,
    tracing), the sandbox AppContainer SID prefix, and the list of old IDs the installer cleans up;
  - `BRANDING` (name, company, copyright with the original credits kept);
  - the icons, from `branding/thoron/`;
  - the Windows program file `thoron.exe` (P2.20) and, on Linux, the `thoron` program, the
    `thoron-browser` package, desktop file and the profile folder `~/.config/thoron` (P2.4, P2.21).
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
  + [(_PNG.format(2 * s), f"{_THEME}/default_200_percent/chromium/product_logo_{s}.png") for s in (16, 32)] \
  + [("branding/thoron/thoron.ico", p) for p in (
      "chrome/installer/mini_installer/mini_installer.ico", "chrome/installer/setup/setup.ico",
      "chrome/browser/web_applications/chrome_pwa_launcher/chrome_pwa_launcher.ico",
      f"{_THEME}/chromium/win/app_list.ico")]

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


CREDIT_MARK = "Alex313031"   # a line that names the upstream author is credit text: never renamed


def rename_product(text: str) -> tuple[str, int]:
    out, total = [], 0
    for line in text.splitlines(keepends=True):
        if CREDIT_MARK in line:
            out.append(line)
            continue
        line, n = NAME_RE.subn("Thoron", line)
        out.append(line)
        total += n
    return "".join(out), total


CHROMIUM_STRINGS_PATH = "chrome/app/chromium_strings.grd"
CREDIT_LINE = "The Chromium Authors, Alex313031 and KuchiSofts"
_ABOUT_EDITS = [
    ("About company name",
     r'(<message name="IDS_ABOUT_VERSION_COMPANY_NAME"[^>]*>\s*)(?:The (?:Thorium|Thoron) Authors|' + re.escape(CREDIT_LINE) + r')(\s*</message>)'),
    ("About copyright",
     r'(<message name="IDS_ABOUT_VERSION_COPYRIGHT"[^>]*>\s*Copyright <ph name="YEAR">[^<]*<ex>[^<]*</ex></ph> )'
     r'(?:The (?:Thorium|Thoron) Authors|' + re.escape(CREDIT_LINE) + r')(\. All rights reserved\.)'),
]


def edit_chromium_strings(text: str) -> str:
    """The About page credits Chromium, Thorium's author and Thoron (instead of "The Thoron Authors")."""
    missing = []
    for name, pattern in _ABOUT_EDITS:
        text, n = re.subn(pattern, lambda m: m.group(1) + CREDIT_LINE + m.group(2), text)
        if n != 1:
            missing.append(f"{name} ({n} matches)")
    if missing:
        raise IdentityError(f"{CHROMIUM_STRINGS_PATH}: anchors not found exactly once: {', '.join(missing)}")
    return text


def compute_remap(messages, id_fn) -> dict[str, str]:
    """Translation IDs to rewrite: GRIT derives a message's ID from its text, so renaming the product
    in a message changes its ID. `messages` holds (id, content, meaning) of the tree before renaming,
    where content is the presentable text or a list of text segments and ("ph", presentation)
    placeholders; each text segment is renamed on its own, exactly as in the file. id_fn is GRIT's
    GenerateMessageId. Refuses if id_fn does not reproduce an ID."""
    remap = {}
    for old_id, parts, meaning in messages:
        parts = [parts] if isinstance(parts, str) else parts
        content = "".join(p if isinstance(p, str) else p[1] for p in parts)
        if CREDIT_MARK in content:
            continue
        n = 0
        pieces = []
        for p in parts:
            if isinstance(p, str):
                p, k = rename_product(p)
                n += k
                pieces.append(p)
            else:
                pieces.append(p[1])
        renamed = "".join(pieces)
        new_meaning, m = rename_product(meaning)
        if not n and not m:
            continue
        if id_fn(content, meaning) != old_id:
            raise IdentityError(f"translation ID {old_id} cannot be reproduced; refusing to guess new IDs")
        remap[old_id] = id_fn(renamed, new_meaning)   # the file rename changes the meaning too
    return remap


def remap_xtb(text: str, remap: dict[str, str]) -> tuple[str, int]:
    """Point translations at the renamed messages' new IDs; never overwrite an ID that already exists."""
    existing = set(re.findall(r'<translation id="(\d+)"', text))
    n = 0
    for old, new in remap.items():
        if new in existing or old not in existing:
            continue
        text = text.replace(f'<translation id="{old}"', f'<translation id="{new}"', 1)
        existing.add(new)
        n += 1
    return text, n


def _grit(src: Path):
    path = str(Path(src) / "tools" / "grit")
    if path not in sys.path:
        sys.path.insert(0, path)
    from grit import grd_reader                     # the tree's own GRIT (it builds these files)
    from grit.extern import tclib
    from grit.node import message
    return grd_reader, tclib, message


def grd_messages(src: Path, grd: Path) -> list[tuple[str, str, str]]:
    grd_reader, _, message = _grit(src)
    names = set()
    for f in [grd] + sorted(grd.parent.rglob("*.grdp")):
        for expr in re.findall(r'expr="([^"]*)"', f.read_text(encoding="utf-8", errors="replace")):
            names.update(re.findall(r"[A-Za-z_]\w*", expr))
    defines = {n: False for n in names if n not in ("and", "or", "not", "True", "False", "lang", "pp_ifdef", "pp_if")}
    defines.update({"_chromium": True, "is_win": True})
    root = grd_reader.Parse(str(grd), defines=defines, target_platform="win32", debug=False)
    out = []
    for node in root.Preorder():
        if isinstance(node, message.MessageNode):
            try:
                clique = node.GetCliques()[0]
                msg = clique.GetMessage()
                parts = [c if isinstance(c, str) else ("ph", c.GetPresentation()) for c in msg.GetContent()]
                out.append((clique.GetId(), parts, msg.GetMeaning() or ""))
            except Exception:
                continue
    return out


def translation_files(grd: Path) -> list[Path]:
    text = grd.read_text(encoding="utf-8", errors="replace")
    return [grd.parent / p for p in re.findall(r'<file\s+path="([^"]+\.xtb)"', text)]


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


_NL = r"\r?\n"
_RELEASE = "chrome/installer/mini_installer/chrome.release"
# Windows program file and installer names (ROADMAP P2.20). Each replacement gives the number of times the old
# or new text must appear, so a changed upstream file stops the run instead of being half renamed. Removals drop
# Thorium-only installed files: thor_ver (read by the Thorium updater), the Thorium icons and content shell.
EXE_EDITS = {
    "build/win/reorder-imports.py": {"replace": [("thorium.exe", "thoron.exe", 6)]},
    "chrome/BUILD.gn": {"replace": [("/thorium.exe", "/thoron.exe", 4),
                                    ('_chrome_output_name = "initialexe/thorium"',
                                     '_chrome_output_name = "initialexe/thoron"', 1)]},
    "chrome/app/chrome_exe.ver": {"replace": [("INTERNAL_NAME=thorium_exe", "INTERNAL_NAME=thoron_exe", 1),
                                              ("ORIGINAL_FILENAME=thorium.exe", "ORIGINAL_FILENAME=thoron.exe", 1)]},
    "chrome/app/chrome_exe.vsprops": {"replace": [("\\thorium.exe", "\\thoron.exe", 1)]},
    "chrome/chrome_proxy/chrome_proxy_main_win.cc": {"replace": [('FILE_PATH_LITERAL("thorium.exe")',
                                                                  'FILE_PATH_LITERAL("thoron.exe")', 1)]},
    "chrome/common/chrome_constants.cc": {"replace": [('FPL("thorium.exe")', 'FPL("thoron.exe")', 4)]},
    "chrome/installer/launcher_support/chrome_launcher_support.cc": {
        "replace": [('kChromeExe[] = L"thorium.exe"', 'kChromeExe[] = L"thoron.exe"', 1)]},
    "chrome/installer/mini_installer/BUILD.gn": {"replace": [
        ('"$root_out_dir/thorium.exe"', '"$root_out_dir/thoron.exe"', 1),
        ('"thorium_mini_installer"', '"thoron_mini_installer"', 1),
        ('"thorium_ARM64_installer"', '"thoron_ARM64_installer"', 1),
        ('"thorium_${thorium_windows_installer_label}_mini_installer"',
         '"thoron_${thorium_windows_installer_label}_mini_installer"', 1)]},
    _RELEASE: {
        "replace": [("thorium.exe: %(ChromeDir)s\\", "thoron.exe: %(ChromeDir)s\\", 1)],
        "remove": [r"(?m)^# thor_ver for Thorium-WinUpdater" + _NL,
                   r"(?m)^thor_ver: %\(ChromeDir\)s\\" + _NL,
                   r"(?m)^thorium_shell\.(?:exe|ico): %\(VersionDir\)s\\" + _NL,
                   r"(?m)^thorium\.(?:ico|svg): %\(VersionDir\)s\\" + _NL],
        "forbid": [r"(?im)^(?!#)(?!thoron\.exe:)[^:\r\n]*thor[^:\r\n]*:"]},
    "chrome/installer/mini_installer/mini_installer_constants.cc": {
        "replace": [('kBrowserExe[] = L"thorium.exe"', 'kBrowserExe[] = L"thoron.exe"', 1)]},
    "chrome/installer/util/util_constants.h": {"replace": [('L"thorium.exe"', 'L"thoron.exe"', 1),
                                                           ('L"new_thorium.exe"', 'L"new_thoron.exe"', 1),
                                                           ('L"old_thorium.exe"', 'L"old_thoron.exe"', 1)]},
    "chrome/installer/setup/install_worker.cc": {
        "remove": [r"// Version marker consumed by Thorium-WinUpdater\." + _NL
                   + r'constexpr wchar_t kThorVer\[\] = L"thor_ver";' + _NL + _NL,
                   r"  // Add Thorium-specific files\." + _NL
                   + r"  install_list->AddCopyTreeWorkItem\(src_path\.Append\(kThorVer\)," + _NL
                   + r"\s*target_path\.Append\(kThorVer\), temp_path\);" + _NL + _NL],
        "forbid": [r"kThorVer|thor_ver"]},
}


_L = "chrome/installer/linux/"
_OUT = '"$root_out_dir/'
_LINE = r"(?m)^[ \t]*"
_EOL = r"\r?\n"
_GH = "https://github.com/KuchiSofts/thoron"
# Linux program, package, desktop and profile names (ROADMAP P2.4, P2.21), in the same anchored form as
# EXE_EDITS. Thoron gets its own package (thoron-browser), program (thoron), install folder
# (/opt/kuchisofts/thoron), desktop file and profile folder (~/.config/thoron), so it installs next to upstream
# thorium-browser and never reads or changes Thorium's profile. Upstream's developer test shell and its prebuilt
# `pak` tool are not packaged (smaller attack surface; /usr/bin/pak would also clash with upstream's package).
# The keyring entry is left as it is ("Chromium Safe Storage", as in upstream Thorium), so passwords in a profile
# copied from Thorium stay readable.
_INFO = _L + "common/chromium-browser.info"
LINUX_EDITS = {
    "base/version_info/nix/version_extra_utils.cc": {"replace": [
        ('kAppName = "org.chromium.Thorium"', 'kAppName = "org.kuchisofts.Thoron"', 1),
        ('kSessionNamePrefix = "thorium"', 'kSessionNamePrefix = "thoron"', 1)]},
    "chrome/BUILD.gn": {"replace": [('_chrome_output_name = "thorium"', '_chrome_output_name = "thoron"', 1),
                                    ('binary = "$root_out_dir/thorium"', 'binary = "$root_out_dir/thoron"', 1)]},
    "chrome/browser/memory_details_linux.cc": {"replace": [('process_name = u"thorium"', 'process_name = u"thoron"', 1)]},
    "chrome/browser/shell_integration_linux.cc": {"replace": [('return "thorium-browser";', 'return "thoron-browser";', 1)]},
    "chrome/common/channel_info_posix.cc": {"replace": [('return "thorium-browser.desktop";',
                                                         'return "thoron-browser.desktop";', 1)]},
    "chrome/common/chrome_constants.cc": {"replace": [('FPL("thorium")', 'FPL("thoron")', 6)]},
    "chrome/common/chrome_paths_linux.cc": {"replace": [('data_dir_basename = "thorium"',
                                                         'data_dir_basename = "thoron"', 1)]},
    "chrome/app/resources/manpage.1.in": {
        "replace": [("the web browser from Alex313031", "the web browser from KuchiSofts, based on Thorium by Alex313031", 1),
                    ("See the Thorium Repository for help", "See the Thoron repository for help", 1),
                    ("<https://github.com/Alex313031/thorium/>", f"<{_GH}/>", 1),
                    ("https://github.com/Alex313031/thorium/issues", f"{_GH}/issues", 1),
                    (".I $HOME/.config/@@PACKAGE@@", ".I $HOME/.config/thoron", 2),
                    (".I $HOME/.cache/@@PACKAGE@@", ".I $HOME/.cache/thoron", 1),
                    ("The Chromium team and Alex313031 \\-", "The Chromium team, Alex313031 and KuchiSofts \\-", 1)],
        "forbid": [r"github\.com/Alex313031", r"Thorium Repository"]},
    _L + "BUILD.gn": {
        "replace": [('Thorium packaging does not support', 'Thoron packaging does not support', 1),
                    (_OUT + 'thorium",', _OUT + 'thoron",', 1),
                    ('binary_input = "$root_out_dir/thorium"\n', 'binary_input = "$root_out_dir/thoron"\n', 1),
                    (_OUT + 'thorium.svg"', _OUT + 'thoron.svg"', 2),
                    ('copy("thorium_svg")', 'copy("thoron_svg")', 1),
                    ('":thorium_svg",', '":thoron_svg",', 1),
                    ('package = "thorium-browser"', 'package = "thoron-browser"', 1)],
        "remove": [_LINE + r'"\$root_out_dir/(?:content_shell\.pak|shell_resources\.pak|thorium_shell\.stripped'
                   r'|thorium_shell)",' + _EOL,
                   r'(?m)^strip_binary\("strip_thorium_shell"\) \{' + _EOL + r'(?:  [^\r\n]*' + _EOL + r')*\}'
                   + _EOL + _EOL + r"?",
                   _LINE + r'"(?::strip_thorium_shell|//content/shell:[a-z_]+)",' + _EOL],
        "forbid": [r"thorium_shell|content_shell|shell_resources|//content/shell|thorium-browser|thorium\.svg"]},
    _L + "common/installer.py": {
        "replace": [('"https://github.com/Alex313031/Thorium/releases"', f'"{_GH}/releases"', 1),
                    ('"thorium.svg",', '"thoron.svg",', 2),
                    ("Missing declared Thorium package inputs", "Missing declared Thoron package inputs", 1)],
        "remove": [_LINE + r'"(?:content_shell\.pak|shell_resources\.pak|thorium_shell\.stripped|thorium_shell\.png'
                   r'|thorium-shell|thorium-shell\.desktop|pak)",' + _EOL,
                   r"(?m)^        self\._install\(" + _EOL
                   + r'            self\.output_dir / "(?:thorium_shell\.stripped|pak|thorium-shell|thorium-shell\.desktop)",'
                   + _EOL + r"[^\r\n]*" + _EOL + r"[^\r\n]*" + _EOL + r"        \)" + _EOL,
                   _EOL + r"        pak_link = [^\r\n]*" + _EOL + r"(?:        [^\r\n]*" + _EOL + r"){3}"],
        "forbid": [r"thorium_shell|thorium-shell|content_shell|shell_resources|\bpak_link\b|/pak\b|\"pak\""]},
    _INFO: {
        "replace": [('PACKAGE="thorium-browser"', 'PACKAGE="thoron-browser"', 1),
                    ("PROGNAME=thorium\n", "PROGNAME=thoron\n", 1),
                    ("INSTALLDIR=/opt/chromium.org/thorium", "INSTALLDIR=/opt/kuchisofts/thoron", 1),
                    ('MENUNAME="Thorium Browser"', 'MENUNAME="Thoron"', 1),
                    ('SHORTDESC="The web browser from Alex313031"',
                     'SHORTDESC="The web browser from KuchiSofts, based on Thorium by Alex313031"', 1),
                    ('FULLDESC="Thorium is a browser that combines a minimal design with sophisticated technology to'
                     ' make the web faster, safer, and easier."',
                     'FULLDESC="Thoron is a fast, private and secure web browser, built on Chromium and on Thorium by'
                     ' Alex313031."', 1),
                    ('MAINTNAME="Thorium Linux Maintainers"', 'MAINTNAME="KuchiSofts"', 1),
                    ('MAINTMAIL="alex313031@gmail.com"', 'MAINTMAIL="KuchiSofts@users.noreply.github.com"', 1),
                    ('PRODUCTURL="https://thorium.rocks/"', f'PRODUCTURL="{_GH}"', 1),
                    ('DEVELOPER_NAME="The Chromium Authors and Alex313031"',
                     'DEVELOPER_NAME="The Chromium Authors, Alex313031 and KuchiSofts"', 1),
                    ('BUGTRACKERURL="https://github.com/Alex313031/thorium/issues"', f'BUGTRACKERURL="{_GH}/issues"', 1),
                    ('RDN="org.chromium.Thorium"', 'RDN="org.kuchisofts.Thoron"', 1)],
        "forbid": [r"thorium-browser|/thorium\b|org\.chromium\.Thorium|alex313031@|thorium\.rocks"]},
    _L + "common/wrapper": {
        "replace": [("# Prefer Thorium's bundled libraries.", "# Prefer Thoron's bundled libraries.", 1),
                    ("$HOME/.config/thorium/Crash Reports", "$HOME/.config/thoron/Crash Reports", 1),
                    ("APPNAME=thorium\n", "APPNAME=thoron\n", 1),
                    ('# DESKTOP="thorium-browser"', '# DESKTOP="thoron-browser"', 1),
                    ('TITLE="Thorium Browser"', 'TITLE="Thoron"', 1),
                    ('CHROME_DESKTOP="thorium-browser.desktop"', 'CHROME_DESKTOP="thoron-browser.desktop"', 1),
                    ("SET_BY_THORIUM", "SET_BY_THORON", 1),
                    ('echo "thorium-browser [-h', 'echo "thoron-browser [-h', 1),
                    ("man thorium-browser", "man thoron-browser", 2),
                    ("$XDG_CONFIG_HOME/thorium/thorium-flags.conf", "$XDG_CONFIG_HOME/thoron/thoron-flags.conf", 2),
                    ('"$XDG_CONFIG_HOME/thorium"', '"$XDG_CONFIG_HOME/thoron"', 2),
                    ("# Launch Thorium\n", "# Launch Thoron\n", 1)],
        "forbid": [r"(?i)thorium"]},
    _L + "common/desktop.template": {
        "replace": [("Name=Thorium Browser\n", "Name=Thoron\n", 1),
                    ("StartupWMClass=thorium-browser", "StartupWMClass=thoron-browser", 1),
                    ("temp-profile;content-shell;safe-mode;", "temp-profile;safe-mode;", 1)],
        "remove": [r"(?m)^\[Desktop Action content-shell\]" + _EOL + r"(?:[^\r\n\[][^\r\n]*" + _EOL + r")*" + _EOL],
        "forbid": [r"(?i)thorium|content-shell"]},
    _L + "common/appdata.xml.template": {
        "replace": [("    Thorium is an open-source browser project that aims to build a safer, faster,\n",
                     "    Thoron is a fast, private and secure web browser by KuchiSofts, built on\n", 1),
                    ("    and more stable way to experience the web.\n", "    Chromium and on Thorium by Alex313031.\n", 1),
                    ("    Thorium supports Vorbis", "    Thoron supports Vorbis", 1)],
        "remove": [r"(?m)^  <screenshots>" + _EOL + r"(?:[^\r\n]*" + _EOL + r")*?  </screenshots>" + _EOL],
        "forbid": [r"Thorium is|Thorium supports|Thorium_Screenshot"]},
    _L + "debian/control.template": {"replace": [("Conflicts: thorium-browser-unstable", "Conflicts: thoron-browser-unstable", 1),
                                                 ("Replaces: thorium-browser-unstable", "Replaces: thoron-browser-unstable", 1)],
                                     "forbid": [r"(?i)thorium"]},
    _L + "rpm/thorium.spec.template": {
        "replace": [("#   Thorium RPM spec", "#   Thoron RPM spec", 1),
                    ("ln -sf /opt/chromium.org/thorium/thorium-browser /usr/bin/",
                     "ln -sf @@INSTALLDIR@@/@@PACKAGE@@ /usr/bin/", 1)],
        "remove": [r"(?m)^# Extra Thorium stuff" + _EOL,
                   r"(?m)^/usr/(?:bin/pak|bin/thorium-shell|share/applications/thorium-shell\.desktop)" + _EOL],
        "forbid": [r"(?i)thorium|/usr/bin/pak"]},
}


def _edit_names(rel: str, text: str, spec: dict, always_forbid: list[str]) -> str:
    """Apply one anchored rename spec to one file; idempotent; raises naming the file on any surprise."""
    problems = []
    for old, new, count in spec.get("replace", []):
        found = text.count(old) + text.count(new)
        if found != count:
            problems.append(f"{old!r} found {found} times, expected {count}")
        text = text.replace(old, new)
    for pattern in spec.get("remove", []):
        text = re.sub(pattern, "", text)
    for pattern in spec.get("forbid", []) + always_forbid:
        hit = re.search(pattern, text)
        if hit:
            problems.append(f"left over after the edit: {hit.group(0)!r}")
    if problems:
        raise IdentityError(f"{rel}: " + "; ".join(problems))
    return text


def edit_exe_names(rel: str, text: str) -> str:
    """Rename the Windows program file in one build file (ROADMAP P2.20)."""
    return _edit_names(rel, text, EXE_EDITS[rel], [r"thorium\.exe"])


def edit_linux_names(rel: str, text: str) -> str:
    """Rename the Linux program, package, desktop and profile names in one file (ROADMAP P2.4, P2.21)."""
    return _edit_names(rel, text, LINUX_EDITS[rel], [])


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


def find_translated_grds(src: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(src), "grep", "-l", "-I", "-e", ".xtb", "--", "*.grd"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l for l in out.stdout.splitlines() if l]


def find_string_files(src: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(src), "grep", "-l", "-I", "-e", "Thorium", "--", "*.grd", "*.grdp", "*.xtb"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode not in (0, 1):
        raise IdentityError(f"git grep failed in {src}: {out.stderr.strip()}")
    return [l for l in out.stdout.splitlines() if l]


def apply(src: Path, repo: Path, string_files: list[str] | None = None, dry_run: bool = False,
          translations: bool = True) -> dict:
    """Plan every change in memory, stop on any problem, then write. Returns a summary."""
    src, repo = Path(src), Path(repo)
    planned: dict[Path, bytes] = {}
    problems: list[str] = []
    replacements = string_changes = 0
    files = string_files if string_files is not None else find_string_files(src)
    for rel in files:
        path = src / rel
        text = path.read_bytes().decode("utf-8")
        new, n = rename_product(text)
        if rel == CHROMIUM_STRINGS_PATH:
            try:
                new = edit_chromium_strings(new)
            except IdentityError as exc:
                problems.append(str(exc))
        if new != text:
            planned[path] = new.encode("utf-8")
            replacements += n
            string_changes += 1
    remapped = 0
    if translations:
        changed_xtb = {(src / r).resolve() for r in files if r.endswith(".xtb")}
        try:
            _, tclib, _ = _grit(src)
            for rel in find_translated_grds(src):
                grd = src / rel
                xtbs = [x for x in translation_files(grd) if x.is_file()]
                if not any(x.resolve() in changed_xtb for x in xtbs):
                    continue
                remap = compute_remap(grd_messages(src, grd), tclib.GenerateMessageId)
                for xtb in xtbs:
                    base = planned.get(xtb, xtb.read_bytes()).decode("utf-8")
                    new, n = remap_xtb(base, remap)
                    if n:
                        planned[xtb] = new.encode("utf-8")
                        remapped += n
        except (ImportError, IdentityError) as exc:
            problems.append(f"translation IDs: {exc}")
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
    for rel in dict.fromkeys([*EXE_EDITS, *LINUX_EDITS]):
        path = src / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
            continue
        text = path.read_bytes().decode("utf-8")
        try:
            new = edit_exe_names(rel, text) if rel in EXE_EDITS else text
            new = edit_linux_names(rel, new) if rel in LINUX_EDITS else new
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
    return {"strings": {"files": string_changes, "replacements": replacements},
            "translation_ids_remapped": remapped, "icons": icons,
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
