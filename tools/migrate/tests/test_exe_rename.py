# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tools.migrate import exe_rename as er

APP_PATHS_KEY = er.APP_PATHS + "\\thorium.exe"


class FakeBackend:
    """In-memory registry and shortcuts, the same interface as the real Windows backend."""

    def __init__(self):
        self.keys = {}          # key -> {name: (value, type)}
        self.links = {}         # path -> {"target", "arguments", "working_dir", "icon"}
        self.running = []

    def processes(self):
        return list(self.running)

    def read_values(self, roots):
        out = []
        for key, values in self.keys.items():
            if any(key.lower() == r.lower() or key.lower().startswith(r.lower() + "\\") for r in roots):
                out += [(key, name, v, t) for name, (v, t) in values.items()]
        return out

    def read_key(self, key):
        return dict(self.keys[key]) if key in self.keys else None

    def set_value(self, key, name, value, kind):
        self.keys.setdefault(key, {})[name] = (value, kind)

    def write_key(self, key, values):
        self.keys[key] = dict(values)

    def delete_key(self, key):
        self.keys.pop(key, None)

    def shortcuts(self, dirs):
        return [dict(path=p, **v) for p, v in self.links.items()
                if any(str(Path(p)).lower().startswith(str(Path(d)).lower()) for d in dirs)]

    def set_shortcut(self, path, target, working_dir, icon):
        self.links[path].update(target=target, working_dir=working_dir, icon=icon)


class ExeRenameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.thoron = self.tmp / "Local" / "Thoron" / "Application"
        self.thorium = self.tmp / "Local" / "Thorium" / "Application"
        for d in (self.thoron / "156.0.8078.28", self.thorium):
            d.mkdir(parents=True)
        for name in ("thorium.exe", "thoron.exe", "thor_ver", "156.0.8078.28/thorium.ico",
                     "156.0.8078.28/thorium.svg", "156.0.8078.28/thorium_shell.ico", "156.0.8078.28/chrome.dll"):
            (self.thoron / name).write_bytes(b"x" + name.encode())
        (self.thorium / "thorium.exe").write_bytes(b"thorium itself")
        self.old = str(self.thoron / "thorium.exe")
        self.new = str(self.thoron / "thoron.exe")
        self.links_dir = self.tmp / "Pins"
        self.b = FakeBackend()
        self.b.keys = {
            APP_PATHS_KEY: {"": (self.old, 1), "Path": (str(self.thoron), 1)},
            er.APP_PATHS + "\\thoron.exe": {"": (self.new, 1), "Path": (str(self.thoron), 1)},
            r"Software\Classes\ThoronHTM.X\shell\open\command": {"": (f'"{self.old}" --single-argument %1', 1)},
            r"Software\Classes\ThoronHTM.X\DefaultIcon": {"": (self.old.upper() + ",0", 1)},
            r"Software\Classes\ThoriumHTM\shell\open\command": {"": (f'"{self.thorium / "thorium.exe"}" %1', 1)},
            r"Software\Classes\Other": {"": ("unrelated", 1)},
        }
        self.b.links = {
            str(self.links_dir / "TaskBar" / "Thoron.lnk"): dict(target=self.old, arguments="", working_dir=str(self.thoron),
                                                                 icon=self.old + ",0"),
            str(self.links_dir / "TaskBar" / "Thorium.lnk"): dict(target=str(self.thorium / "thorium.exe"), arguments="",
                                                                  working_dir=str(self.thorium), icon=""),
            str(self.links_dir / "Work.lnk"): dict(target=self.old, arguments="--profile-directory=\"Profile 1\"",
                                                   working_dir="", icon=""),
        }
        self.backup = self.tmp / "Backups" / "exe-rename"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self):
        return er.plan(self.thoron, self.thorium, self.b, [self.links_dir])

    def test_plan_lists_every_change_and_nothing_of_thorium(self):
        p = self.plan()
        self.assertEqual(sorted(Path(s["path"]).name for s in p["shortcuts"]), ["Thoron.lnk", "Work.lnk"])
        self.assertTrue(all(s["new"]["target"] == self.new for s in p["shortcuts"]))
        keys = sorted(v["key"] for v in p["values"])
        self.assertEqual(keys, [r"Software\Classes\ThoronHTM.X\DefaultIcon", r"Software\Classes\ThoronHTM.X\shell\open\command"])
        self.assertEqual(p["app_paths"]["action"], "restore")
        self.assertEqual(p["app_paths"]["new"][""][0], str(self.thorium / "thorium.exe"))
        names = sorted(Path(f).name for f in p["files"])
        self.assertEqual(names, ["thor_ver", "thorium.exe", "thorium.ico", "thorium.svg", "thorium_shell.ico"])
        self.assertFalse([f for f in p["files"] if "Thorium" in Path(f).parts])

    def test_value_rewrite_keeps_arguments_and_is_case_insensitive(self):
        p = self.plan()
        by_key = {v["key"]: v["new"] for v in p["values"]}
        self.assertEqual(by_key[r"Software\Classes\ThoronHTM.X\shell\open\command"], f'"{self.new}" --single-argument %1')
        self.assertEqual(by_key[r"Software\Classes\ThoronHTM.X\DefaultIcon"], self.new + ",0")

    def test_apply_then_restore_is_exact(self):
        keys_before = json.loads(json.dumps(self.b.keys))
        links_before = json.loads(json.dumps(self.b.links))
        files_before = {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}
        er.apply(self.plan(), self.b, self.backup)
        self.assertEqual(self.b.keys[APP_PATHS_KEY][""][0], str(self.thorium / "thorium.exe"))
        self.assertEqual(self.b.keys[APP_PATHS_KEY]["Path"][0], str(self.thorium))
        self.assertEqual(self.b.links[str(self.links_dir / "Work.lnk")]["target"], self.new)
        self.assertEqual(self.b.links[str(self.links_dir / "Work.lnk")]["arguments"], "--profile-directory=\"Profile 1\"")
        self.assertFalse((self.thoron / "thorium.exe").exists())
        self.assertTrue((self.thorium / "thorium.exe").exists())                   # Thorium untouched
        self.assertTrue((self.thoron / "thoron.exe").exists())
        self.assertEqual(self.b.keys[r"Software\Classes\ThoriumHTM\shell\open\command"],
                         {"": (f'"{self.thorium / "thorium.exe"}" %1', 1)})
        er.restore(self.backup, self.b)
        self.assertEqual(json.loads(json.dumps(self.b.keys)), keys_before)
        self.assertEqual(json.loads(json.dumps(self.b.links)), links_before)
        files_after = {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file() and self.backup not in p.parents}
        self.assertEqual(files_after, files_before)

    def test_app_paths_removed_when_thorium_is_not_installed(self):
        (self.thorium / "thorium.exe").unlink()
        p = self.plan()
        self.assertEqual(p["app_paths"]["action"], "delete")
        er.apply(p, self.b, self.backup)
        self.assertNotIn(APP_PATHS_KEY, self.b.keys)
        er.restore(self.backup, self.b)
        self.assertEqual(self.b.keys[APP_PATHS_KEY][""][0], self.old)

    def test_app_paths_that_already_belong_to_thorium_are_kept(self):
        self.b.keys[APP_PATHS_KEY] = {"": (str(self.thorium / "thorium.exe"), 1), "Path": (str(self.thorium), 1)}
        self.assertEqual(self.plan()["app_paths"]["action"], "keep")

    def test_refused_while_thoron_runs(self):
        self.b.running = [self.old.upper()]
        with self.assertRaisesRegex(er.MigrationRefused, "running"):
            self.plan()
        self.b.running = [str(self.thorium / "thorium.exe")]                       # Thorium may run
        self.plan()

    def test_refused_before_the_new_build_is_installed(self):
        (self.thoron / "thoron.exe").unlink()
        with self.assertRaisesRegex(er.MigrationRefused, "thoron.exe"):
            self.plan()

    def test_refused_for_a_folder_that_is_not_thorons(self):
        with self.assertRaises(er.MigrationRefused):
            er.plan(self.thorium, self.thorium, self.b, [self.links_dir])

    def test_backup_must_be_new_and_not_in_a_cloud_or_repo_folder(self):
        p = self.plan()
        self.backup.mkdir(parents=True)
        with self.assertRaises(er.MigrationRefused):
            er.apply(p, self.b, self.backup)
        for bad in (self.tmp / "Google Drive" / "b", self.tmp / "OneDrive" / "b",
                    Path(er.__file__).resolve().parents[2] / "backup-here"):
            with self.assertRaises(er.MigrationRefused, msg=str(bad)):
                er.apply(p, self.b, bad)
        self.assertTrue((self.thoron / "thorium.exe").exists())                    # nothing changed

    def test_second_run_finds_nothing_to_do(self):
        er.apply(self.plan(), self.b, self.backup)
        p = self.plan()
        self.assertEqual((p["shortcuts"], p["values"], p["files"], p["app_paths"]["action"]), ([], [], [], "keep"))


@unittest.skipUnless(sys.platform == "win32", "Windows shortcuts")
class WindowsShortcutTests(unittest.TestCase):
    def test_read_and_retarget_a_real_shortcut(self):
        tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        try:
            link = tmp / "Test.lnk"
            backend = er.WindowsBackend()
            backend.create_shortcut_for_test(str(link), r"C:\Old\thorium.exe", "--x \"a b\"", r"C:\Old")
            found = backend.shortcuts([str(tmp)])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["target"].lower(), r"c:\old\thorium.exe")
            self.assertEqual(found[0]["arguments"], "--x \"a b\"")
            backend.set_shortcut(str(link), r"C:\Old\thoron.exe", r"C:\Old", r"C:\Old\thoron.exe,0")
            again = backend.shortcuts([str(tmp)])[0]
            self.assertEqual(again["target"].lower(), r"c:\old\thoron.exe")
            self.assertEqual(again["arguments"], "--x \"a b\"")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
