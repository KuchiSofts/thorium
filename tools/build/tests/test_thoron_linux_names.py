# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Linux program, package and profile names (ROADMAP P2.4, P2.21)."""
import re
import unittest

from tools.build import thoron_identity as ti
from tools.build.tests.test_thoron_identity import EXE_FIXTURES

L = "chrome/installer/linux/"

# Excerpts of the real files after the upstream Thorium M156 series is applied to Chromium 158.
LINUX_FIXTURES = {
    "base/version_info/nix/version_extra_utils.cc": (
        '#if BUILDFLAG(GOOGLE_CHROME_BRANDING)\n  static constexpr std::string_view kAppName = "com.google.Chrome";\n'
        '#else\n  static constexpr std::string_view kAppName = "org.chromium.Thorium";\n#endif\n'
        '#if BUILDFLAG(GOOGLE_CHROME_BRANDING)\n  static constexpr std::string_view kSessionNamePrefix = "chrome";\n'
        '#else\n  static constexpr std::string_view kSessionNamePrefix = "thorium";\n#endif\n'),
    "chrome/browser/memory_details_linux.cc": '  current_browser.process_name = u"thorium";\n',
    "chrome/browser/shell_integration_linux.cc": (
        '#if BUILDFLAG(GOOGLE_CHROME_BRANDING)\n  return "google-chrome";\n'
        '#else  // BUILDFLAG(CHROMIUM_BRANDING)\n  return "thorium-browser";\n#endif\n'),
    "chrome/common/channel_info_posix.cc": '  return "thorium-browser.desktop";\n',
    "chrome/common/chrome_paths_linux.cc": (
        '#elif BUILDFLAG(GOOGLE_CHROME_BRANDING)\n  std::string data_dir_basename = "google-chrome";\n'
        '#else\n  std::string data_dir_basename = "thorium";\n#endif\n'),
    "chrome/app/resources/manpage.1.in": (
        '.SH NAME\n@@PACKAGE@@ \\- the web browser from Alex313031\n'
        '.SH DESCRIPTION\nSee the Thorium Repository for help on using the browser.\n.IP\n'
        '<https://github.com/Alex313031/thorium/>\n'
        '.I $HOME/.config/@@PACKAGE@@ .\nSeparate instances of @@MENUNAME@@ must use separate user data directories;\n'
        '.I $HOME/.config/@@PACKAGE@@\n.I $HOME/.cache/@@PACKAGE@@\n'
        'http://code.google.com/p/chromium/issues/list & https://github.com/Alex313031/thorium/issues\n'
        '.SH AUTHOR\nThe Chromium team and Alex313031 \\- <http://www.chromium.org>\n'),
    L + "BUILD.gn": (
        'assert(!enable_flatpak, "Thorium packaging does not support Flatpak.")\n'
        'thorium_package_generated_inputs = [\n'
        '  "$root_out_dir/content_shell.pak",\n'
        '  "$root_out_dir/shell_resources.pak",\n'
        '  "$root_out_dir/thorium_shell.stripped",\n'
        ']\n'
        'packaging_files_executables = [\n'
        '  "$root_out_dir/thorium",\n'
        '  "$root_out_dir/chromedriver",\n'
        '  "$root_out_dir/thorium_shell",\n'
        ']\n'
        '                    "$root_out_dir/thorium.svg",\n'
        'strip_binary("strip_chrome_binary") {\n'
        '  binary_input = "$root_out_dir/thorium"\n'
        '  deps = [ "//chrome" ]\n'
        '}\n'
        '\n'
        'strip_binary("strip_thorium_shell") {\n'
        '  testonly = true\n'
        '  binary_input = "$root_out_dir/thorium_shell"\n'
        '  deps = [ "//content/shell:thorium_shell" ]\n'
        '}\n'
        '\n'
        'group("thorium_package_extras") {\n'
        '  testonly = true\n'
        '  public_deps = [\n'
        '    ":strip_thorium_shell",\n'
        '    "//chrome/test/chromedriver:chromedriver_server",\n'
        '    "//content/shell:copy_shell_resources",\n'
        '    "//content/shell:pak",\n'
        '    "//content/shell:thorium_shell",\n'
        '  ]\n'
        '}\n'
        'copy("thorium_svg") {\n'
        '  sources = [ "//chrome/app/theme/chromium/product_logo.svg" ]\n'
        '  outputs = [ "$root_out_dir/thorium.svg" ]\n'
        '}\n'
        '    sources = [ "rpm/thorium.spec.template" ]\n'
        '    ":thorium_svg",\n'
        '  } else {\n'
        '    package = "thorium-browser"\n'
        '  }\n'),
    L + "common/installer.py": (
        '    thorium_releases = "https://github.com/Alex313031/Thorium/releases"\n'
        '                inspector_overlay_dir / filename,\n'
        '                mode=0o644,\n'
        '            )\n'
        '\n'
        '        pak_link = self.staging_dir / "usr/bin/pak"\n'
        '        if pak_link.exists() or pak_link.is_symlink():\n'
        '            pak_link.unlink()\n'
        '        os.symlink(f"{self.context[\'INSTALLDIR\']}/pak", pak_link)\n'
        '\n'
        '    def _stage_resources(self, install_dir):\n'
        '    def _stage_thorium_extras(self, install_dir):\n'
        '        required_files = [\n'
        '            "chromedriver",\n'
        '            "content_shell.pak",\n'
        '            "resources/inspector_overlay/main.js",\n'
        '            "shell_resources.pak",\n'
        '            "thorium.svg",\n'
        '            "thorium_shell.stripped",\n'
        '            "thorium_shell.png",\n'
        '            "thorium-shell",\n'
        '            "thorium-shell.desktop",\n'
        '            "ui_resources_100_percent.pak",\n'
        '            "pak",\n'
        '        ]\n'
        '                "Missing declared Thorium package inputs: "\n'
        '        for filename in [\n'
        '            "content_shell.pak",\n'
        '            "shell_resources.pak",\n'
        '            "thorium.svg",\n'
        '            "thorium_shell.png",\n'
        '            "ui_resources_100_percent.pak",\n'
        '        ]:\n'
        '            self._install_into_dir(\n'
        '                self.output_dir / filename,\n'
        '                install_dir,\n'
        '                mode=0o644,\n'
        '            )\n'
        '\n'
        '        self._install(\n'
        '            self.output_dir / "thorium_shell.stripped",\n'
        '            install_dir / "thorium_shell",\n'
        '            mode=0o755,\n'
        '        )\n'
        '        self._install(\n'
        '            self.output_dir / "chromedriver",\n'
        '            install_dir / "chromedriver",\n'
        '            mode=0o755,\n'
        '        )\n'
        '        self._install(\n'
        '            self.output_dir / "pak",\n'
        '            install_dir / "pak",\n'
        '            mode=0o755,\n'
        '        )\n'
        '        self._install(\n'
        '            self.output_dir / "thorium-shell",\n'
        '            self.staging_dir / "usr/bin/thorium-shell",\n'
        '            mode=0o755,\n'
        '        )\n'
        '        self._install(\n'
        '            self.output_dir / "thorium-shell.desktop",\n'
        '            self.staging_dir / "usr/share/applications/thorium-shell.desktop",\n'
        '            mode=0o644,\n'
        '        )\n'
        '\n'
        '        if self.clearkey_cdm_path:\n'),
    L + "common/chromium-browser.info": (
        '# Copyright 2026 The Chromium Authors and Alex313031\n'
        'PACKAGE="thorium-browser"\n'
        'PROGNAME=thorium\n'
        'INSTALLDIR=/opt/chromium.org/thorium\n'
        'ENROLLMENTDIR=/etc/chromium/policies/enrollment\n'
        'MENUNAME="Thorium Browser"\n'
        'SHORTDESC="The web browser from Alex313031"\n'
        'FULLDESC="Thorium is a browser that combines a minimal design with sophisticated technology to make the'
        ' web faster, safer, and easier."\n'
        'MAINTNAME="Thorium Linux Maintainers"\n'
        'MAINTMAIL="alex313031@gmail.com"\n'
        'PRODUCTURL="https://thorium.rocks/"\n'
        'DEVELOPER_NAME="The Chromium Authors and Alex313031"\n'
        'BUGTRACKERURL="https://github.com/Alex313031/thorium/issues"\n'
        'RDN="org.chromium.Thorium"\n'),
    L + "common/wrapper": (
        '# Copyright 2026 The Chromium Authors, the AUR, and Alex313031\n'
        "# Prefer Thorium's bundled libraries.\n"
        'find "$HOME/.config/thorium/Crash Reports/pending/" -mtime +30 \\\n'
        'APPNAME=thorium\n'
        '# DESKTOP="thorium-browser"\n'
        'TITLE="Thorium Browser"\n'
        'export CHROME_DESKTOP="thorium-browser.desktop"\n'
        'export GNOME_DISABLE_CRASH_DIALOG=SET_BY_THORIUM\n'
        '  echo "thorium-browser [-h|--help] [--temp-profile] [options] [URL]"\n'
        "  MANWIDTH=80 man thorium-browser | sed -e '1,/OPTIONS/d; /ENVIRONMENT/,$d'\n"
        "  echo \" See 'man thorium-browser' for more details\"\n"
        'if [[ -f "$XDG_CONFIG_HOME/thorium/thorium-flags.conf" ]]; then\n'
        '   CHROME_USER_FLAGS="$(cat "$XDG_CONFIG_HOME/thorium/thorium-flags.conf")"\n'
        '  PROFILE="$XDG_CONFIG_HOME/thorium"\n'
        '  CACHE="$XDG_CONFIG_HOME/thorium"\n'
        '# Launch Thorium\n'),
    L + "common/desktop.template": (
        '[Desktop Entry]\nVersion=1.0\nName=Thorium Browser\n'
        'StartupWMClass=thorium-browser\n'
        'Actions=new-window;new-private-window;temp-profile;content-shell;safe-mode;dark-mode;\n'
        'Exec=/usr/bin/@@USR_BIN_SYMLINK_NAME@@ --temp-profile %U\n'
        '\n'
        '[Desktop Action content-shell]\n'
        'Name=Open Thorium Shell\n'
        'Exec=/usr/bin/thorium-shell %U\n'
        '\n'
        '[Desktop Action safe-mode]\n'
        'Name=Open in Safe Mode\n'),
    L + "common/appdata.xml.template": (
        '<!-- Copyright 2026 The Chromium Authors and Alex313031 -->\n'
        '    <p>\n'
        '    Thorium is an open-source browser project that aims to build a safer, faster,\n'
        '    and more stable way to experience the web.\n'
        '    </p>\n'
        '    Thorium supports Vorbis, Theora, WebM, AAC, H.264, H.265, MP3, and HTML5 audio and video standards.\n'
        '  <url type="homepage">@@PRODUCTURL@@</url>\n'
        '  <screenshots>\n'
        '    <screenshot type="default">\n'
        '      <image>https://raw.githubusercontent.com/Alex313031/Thorium/main/logos/STAGING/Thorium_Screenshot.png'
        '</image>\n'
        '      <caption/>\n'
        '    </screenshot>\n'
        '  </screenshots>\n'
        '  <translation/>\n'),
    L + "debian/control.template": (
        'Recommends: vdpau-driver-all\nConflicts: thorium-browser-unstable\nReplaces: thorium-browser-unstable\n'),
    L + "rpm/thorium.spec.template": (
        '#   Thorium RPM spec\n'
        '/usr/bin/@@USR_BIN_SYMLINK_NAME@@\n'
        '# Extra Thorium stuff\n'
        '/usr/bin/pak\n'
        '/usr/bin/thorium-shell\n'
        '/usr/share/applications/thorium-shell.desktop\n'
        '/usr/share/appdata/@@PACKAGE@@.appdata.xml\n'
        'remove_udev_symlinks\n'
        '\n'
        'ln -sf /opt/chromium.org/thorium/thorium-browser /usr/bin/@@USR_BIN_SYMLINK_NAME@@\n'),
}
SHARED = ("chrome/BUILD.gn", "chrome/common/chrome_constants.cc")   # also renamed for Windows (EXE_EDITS)


def fixture(rel):
    if rel in SHARED:
        return ti.edit_exe_names(rel, EXE_FIXTURES[rel])
    return LINUX_FIXTURES[rel]


def edited():
    return {rel: ti.edit_linux_names(rel, fixture(rel)) for rel in ti.LINUX_EDITS}


class LinuxNameTests(unittest.TestCase):
    def test_every_file_is_covered(self):
        self.assertEqual(set(ti.LINUX_EDITS), set(LINUX_FIXTURES) | set(SHARED))

    def test_program_package_and_desktop_names(self):
        out = edited()
        self.assertIn('_chrome_output_name = "thoron"', out["chrome/BUILD.gn"])
        self.assertIn('binary = "$root_out_dir/thoron"', out["chrome/BUILD.gn"])
        self.assertEqual(out["chrome/common/chrome_constants.cc"].count('FPL("thoron")'), 6)
        info = out[L + "common/chromium-browser.info"]
        for line in ('PACKAGE="thoron-browser"', "PROGNAME=thoron", "INSTALLDIR=/opt/kuchisofts/thoron",
                     'MENUNAME="Thoron"', 'RDN="org.kuchisofts.Thoron"',
                     'BUGTRACKERURL="https://github.com/KuchiSofts/thoron/issues"'):
            self.assertIn(line + "\n", info)
        self.assertIn('package = "thoron-browser"', out[L + "BUILD.gn"])
        self.assertIn('return "thoron-browser";', out["chrome/browser/shell_integration_linux.cc"])
        self.assertIn('return "thoron-browser.desktop";', out["chrome/common/channel_info_posix.cc"])
        self.assertIn('kAppName = "org.kuchisofts.Thoron"', out["base/version_info/nix/version_extra_utils.cc"])
        self.assertIn("StartupWMClass=thoron-browser\n", out[L + "common/desktop.template"])
        self.assertIn('CHROME_DESKTOP="thoron-browser.desktop"', out[L + "common/wrapper"])
        self.assertIn("ln -sf @@INSTALLDIR@@/@@PACKAGE@@ /usr/bin/", out[L + "rpm/thorium.spec.template"])

    def test_own_profile_folder_and_upstream_profile_untouched(self):
        out = edited()
        self.assertIn('data_dir_basename = "thoron"', out["chrome/common/chrome_paths_linux.cc"])
        wrapper = out[L + "common/wrapper"]
        self.assertEqual(wrapper.count('"$XDG_CONFIG_HOME/thoron"'), 2)
        self.assertIn("$XDG_CONFIG_HOME/thoron/thoron-flags.conf", wrapper)
        self.assertIn("$HOME/.config/thoron/Crash Reports", wrapper)   # never cleans Thorium's crash reports
        man = out["chrome/app/resources/manpage.1.in"]
        self.assertIn(".I $HOME/.config/thoron\n", man)
        self.assertIn(".I $HOME/.cache/thoron\n", man)

    def test_coexists_with_upstream_thorium(self):
        out = edited()
        control = out[L + "debian/control.template"]
        self.assertNotIn("thorium", control)          # never conflicts with or replaces a Thorium package
        self.assertIn("Replaces: thoron-browser-unstable\n", control)
        installed = out[L + "rpm/thorium.spec.template"] + out[L + "common/installer.py"]
        self.assertNotIn("/usr/bin/pak", installed)   # upstream installs the same path

    def test_test_shell_and_prebuilt_pak_are_not_packaged(self):
        out = edited()
        for rel in (L + "BUILD.gn", L + "common/installer.py", L + "common/desktop.template",
                    L + "rpm/thorium.spec.template"):
            self.assertNotRegex(out[rel], r"thorium_shell|thorium-shell|content[_-]shell|shell_resources", rel)
        self.assertNotRegex(out[L + "common/installer.py"], r'"pak"|/pak"|\bpak_link\b')
        self.assertNotIn("//content/shell", out[L + "BUILD.gn"])
        self.assertIn("Actions=new-window;new-private-window;temp-profile;safe-mode;dark-mode;\n",
                      out[L + "common/desktop.template"])
        self.assertIn('"//chrome/test/chromedriver:chromedriver_server"', out[L + "BUILD.gn"])
        self.assertIn('install_dir / "chromedriver"', out[L + "common/installer.py"])
        self.assertIn('"thoron.svg"', out[L + "common/installer.py"])

    def test_keyring_entry_is_not_renamed(self):
        # Thorium stores the Linux password key as "Chromium Safe Storage"; keeping it keeps copied passwords
        # readable. No edit may touch os_crypt.
        self.assertFalse([rel for rel in ti.LINUX_EDITS if "os_crypt" in rel])

    def test_credits_kept_and_owner_details_not_added(self):
        out = edited()
        info = out[L + "common/chromium-browser.info"]
        self.assertIn("Copyright 2026 The Chromium Authors and Alex313031", info)
        self.assertIn('DEVELOPER_NAME="The Chromium Authors, Alex313031 and KuchiSofts"', info)
        self.assertIn("Alex313031", re.search(r'SHORTDESC="[^"]*"', info).group(0))
        self.assertIn('MAINTMAIL="KuchiSofts@users.noreply.github.com"', info)
        self.assertNotIn("alex313031@gmail.com", info)
        self.assertIn("Alex313031", out["chrome/app/resources/manpage.1.in"].split(".SH AUTHOR")[1])
        self.assertIn("Copyright 2026 The Chromium Authors and Alex313031", out[L + "common/appdata.xml.template"])

    def test_nothing_installed_is_named_after_thorium(self):
        for rel, text in edited().items():
            if rel.startswith("chrome/installer/linux/common/") or rel.endswith(("control.template", ".info")):
                lines = [l for l in text.splitlines() if "Alex313031" not in l and "on Thorium" not in l]
                self.assertNotRegex("\n".join(lines), r"(?i)thorium(?!_releases|_package|_extras)", rel)

    def test_idempotent(self):
        for rel in ti.LINUX_EDITS:
            once = ti.edit_linux_names(rel, fixture(rel))
            self.assertEqual(ti.edit_linux_names(rel, once), once, rel)

    def test_crlf_files_keep_their_line_endings(self):
        rel = L + "common/installer.py"
        out = ti.edit_linux_names(rel, LINUX_FIXTURES[rel].replace("\n", "\r\n"))
        self.assertNotIn("thorium_shell", out)
        self.assertNotIn("\n", out.replace("\r\n", ""))

    def test_missing_anchor_raises_and_names_the_file(self):
        text = LINUX_FIXTURES["chrome/common/chrome_paths_linux.cc"].replace('"thorium"', '"other"')
        with self.assertRaisesRegex(ti.IdentityError, "chrome_paths_linux.cc"):
            ti.edit_linux_names("chrome/common/chrome_paths_linux.cc", text)

    def test_unexpected_leftover_raises(self):
        rel = L + "common/installer.py"
        with self.assertRaisesRegex(ti.IdentityError, "installer.py"):
            ti.edit_linux_names(rel, LINUX_FIXTURES[rel] + '            "thorium-shell2",\n')


if __name__ == "__main__":
    unittest.main()
