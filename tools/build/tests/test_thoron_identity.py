# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.build import thoron_identity as ti

REPO = Path(__file__).resolve().parents[3]

# Same layout as upstream Thorium's chrome/install_static/chromium_install_modes.h (M156).
INSTALL_MODES = """inline constexpr wchar_t kCompanyPathName[] = L"";
inline constexpr wchar_t kProductPathName[] = L"Thorium";
inline constexpr char kSafeBrowsingName[] = "thorium";
inline constexpr auto kOldTracingServiceIids = std::to_array<IID>({
    // Replaced in 2026-09. Delete after 2028-09.
    // {A3FD580A-FFD4-4075-9174-75D0B199D3CB}
    {0xa3fd580a,
     0xffd4,
     0x4075,
     {0x91, 0x74, 0x75, 0xd0, 0xb1, 0x99, 0xd3, 0xcb}},
});
        .app_guid = L"{7D2B3E1D-D096-4594-9D8F-A6667F12E0AF}",
        .base_app_name = L"Thorium",              // A distinct base_app_name.
        .base_app_id = L"Thorium",                // A distinct base_app_id.
        .browser_prog_id_prefix = L"ThoriumHTM",  // Browser ProgID prefix.
        .browser_prog_id_description =
            L"Thorium HTML Document",  // Browser ProgID description.
        .direct_launch_url_scheme = "chromium",
        .pdf_prog_id_prefix = L"ThoriumPDF",  // PDF ProgID prefix.
        .pdf_prog_id_description =
            L"Thorium PDF Document",  // PDF ProgID description.
        .active_setup_guid =
            L"{7D2B3E1D-D096-4594-9D8F-A6667F12E0AC}",  // Active Setup
        .toast_activator_clsid = {0x635EFA6F,
                                  0x08D6,
                                  0x4EC9,
                                  {0xBD, 0x14, 0x8A, 0x0F, 0xDE, 0x97, 0x51,
                                   0x59}},  // Toast Activator CLSID.
        .elevator_clsid = {0xD133B120,
                           0x6DB4,
                           0x4D6B,
                           {0x8B, 0xFE, 0x83, 0xBF, 0x8C, 0xA1, 0xB1,
                            0xB0}},  // Elevator CLSID.
        .elevator_iid = {0xbb19a0e5,
                         0xc6,
                         0x4966,
                         {0x94, 0xb2, 0x5a, 0xfe, 0xc6, 0xfe, 0xd9,
                          0x3a}},  // IElevator IID and TypeLib
        .tracing_service_clsid = {0x83f69367,
                                  0x442d,
                                  0x447f,
                                  {0x8b, 0xcc, 0x0e, 0x3f, 0x97, 0xbe, 0x9c,
                                   0xf2}},  // SystemTraceSession CLSID.
        .tracing_service_iid = {0xe0b03e2d,
                                0x7682,
                                0x4d83,
                                {0xb9, 0xff, 0x45, 0x74, 0xaf, 0x72, 0x05,
                                 0x00}},  // ISystemTraceSessionChromium IID and
        .sandbox_sid_prefix =
            L"S-1-15-2-3251537155-1984446955-2931258699-841473695-"
            L"1938553385-"
            L"924012148-",  // App container sid prefix for sandbox.
"""
THORIUM_IDS = ("7D2B3E1D", "635EFA6F", "D133B120", "83f69367", "A3FD580A", "a3fd580a", "3251537155",
               "ThoriumHTM", "ThoriumPDF", '"chromium"', 'L"Thorium"', '"thorium"')

BRANDING = """COMPANY_FULLNAME=Alex313031
COMPANY_SHORTNAME=Alex313031
PRODUCT_FULLNAME=Thorium
PRODUCT_SHORTNAME=Thorium
PRODUCT_INSTALLER_FULLNAME=Thorium Installer
PRODUCT_INSTALLER_SHORTNAME=Thorium Installer
COPYRIGHT=Copyright @LASTCHANGE_YEAR@ The Chromium Authors and Alex313031.
MAC_BUNDLE_ID=org.chromium.Thorium
MAC_CREATOR_CODE=Cr24
MAC_TEAM_ID=
"""


class RenameProductTests(unittest.TestCase):
    def test_changes_the_product_name(self):
        cases = {
            "About Thorium": "About Thoron",
            "<ph name=\"PRODUCT_NAME\">$1<ex>Thorium</ex></ph>": "<ph name=\"PRODUCT_NAME\">$1<ex>Thoron</ex></ph>",
            "Thorium's settings": "Thoron's settings",
            "Relaunch Thorium.": "Relaunch Thoron.",
            "(Thorium)": "(Thoron)",
        }
        for before, after in cases.items():
            self.assertEqual(ti.rename_product(before)[0], after, before)

    def test_leaves_urls_paths_identifiers_and_lowercase_alone(self):
        for text in ("https://github.com/Alex313031/Thorium-Win", "github.com/Alex313031/thorium",
                     "Thorium_Public_Bundle", "THORIUM_DEBUG", "thorium_flag_entries.h", "org.chromium.Thorium",
                     "Thorium.app", "ThoriumHTM", "Thorium/User Data", "%LOCALAPPDATA%\\Thorium\\"):
            self.assertEqual(ti.rename_product(text), (text, 0), text)

    def test_idempotent(self):
        once, n1 = ti.rename_product("Thorium and Thorium")
        twice, n2 = ti.rename_product(once)
        self.assertEqual((once, n1, twice, n2), ("Thoron and Thoron", 2, "Thoron and Thoron", 0))


class InstallModesTests(unittest.TestCase):
    def test_every_identity_value_changes(self):
        out = ti.edit_install_modes(INSTALL_MODES)
        for old in THORIUM_IDS:
            self.assertNotIn(old, out, old)
        self.assertIn('kProductPathName[] = L"Thoron"', out)
        self.assertIn('kSafeBrowsingName[] = "thoron"', out)
        self.assertIn(f'.app_guid = L"{ti.THORON_IDS["app_guid"]}"', out)
        self.assertIn('.browser_prog_id_prefix = L"ThoronHTM"', out)
        self.assertIn('L"Thoron PDF Document"', out)
        self.assertIn('.direct_launch_url_scheme = "thoron"', out)
        self.assertIn(ti.guid_struct(ti.THORON_IDS["toast_activator_clsid"]), out)
        self.assertIn(ti.THORON_IDS["sandbox_sid_prefix"], out)

    def test_interface_iids_stay_with_the_checked_in_midl_output(self):
        out = ti.edit_install_modes(INSTALL_MODES)
        self.assertIn("{0xbb19a0e5", out)
        self.assertIn("{0xe0b03e2d", out)

    def test_new_ids_differ_from_each_other_and_from_thorium(self):
        values = [v.upper() for k, v in ti.THORON_IDS.items() if k != "sandbox_sid_prefix"]
        self.assertEqual(len(values), len(set(values)))
        for v in values:
            self.assertRegex(v, r"^\{?[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}?$")

    def test_missing_anchor_raises_and_names_it(self):
        broken = re.sub(r".*\.app_guid = .*\n", "", INSTALL_MODES)
        with self.assertRaises(ti.IdentityError) as ctx:
            ti.edit_install_modes(broken)
        self.assertIn("app_guid", str(ctx.exception))

    def test_idempotent(self):
        once = ti.edit_install_modes(INSTALL_MODES)
        self.assertEqual(ti.edit_install_modes(once), once)


class BrandingTests(unittest.TestCase):
    def test_names_and_credits(self):
        out = ti.edit_branding(BRANDING)
        self.assertIn("PRODUCT_FULLNAME=Thoron\n", out)
        self.assertIn("PRODUCT_INSTALLER_SHORTNAME=Thoron Installer\n", out)
        copyright_line = next(l for l in out.splitlines() if l.startswith("COPYRIGHT="))
        for credit in ("The Chromium Authors", "Alex313031", "KuchiSofts"):
            self.assertIn(credit, copyright_line)
        self.assertIn("MAC_CREATOR_CODE=Cr24\n", out)       # untouched keys stay
        self.assertEqual(ti.edit_branding(out), out)

    def test_missing_key_raises(self):
        with self.assertRaises(ti.IdentityError):
            ti.edit_branding(BRANDING.replace("PRODUCT_FULLNAME=Thorium\n", ""))


# The Windows program-file references, as upstream Thorium M156 has them (P2.20).
EXE_FIXTURES = {
    "build/win/reorder-imports.py": (
        '    """Swap chrome_elf.dll to be the first import of thorium.exe.\n'
        "    input_image = os.path.join(input_dir, 'thorium.exe')\n"
        "    output_image = os.path.join(output_dir, 'thorium.exe')\n"
        "    for fname in glob.iglob(os.path.join(input_dir, 'thorium.exe.*')):\n"
        "        '-i', '--input', help='reorder thorium.exe in DIR', metavar='DIR'\n"
        "        '-o', '--output', help='write new thorium.exe to DIR', metavar='DIR'\n"),
    "chrome/BUILD.gn": (
        '      "$root_out_dir/initialexe/thorium.exe",\n      "$root_out_dir/initialexe/thorium.exe.pdb",\n'
        '      "$root_out_dir/thorium.exe",\n      "$root_out_dir/thorium.exe.pdb",\n'
        '  if (is_win) {\n    _chrome_output_name = "initialexe/thorium"\n  } else if (is_chromeos) {\n'
        '    _chrome_output_name = "chrome"\n  } else {\n    _chrome_output_name = "thorium"\n  }\n'
        '      if (is_chromeos) {\n        binary = "$root_out_dir/chrome"\n      } else {\n'
        '        binary = "$root_out_dir/thorium"\n      }\n'),
    "chrome/app/chrome_exe.ver": "INTERNAL_NAME=thorium_exe\nORIGINAL_FILENAME=thorium.exe\n",
    "chrome/app/chrome_exe.vsprops": '\t\tOutputFile="$(OutDir)\\thorium.exe"\n',
    "chrome/chrome_proxy/chrome_proxy_main_win.cc": '    FILE_PATH_LITERAL("thorium.exe");\n',
    "chrome/common/chrome_constants.cc": (
        "#if BUILDFLAG(IS_WIN)\nconst base::FilePath::CharType kBrowserProcessExecutableName[] =\n"
        '    FPL("thorium.exe");\nconst base::FilePath::CharType kHelperProcessExecutableName[] =\n'
        '    FPL("thorium.exe");\n#elif BUILDFLAG(IS_ANDROID)\n'
        'const base::FilePath::CharType kBrowserProcessExecutableName[] = FPL("thorium");\n'
        '#elif BUILDFLAG(IS_POSIX)\n'
        'const base::FilePath::CharType kBrowserProcessExecutableName[] = FPL("thorium");\n#endif\n'
        "#if BUILDFLAG(IS_WIN)\nconst base::FilePath::CharType kBrowserProcessExecutablePath[] =\n"
        '    FPL("thorium.exe");\nconst base::FilePath::CharType kHelperProcessExecutablePath[] =\n'
        '    FPL("thorium.exe");\n#elif BUILDFLAG(IS_ANDROID)\n'
        'const base::FilePath::CharType kBrowserProcessExecutablePath[] = FPL("thorium");\n'
        'const base::FilePath::CharType kHelperProcessExecutablePath[] = FPL("thorium");\n'
        '#elif BUILDFLAG(IS_POSIX)\n'
        'const base::FilePath::CharType kBrowserProcessExecutablePath[] = FPL("thorium");\n'
        'const base::FilePath::CharType kHelperProcessExecutablePath[] = FPL("thorium");\n#endif\n'),
    "chrome/installer/launcher_support/chrome_launcher_support.cc": 'const wchar_t kChromeExe[] = L"thorium.exe";\n',
    "chrome/installer/mini_installer/BUILD.gn": (
        '    "$root_out_dir/chrome_elf.dll",\n    "$root_out_dir/thorium.exe",\n'
        '_thorium_mini_installer_target = "thorium_mini_installer"\nif (current_cpu == "arm64") {\n'
        '  _thorium_mini_installer_target = "thorium_ARM64_installer"\n'
        '} else if (thorium_windows_installer_label != "") {\n  _thorium_mini_installer_target =\n'
        '      "thorium_${thorium_windows_installer_label}_mini_installer"\n}\n'),
    "chrome/installer/mini_installer/chrome.release": (
        "# Copyright 2026 The Chromium Authors, Alex313031, ltguillaume, and gz83\n[GENERAL]\n"
        "thorium.exe: %(ChromeDir)s\\\nchrome_proxy.exe: %(ChromeDir)s\\\n# thor_ver for Thorium-WinUpdater\n"
        "thor_ver: %(ChromeDir)s\\\nshell_resources.pak: %(VersionDir)s\\\nthorium_shell.exe: %(VersionDir)s\\\n"
        "thorium_shell.ico: %(VersionDir)s\\\n# Add pak to Thorium.\npack.bat: %(VersionDir)s\\\n[HIDPI]\n"
        "chrome_200_percent.pak: %(VersionDir)s\\\nthorium.ico: %(VersionDir)s\\\nthorium.svg: %(VersionDir)s\\\n"
        "\n[FFMPEG]\nffmpeg.dll: %(VersionDir)s\\\n"),
    "chrome/installer/mini_installer/mini_installer_constants.cc": 'const wchar_t kBrowserExe[] = L"thorium.exe";\n',
    "chrome/installer/util/util_constants.h": (
        'inline constexpr wchar_t kChromeExe[] = L"thorium.exe";\n'
        'inline constexpr wchar_t kChromeNewExe[] = L"new_thorium.exe";\n'
        'inline constexpr wchar_t kChromeOldExe[] = L"old_thorium.exe";\n'),
    "chrome/installer/setup/install_worker.cc": (
        "namespace {\n\n// Version marker consumed by Thorium-WinUpdater.\n"
        'constexpr wchar_t kThorVer[] = L"thor_ver";\n\nvoid AddInstallerCopyTasks() {\n'
        "  // Add Thorium-specific files.\n  install_list->AddCopyTreeWorkItem(src_path.Append(kThorVer),\n"
        "                                    target_path.Append(kThorVer), temp_path);\n\n"
        "  // Move chrome.exe to new_chrome.exe if the target is in use.\n}\n"),
}


def write_exe_fixtures(src: Path) -> None:
    for rel, text in EXE_FIXTURES.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(text.encode("utf-8"))


class ExeNameTests(unittest.TestCase):
    def test_every_windows_reference_is_renamed(self):
        out = {rel: ti.edit_exe_names(rel, text) for rel, text in EXE_FIXTURES.items()}
        joined = "".join(out.values())
        self.assertNotIn("thorium.exe", joined)
        self.assertNotIn("thor_ver", joined)
        self.assertNotIn("kThorVer", joined)
        self.assertIn("'thoron.exe.*'", out["build/win/reorder-imports.py"])
        self.assertIn('_chrome_output_name = "initialexe/thoron"', out["chrome/BUILD.gn"])
        self.assertIn('L"new_thoron.exe"', out["chrome/installer/util/util_constants.h"])
        self.assertIn("ORIGINAL_FILENAME=thoron.exe", out["chrome/app/chrome_exe.ver"])
        self.assertIn('"thoron_${thorium_windows_installer_label}_mini_installer"',
                      out["chrome/installer/mini_installer/BUILD.gn"])
        self.assertIn("// Move chrome.exe to new_chrome.exe", out["chrome/installer/setup/install_worker.cc"])

    def test_the_installed_file_list_names_nothing_after_thorium(self):
        release = ti.edit_exe_names("chrome/installer/mini_installer/chrome.release",
                                    EXE_FIXTURES["chrome/installer/mini_installer/chrome.release"])
        entries = [l.split(":")[0] for l in release.splitlines() if ":" in l and not l.startswith("#")]
        self.assertIn("thoron.exe", entries)
        self.assertFalse([e for e in entries if "thor" in e.lower() and e != "thoron.exe"], entries)
        self.assertIn("pack.bat: %(VersionDir)s\\", release)           # other entries are kept
        self.assertIn("Alex313031, ltguillaume, and gz83", release)    # credits are kept

    def test_other_platforms_keep_their_names(self):
        build = ti.edit_exe_names("chrome/BUILD.gn", EXE_FIXTURES["chrome/BUILD.gn"])
        self.assertIn('    _chrome_output_name = "thorium"\n', build)   # Linux binary: a separate task
        consts = ti.edit_exe_names("chrome/common/chrome_constants.cc", EXE_FIXTURES["chrome/common/chrome_constants.cc"])
        self.assertEqual(consts.count('FPL("thorium")'), 6)
        self.assertEqual(consts.count('FPL("thoron.exe")'), 4)

    def test_idempotent(self):
        for rel, text in EXE_FIXTURES.items():
            once = ti.edit_exe_names(rel, text)
            self.assertEqual(ti.edit_exe_names(rel, once), once, rel)

    def test_missing_anchor_raises_and_names_the_file(self):
        text = EXE_FIXTURES["chrome/common/chrome_constants.cc"].replace('FPL("thorium.exe")', 'FPL("x.exe")', 1)
        with self.assertRaisesRegex(ti.IdentityError, "chrome_constants.cc"):
            ti.edit_exe_names("chrome/common/chrome_constants.cc", text)

    def test_unexpected_leftover_raises(self):
        text = EXE_FIXTURES["chrome/installer/mini_installer/chrome.release"] + "thor_ver2: %(ChromeDir)s\\\n"
        with self.assertRaisesRegex(ti.IdentityError, "chrome.release"):
            ti.edit_exe_names("chrome/installer/mini_installer/chrome.release", text)

    def test_crlf_files_keep_their_line_endings(self):
        rel = "chrome/installer/setup/install_worker.cc"
        out = ti.edit_exe_names(rel, EXE_FIXTURES[rel].replace("\n", "\r\n"))
        self.assertNotIn("kThorVer", out)
        self.assertNotIn("\n", out.replace("\r\n", ""))

    def test_every_file_is_covered(self):
        self.assertEqual(set(ti.EXE_EDITS), set(EXE_FIXTURES))


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.src = self.tmp / "src"
        (self.src / Path(ti.INSTALL_MODES_PATH).parent).mkdir(parents=True)
        (self.src / ti.INSTALL_MODES_PATH).write_text(INSTALL_MODES, encoding="utf-8")
        (self.src / Path(ti.BRANDING_PATH).parent).mkdir(parents=True)
        (self.src / ti.BRANDING_PATH).write_text(BRANDING, encoding="utf-8")
        (self.src / "chrome/app").mkdir(parents=True, exist_ok=True)
        self.strings = self.src / "chrome/app/chromium_strings.grd"
        self.strings.write_text('<message name="IDS_PRODUCT_NAME">Thorium</message>\n' + CreditsTests.ABOUT,
                                encoding="utf-8")
        for _, dest in ti.ICON_MAP:
            (self.src / dest).parent.mkdir(parents=True, exist_ok=True)
            (self.src / dest).write_bytes(b"old icon")
        write_exe_fixtures(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_icon_sources_exist_in_the_repo(self):
        for source, _ in ti.ICON_MAP:
            self.assertTrue((REPO / source).is_file(), source)

    def test_apply_changes_everything_then_is_a_no_op(self):
        summary = ti.apply(self.src, REPO, string_files=["chrome/app/chromium_strings.grd"], translations=False)
        self.assertEqual(summary["strings"]["replacements"], 3)
        self.assertIn("Thoron", self.strings.read_text(encoding="utf-8"))
        self.assertIn('L"Thoron"', (self.src / ti.INSTALL_MODES_PATH).read_text(encoding="utf-8"))
        source, dest = ti.ICON_MAP[0]
        self.assertEqual((self.src / dest).read_bytes(), (REPO / source).read_bytes())
        util = (self.src / "chrome/installer/util/util_constants.h").read_text(encoding="utf-8")
        self.assertIn('L"thoron.exe"', util)
        again = ti.apply(self.src, REPO, string_files=["chrome/app/chromium_strings.grd"], translations=False)
        self.assertEqual(again["strings"]["replacements"], 0)
        self.assertEqual(again["files_changed"], 0)

    def test_apply_is_all_or_nothing(self):
        broken = re.sub(r".*\.app_guid = .*\n", "", INSTALL_MODES)
        (self.src / ti.INSTALL_MODES_PATH).write_text(broken, encoding="utf-8")
        before = {p: p.read_bytes() for p in self.src.rglob("*") if p.is_file()}
        with self.assertRaises(ti.IdentityError):
            ti.apply(self.src, REPO, string_files=["chrome/app/chromium_strings.grd"], translations=False)
        after = {p: p.read_bytes() for p in self.src.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class CreditsTests(unittest.TestCase):
    ABOUT = ('<message name="IDS_ABOUT_VERSION_COMPANY_NAME" desc="Company name on the about pages">\n'
             '            The Thorium Authors\n          </message>\n'
             '<message name="IDS_ABOUT_VERSION_COPYRIGHT" desc="Copyright information on the about pages">\n'
             '            Copyright <ph name="YEAR">{0,date,y}<ex>2016</ex></ph> The Thorium Authors. '
             'All rights reserved.\n          </message>\n')

    def test_about_page_keeps_every_credit(self):
        out = ti.edit_chromium_strings(ti.rename_product(self.ABOUT)[0])
        self.assertIn("The Chromium Authors, Alex313031 and KuchiSofts", out)
        self.assertEqual(out.count("Alex313031"), 2)
        self.assertNotIn("Thoron Authors", out)
        self.assertEqual(ti.edit_chromium_strings(out), out)

    def test_about_page_anchor_missing_raises(self):
        with self.assertRaises(ti.IdentityError):
            ti.edit_chromium_strings('<message name="OTHER">x</message>')

    def test_lines_crediting_upstream_are_never_renamed(self):
        text = "Alex313031 recommends Thorium\nAbout Thorium\n"
        self.assertEqual(ti.rename_product(text), ("Alex313031 recommends Thorium\nAbout Thoron\n", 1))


class TranslationIdTests(unittest.TestCase):
    @staticmethod
    def fake_id(text, meaning=""):
        return str(abs(hash((text, meaning))) % 10**12)

    def test_remap_old_to_new_ids(self):
        msgs = [(self.fake_id("About Thorium"), "About Thorium", ""),
                (self.fake_id("Hello PRODUCT_NAME"), "Hello PRODUCT_NAME", ""),      # name only in a placeholder
                (self.fake_id("Alex313031 recommends Thorium"), "Alex313031 recommends Thorium", "")]
        remap = ti.compute_remap(msgs, self.fake_id)
        self.assertEqual(remap, {self.fake_id("About Thorium"): self.fake_id("About Thoron")})

    def test_name_right_after_a_placeholder_is_renamed_like_in_the_file(self):
        parts = [("ph", "BEGIN_LINK"), "Thorium warns you", ("ph", "END_LINK")]
        old = self.fake_id("BEGIN_LINKThorium warns youEND_LINK")
        remap = ti.compute_remap([(old, parts, "")], self.fake_id)
        self.assertEqual(remap, {old: self.fake_id("BEGIN_LINKThoron warns youEND_LINK")})

    def test_renamed_meaning_counts_in_the_new_id(self):
        old = self.fake_id("Saved from Thorium", "Folder for files saved from Thorium")
        remap = ti.compute_remap([(old, "Saved from Thorium", "Folder for files saved from Thorium")], self.fake_id)
        self.assertEqual(remap, {old: self.fake_id("Saved from Thoron", "Folder for files saved from Thoron")})

    def test_meaning_alone_changes_the_id(self):
        old = self.fake_id("Open folder", "Folder made by Thorium")
        remap = ti.compute_remap([(old, "Open folder", "Folder made by Thorium")], self.fake_id)
        self.assertEqual(remap, {old: self.fake_id("Open folder", "Folder made by Thoron")})

    def test_remap_rejects_an_id_function_that_does_not_match_grit(self):
        with self.assertRaises(ti.IdentityError):
            ti.compute_remap([("123", "About Thorium", "")], self.fake_id)

    def test_xtb_ids_rewritten_without_clobbering_existing(self):
        xtb = ('<translation id="111">A</translation>\n<translation id="222">B</translation>\n'
               '<translation id="333">C</translation>\n')
        out, n = ti.remap_xtb(xtb, {"111": "999", "222": "333"})          # 333 already exists: keep both
        self.assertEqual(n, 1)
        self.assertIn('id="999">A', out)
        self.assertIn('id="222">B', out)
        self.assertEqual(ti.remap_xtb(out, {"111": "999"})[1], 0)



if __name__ == "__main__":
    unittest.main()
