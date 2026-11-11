# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
import json
import shutil
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.qa import profile_check as pc

G1 = (0x1111, 0x2222)
G2 = (0x3333, 0x4444)


def rec(cmd: int, payload: bytes) -> bytes:
    return struct.pack("<HB", len(payload) + 1, cmd) + payload


def snss(*records: bytes, version: int = 3) -> bytes:
    return b"SNSS" + struct.pack("<i", version) + b"".join(records)


def tab_window(window: int, tab: int) -> bytes:
    return rec(0, struct.pack("<ii", window, tab))


def tab_closed(tab: int) -> bytes:
    return rec(16, struct.pack("<i4xq", tab, 0))


def window_closed(window: int) -> bytes:
    return rec(17, struct.pack("<i4xq", window, 0))


def pinned(tab: int, state: bool = True) -> bytes:
    return rec(12, struct.pack("<i?3x", tab, state))


def tab_group(tab: int, token=None) -> bytes:
    hi, lo = token or (0, 0)
    return rec(25, struct.pack("<i4xQQ?7x", tab, hi, lo, token is not None))


def group_meta(token, title: str, color: int) -> bytes:
    text = title.encode("utf-16-le")
    body = struct.pack("<QQ", *token) + struct.pack("<i", len(title)) + text + b"\0" * (-len(text) % 4)
    body += struct.pack("<Iii", color, 0, 0)          # color, collapsed, has saved guid
    return rec(27, struct.pack("<I", len(body)) + body)


SESSION = snss(
    tab_window(1, 10), tab_window(1, 11), tab_window(1, 12), tab_window(2, 20),
    group_meta(G1, "Shopping", 3), tab_group(10, G1), tab_group(11, G1),
    group_meta(G2, "Videos", 5), tab_group(20, G2),
    pinned(10), tab_closed(12))


class SessionTests(unittest.TestCase):
    def test_counts_live_windows_tabs_pins_and_groups(self):
        s = pc.session_summary(SESSION)
        self.assertEqual((s["windows"], s["tabs"], s["pinned"]), (2, 3, 1))
        self.assertEqual(s["groups"], [{"title": "Shopping", "color": 3, "tabs": 2},
                                       {"title": "Videos", "color": 5, "tabs": 1}])

    def test_closed_window_takes_its_tabs(self):
        s = pc.session_summary(snss(tab_window(1, 10), tab_window(2, 20), window_closed(2)))
        self.assertEqual((s["windows"], s["tabs"]), (1, 1))

    def test_tab_leaving_a_group(self):
        s = pc.session_summary(snss(tab_window(1, 10), group_meta(G1, "A", 1), tab_group(10, G1), tab_group(10)))
        self.assertEqual(s["groups"], [])

    def test_encrypted_or_foreign_files_are_reported_not_parsed(self):
        self.assertEqual(pc.session_summary(snss(tab_window(1, 1), version=5)), {"encrypted": True})
        self.assertEqual(pc.session_summary(b"not a session"), {"unreadable": True})


class ProfileTests(unittest.TestCase):
    SECRET_KEY = "c2VjcmV0LWtleS12YWx1ZQ=="

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.ud = self.tmp / "User Data"
        prof = self.ud / "Default"
        (prof / "Sessions").mkdir(parents=True)
        (prof / "Network").mkdir()
        (self.ud / "Local State").write_text(json.dumps(
            {"os_crypt": {"encrypted_key": self.SECRET_KEY},
             "profile": {"info_cache": {"Default": {"name": "Person 1"}}}}), encoding="utf-8")
        (prof / "Bookmarks").write_text(json.dumps({"roots": {
            "bookmark_bar": {"type": "folder", "children": [
                {"type": "url", "url": "https://a.example/"},
                {"type": "folder", "children": [{"type": "url", "url": "https://b.example/"}]}]},
            "other": {"type": "folder", "children": [{"type": "url", "url": "https://c.example/"}]}}}),
            encoding="utf-8")
        with sqlite3.connect(prof / "Login Data") as db:
            db.execute("CREATE TABLE logins (origin_url TEXT, password_value BLOB)")
            db.executemany("INSERT INTO logins VALUES (?, ?)", [("https://a/", b"v10xx")] * 3)
        with sqlite3.connect(prof / "Network" / "Cookies") as db:
            db.execute("CREATE TABLE cookies (host_key TEXT, encrypted_value BLOB)")
            db.executemany("INSERT INTO cookies VALUES (?, ?)", [("a", b"v10abc"), ("b", b"v10def"), ("c", b"")])
            db.execute("INSERT INTO cookies VALUES ('d', 'plain')")  # real profiles hold some as TEXT
        (prof / "Secure Preferences").write_text(json.dumps({"session": {"restore_on_startup": 1}, "extensions": {
            "settings": {"aaaa": {"disable_reasons": []}, "bbbb": {"disable_reasons": [1]}}}}), encoding="utf-8")
        (prof / "Preferences").write_text(json.dumps({"extensions": {"settings": {"cccc": {}}}}), encoding="utf-8")
        (prof / "Sessions" / "Session_100").write_bytes(snss(tab_window(1, 1)))
        (prof / "Sessions" / "Session_200").write_bytes(SESSION)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_counts_without_secrets(self):
        snap = pc.snapshot(self.ud)
        p = snap["profiles"]["Default"]
        self.assertEqual(p["bookmarks"], 3)
        self.assertEqual(p["passwords"], 3)
        self.assertEqual(p["cookies"], {"total": 4, "v10": 2, "empty": 1, "other": 1})
        self.assertEqual(p["extensions_enabled"], ["aaaa", "cccc"])
        self.assertEqual(p["session"]["tabs"], 3)                 # the newest Session_ file
        self.assertEqual(snap["os_crypt"], {"dpapi_key": True, "app_bound_key": False})
        text = json.dumps(snap)
        self.assertNotIn(self.SECRET_KEY, text)
        self.assertNotIn("a.example", text)

    def test_compare_identical_is_clean(self):
        snap = pc.snapshot(self.ud)
        self.assertEqual(pc.compare(snap, json.loads(json.dumps(snap))), [])

    def test_compare_flags_every_kind_of_loss(self):
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        p = after["profiles"]["Default"]
        p["passwords"] = 2
        p["bookmarks"] = 2
        p["extensions_enabled"] = ["aaaa"]
        p["session"]["groups"] = p["session"]["groups"][:1]
        p["cookies"] = {"total": 1, "v20": 1}
        after["os_crypt"]["app_bound_key"] = True
        problems = "\n".join(pc.compare(before, after))
        for word in ("passwords", "bookmarks", "cccc", "Videos", "cookies", "app-bound"):
            self.assertIn(word, problems)

    def set_startup(self, value, where="Secure Preferences"):
        path = self.ud / "Default" / where
        prefs = json.loads(path.read_text(encoding="utf-8"))
        prefs.pop("session", None)
        if value is not None:
            prefs["session"] = {"restore_on_startup": value}
        path.write_text(json.dumps(prefs), encoding="utf-8")

    def restores(self):
        return pc.snapshot(self.ud)["profiles"]["Default"]["restores_session"]

    def test_snapshot_records_whether_the_profile_continues_where_it_left_off(self):
        self.assertIs(self.restores(), True)                     # 1: the last session
        for value, expected in ((6, True), (5, False), (4, False), (None, False)):
            self.set_startup(value)
            self.assertIs(self.restores(), expected, value)
        self.set_startup(1, where="Preferences")                 # where other systems keep it
        self.assertIs(self.restores(), True)
        self.set_startup(5)                                      # the protected file wins
        self.assertIs(self.restores(), False)
        (self.ud / "Default" / "Preferences").write_text("not json", encoding="utf-8")
        self.assertIsNone(self.restores())

    def test_tabs_are_not_compared_when_a_start_opens_a_new_tab_page(self):
        self.set_startup(5)
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        after["profiles"]["Default"]["session"] = {"windows": 1, "tabs": 1, "pinned": 0, "groups": []}
        self.assertEqual(pc.compare(before, after), [])
        notes = pc.notes(before)
        self.assertEqual(len(notes), 1)
        self.assertIn("Default", notes[0])
        self.assertIn("not compared", notes[0])
        after["profiles"]["Default"]["bookmarks"] = 0             # every other loss still counts
        self.assertEqual(pc.compare(before, after), ["Default: bookmarks 3 -> 0"])

    def test_tabs_are_compared_when_the_profile_continues_where_it_left_off(self):
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        after["profiles"]["Default"]["session"] = {"windows": 1, "tabs": 1, "pinned": 0, "groups": []}
        self.assertTrue(any("open tabs 3 -> 1" in line for line in pc.compare(before, after)))
        self.assertEqual(pc.notes(before), [])

    def test_a_snapshot_from_an_older_tool_compares_tabs_as_before(self):
        before = pc.snapshot(self.ud)
        del before["profiles"]["Default"]["restores_session"]
        after = json.loads(json.dumps(before))
        after["profiles"]["Default"]["session"] = {"windows": 1, "tabs": 1, "pinned": 0, "groups": []}
        self.assertTrue(any("open tabs 3 -> 1" in line for line in pc.compare(before, after)))
        self.assertEqual(pc.notes(before), [])

    def test_missing_profile_is_a_problem(self):
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        after["profiles"] = {}
        self.assertTrue(any("Default" in p for p in pc.compare(before, after)))

    def test_snapshot_refuses_a_folder_that_is_not_user_data(self):
        with self.assertRaises(pc.SnapshotError):
            pc.snapshot(self.tmp)                                 # the parent folder, not "User Data"
        (self.ud / "Local State").write_text("{}", encoding="utf-8")
        with self.assertRaises(pc.SnapshotError):
            pc.snapshot(self.ud)                                  # no profile listed

    def test_snapshot_refuses_a_running_browser(self):
        (self.ud / "lockfile").write_bytes(b"")
        with self.assertRaises(pc.SnapshotError) as ctx:
            pc.snapshot(self.ud)
        self.assertIn("running", str(ctx.exception))

    def test_unreadable_database_is_recorded_not_counted_as_zero(self):
        before = pc.snapshot(self.ud)
        (self.ud / "Default" / "Login Data").write_bytes(b"this is not a database")
        after = pc.snapshot(self.ud)
        self.assertIsNone(after["profiles"]["Default"]["passwords"])
        self.assertTrue(any("passwords" in p and "unreadable" in p for p in pc.compare(before, after)))
        self.assertTrue(pc.compare(after, before))                # unreadable before hides losses: a problem too

    def test_unreadable_session_before_is_a_problem(self):
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        before["profiles"]["Default"]["session"] = {"unreadable": True}
        self.assertTrue(any("session" in p for p in pc.compare(before, after)))

    def test_duplicate_groups_are_counted(self):
        before = pc.snapshot(self.ud)
        after = json.loads(json.dumps(before))
        g = before["profiles"]["Default"]["session"]["groups"][0]
        before["profiles"]["Default"]["session"]["groups"].append(dict(g))   # two identical groups
        self.assertTrue(any(g["title"] in p for p in pc.compare(before, after)))

    def test_stale_session_of_an_active_profile_is_a_problem(self):
        before = pc.snapshot(self.ud)
        same = json.loads(json.dumps(before))
        before["last_active_profiles"] = ["Default"]
        problems = pc.compare(before, same)
        self.assertTrue(any("did not write" in p for p in problems), problems)
        before["last_active_profiles"] = []
        self.assertEqual(pc.compare(before, same), [])

    def test_cli_snapshot_and_compare(self):
        out1, out2 = self.tmp / "before.json", self.tmp / "after.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pc.main(["snapshot", str(self.ud), "--out", str(out1)]), 0)
            self.assertEqual(pc.main(["snapshot", str(self.ud), "--out", str(out2)]), 0)
            self.assertEqual(pc.main(["compare", str(out1), str(out2)]), 0)
        data = json.loads(out2.read_text(encoding="utf-8"))
        data["profiles"]["Default"]["passwords"] = 0
        out2.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pc.main(["compare", str(out1), str(out2)]), 1)


if __name__ == "__main__":
    unittest.main()
