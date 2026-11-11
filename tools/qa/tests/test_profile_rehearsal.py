# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.qa import profile_rehearsal as pr
from tools.qa.tests.test_profile_check import snss, tab_window

SESSION = snss(tab_window(1, 1), tab_window(1, 2))


def make_user_data(root: Path, startup: int = 1) -> Path:
    """A small closed `User Data` folder: 2 bookmarks, 3 passwords, 2 cookies, 1 extension, 2 open tabs.
    It continues where it left off, unless `startup` says otherwise (5: a new tab page)."""
    ud = root / "User Data"
    prof = ud / "Default"
    (prof / "Sessions").mkdir(parents=True)
    (prof / "Network").mkdir()
    (ud / "Local State").write_text(json.dumps(
        {"os_crypt": {"encrypted_key": "a2V5"},
         "profile": {"info_cache": {"Default": {}}, "last_active_profiles": ["Default"]}}), encoding="utf-8")
    write_bookmarks(ud, 2)
    with contextlib.closing(sqlite3.connect(prof / "Login Data")) as db, db:
        db.execute("CREATE TABLE logins (origin_url TEXT, password_value BLOB)")
        db.executemany("INSERT INTO logins VALUES (?, ?)", [("https://a/", b"v10xx")] * 3)
    with contextlib.closing(sqlite3.connect(prof / "Network" / "Cookies")) as db, db:
        db.execute("CREATE TABLE cookies (host_key TEXT, encrypted_value BLOB)")
        db.executemany("INSERT INTO cookies VALUES (?, ?)", [("a", b"v10abc"), ("b", b"v10def")])
    (prof / "Secure Preferences").write_text(json.dumps(
        {"session": {"restore_on_startup": startup},
         "extensions": {"settings": {"aaaa": {"disable_reasons": []}}}}), encoding="utf-8")
    (prof / "Preferences").write_text("{}", encoding="utf-8")
    session = prof / "Sessions" / "Session_100"
    session.write_bytes(SESSION)
    rest(ud)
    os.utime(session, (1_000_000, 1_000_000))
    return ud


def rest(user_data: Path) -> None:
    """As if the browser had been closed an hour ago: nothing in the folder was written since."""
    hour_ago = time.time() - 3600
    for path in user_data.rglob("*"):
        if path.is_file():
            os.utime(path, (hour_ago, hour_ago))


def write_bookmarks(user_data: Path, count: int) -> None:
    (user_data / "Default" / "Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {
        "type": "folder", "children": [{"type": "url", "url": f"https://{i}.example/"} for i in range(count)]}}}),
        encoding="utf-8")


def new_session(copy: Path) -> None:
    """What a browser with a window does on the copy: it writes a newer session with the same tabs."""
    (copy / "Default" / "Sessions" / "Session_200").write_bytes(SESSION)


def fingerprint(folder: Path) -> dict:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thoron-test-"))
        self.ud = make_user_data(self.tmp / "install")
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.browser = self.tmp / "thoron.exe"
        self.browser.write_bytes(b"")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class ArgumentsTests(unittest.TestCase):
    def test_the_copy_is_opened_fully_offline(self):
        args = pr.launch_arguments(Path("out") / "thoron.exe", Path("work") / "User Data")
        self.assertEqual(args[0], str(Path("out") / "thoron.exe"))
        self.assertIn(f"--user-data-dir={Path('work') / 'User Data'}", args)
        for flag in ("--disable-sync", "--disable-background-networking", "--disable-component-update",
                     "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
                     "--host-resolver-rules=MAP * ~NOTFOUND",
                     "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                     "--no-first-run", "--no-default-browser-check"):
            self.assertIn(flag, args)

    def test_devtools_listens_on_this_machine_only(self):
        args = pr.launch_arguments(Path("thoron.exe"), Path("copy"))
        self.assertIn("--remote-debugging-address=127.0.0.1", args)
        self.assertIn("--remote-debugging-port=0", args)

    def test_a_window_unless_asked_otherwise(self):
        self.assertFalse([a for a in pr.launch_arguments(Path("b"), Path("c")) if a.startswith("--headless")])
        self.assertIn("--headless=new", pr.launch_arguments(Path("b"), Path("c"), headless=True))


class RefusalTests(Scratch):
    def test_a_closed_profile_and_a_plain_work_folder_are_accepted(self):
        self.assertIsNone(pr.refusal(self.browser, self.ud, self.work))

    def test_a_missing_browser(self):
        self.assertIn("no browser", pr.refusal(self.tmp / "nothing.exe", self.ud, self.work))

    def test_a_folder_that_is_not_user_data(self):
        self.assertIn("Local State", pr.refusal(self.browser, self.ud / "Default", self.work))

    def test_a_running_browser_is_never_copied(self):
        (self.ud / "lockfile").write_bytes(b"")
        self.assertIn("running", pr.refusal(self.browser, self.ud, self.work))

    def test_a_profile_that_was_written_a_moment_ago_is_not_copied_yet(self):
        write_bookmarks(self.ud, 2)                    # its browser may still be closing
        why = pr.refusal(self.browser, self.ud, self.work)
        self.assertIn("still", why)
        self.assertIn("Bookmarks", why)
        rest(self.ud)
        self.assertIsNone(pr.refusal(self.browser, self.ud, self.work))

    def test_a_file_dated_in_the_future_does_not_block_for_ever(self):
        future = time.time() + 86400
        os.utime(self.ud / "Default" / "Bookmarks", (future, future))
        self.assertIsNone(pr.refusal(self.browser, self.ud, self.work))

    def test_a_work_folder_inside_the_profile(self):
        inside = self.ud / "work"
        inside.mkdir()
        self.assertIn("inside", pr.refusal(self.browser, self.ud, inside))
        self.assertIn("inside", pr.refusal(self.browser, self.ud, self.ud))

    def test_a_work_folder_in_a_repository(self):
        (self.tmp / ".git").mkdir()
        self.assertIn("repository", pr.refusal(self.browser, self.ud, self.work))

    def test_a_work_folder_that_looks_cloud_synced(self):
        for name in ("Google Drive", "OneDrive - Work", "Dropbox", "My Drive", "iCloudDrive"):
            synced = self.tmp / name / "work"
            synced.mkdir(parents=True)
            self.assertIn("cloud", pr.refusal(self.browser, self.ud, synced), name)

    def test_too_little_room_for_the_copy(self):
        with mock.patch.object(pr.shutil, "disk_usage", return_value=mock.Mock(free=10)):
            self.assertIn("room", pr.refusal(self.browser, self.ud, self.work))


class RunTests(Scratch):
    class Process:
        def __init__(self, ended=None, closes_when_asked=True):
            self.pid, self.returncode, self.closes_when_asked = 4242, ended, closes_when_asked
            self.asked = self.stopped = False

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            if self.returncode is None:
                if not (self.asked and self.closes_when_asked):
                    raise subprocess.TimeoutExpired("thoron", timeout)
                self.returncode = 0
            return self.returncode

    def run_with(self, proc, port_of=lambda copy, proc, timeout: 9222, **more):
        self.started = []

        def start(args):
            self.started.append(args)
            return proc

        def ask(port):
            self.asked_port = port
            proc.asked = True

        def stop(p):
            p.stopped = True

        return pr.run(self.browser, self.ud, 60, start=start, port_of=port_of, ask_to_close=ask,
                      sleep=lambda s: None, stop=stop, **more)

    def test_runs_and_closes_when_asked(self):
        proc = self.Process()
        self.assertIsNone(self.run_with(proc))
        self.assertEqual(self.started, [pr.launch_arguments(self.browser, self.ud)])
        self.assertEqual(self.asked_port, 9222)
        self.assertFalse(proc.stopped)

    def test_a_stale_devtools_port_is_removed_first(self):
        (self.ud / "DevToolsActivePort").write_text("1\n", encoding="utf-8")
        self.run_with(self.Process())
        self.assertFalse((self.ud / "DevToolsActivePort").exists())

    def test_a_browser_that_does_not_start(self):
        def no_port(copy, proc, timeout):
            raise RuntimeError("DevTools did not start")

        proc = self.Process()
        self.assertIn("did not start", self.run_with(proc, port_of=no_port))
        self.assertTrue(proc.stopped)

    def test_a_browser_that_ends_by_itself(self):
        problem = self.run_with(self.Process(ended=3))
        self.assertIn("ended by itself", problem)
        self.assertIn("3", problem)

    def test_a_browser_that_does_not_close_is_a_failure_not_a_pass(self):
        proc = self.Process(closes_when_asked=False)
        problem = self.run_with(proc, close_timeout=5)
        self.assertIn("did not close", problem)
        self.assertTrue(proc.stopped)                      # a copy may be stopped by force, but it does not count

    def test_a_browser_that_cannot_be_asked(self):
        proc = self.Process()

        def broken(port):
            raise OSError("refused")

        problem = pr.run(self.browser, self.ud, 60, start=lambda args: proc, port_of=lambda c, p, t: 1,
                         ask_to_close=broken, sleep=lambda s: None, stop=lambda p: setattr(p, "stopped", True))
        self.assertIn("could not be asked", problem)
        self.assertTrue(proc.stopped)


class RehearseTests(Scratch):
    def rehearse(self, runner, **more):
        return pr.rehearse(self.browser, self.ud, self.work, runner=runner, **more)

    def test_a_build_that_keeps_everything(self):
        source = fingerprint(self.ud)
        seen = []

        def runner(browser, copy, seconds, headless, close_timeout):
            seen.append((browser, copy, seconds, headless))
            self.assertNotEqual(copy.resolve(), self.ud.resolve())
            self.assertEqual(fingerprint(copy), source)         # a complete copy
            new_session(copy)

        result = self.rehearse(runner, seconds=7)
        self.assertEqual(result.problems, [])
        self.assertEqual(seen[0][0], self.browser)
        self.assertEqual(seen[0][2:], (7, False))
        self.assertEqual(self.work.resolve() in seen[0][1].resolve().parents, True)
        self.assertEqual(list(self.work.iterdir()), [])         # the copy is gone
        self.assertEqual(fingerprint(self.ud), source)          # the real folder was only read
        self.assertEqual(result.before["profiles"]["Default"]["bookmarks"], 2)
        self.assertEqual(result.after["profiles"]["Default"]["passwords"], 3)

    def test_a_loss_is_reported_and_the_copy_still_deleted(self):
        def runner(browser, copy, seconds, headless, close_timeout):
            new_session(copy)
            write_bookmarks(copy, 1)

        result = self.rehearse(runner)
        self.assertEqual(result.problems, ["Default: bookmarks 2 -> 1"])
        self.assertEqual(list(self.work.iterdir()), [])

    def test_a_browser_problem_is_reported_and_nothing_compared(self):
        result = self.rehearse(lambda *a: "the new build did not close")
        self.assertEqual(result.problems, ["the new build did not close"])
        self.assertIsNone(result.after)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_the_copy_is_deleted_even_when_the_run_breaks(self):
        def runner(*a):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            self.rehearse(runner)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_a_window_that_restores_nothing_is_a_problem(self):
        result = self.rehearse(lambda *a: None)                # no newer session was written
        self.assertEqual(len(result.problems), 1)
        self.assertIn("did not write a session", result.problems[0])

    def test_a_profile_that_starts_with_a_new_tab_page_is_not_a_false_alarm(self):
        shutil.rmtree(self.ud.parent)
        self.ud = make_user_data(self.tmp / "install", startup=5)

        def runner(browser, copy, seconds, headless, close_timeout):
            (copy / "Default" / "Sessions" / "Session_200").write_bytes(snss(tab_window(1, 1)))   # one new tab

        result = self.rehearse(runner)
        self.assertEqual(result.problems, [])
        self.assertTrue(any("Default" in n and "not compared" in n for n in result.notes))

    def test_without_a_window_tabs_are_said_to_be_unchecked(self):
        result = self.rehearse(lambda *a: None, headless=True)
        self.assertEqual(result.problems, [])
        self.assertTrue(any("tabs" in n and "not checked" in n for n in result.notes))

    def test_a_profile_that_cannot_be_copied_completely_is_a_problem_not_a_crash(self):
        started = []
        failed = shutil.Error([(str(self.ud / "Default" / "Cookies"), "x", "in use"), ("y", "z", "in use")])
        with mock.patch.object(pr.shutil, "copytree", side_effect=failed):
            result = self.rehearse(lambda *a: started.append(a))
        self.assertEqual(started, [])                           # no browser on half a copy
        self.assertEqual(len(result.problems), 1)
        self.assertIn("2 file(s) could not be copied", result.problems[0])
        self.assertIn("in use", result.problems[0])
        self.assertEqual(list(self.work.iterdir()), [])

    def test_paths_longer_than_260_characters_are_copied_counted_and_deleted(self):
        deep = self.ud / "Default" / ("d" * 120) / ("e" * 120)
        os.makedirs(pr.long_path(deep))
        with open(pr.long_path(deep / "data.bin"), "wb") as f:
            f.write(b"x" * 5000)
        os.utime(pr.long_path(deep / "data.bin"), (time.time() - 3600,) * 2)
        self.assertGreater(len(str(deep)), 260)
        self.assertGreaterEqual(pr._size(self.ud), 5000)
        seen = []

        def runner(browser, copy, seconds, headless, close_timeout):
            new_session(copy)
            with open(pr.long_path(copy / deep.relative_to(self.ud) / "data.bin"), "rb") as f:
                seen.append(len(f.read()))

        result = self.rehearse(runner)
        self.assertEqual((result.problems, seen), ([], [5000]))
        self.assertEqual(list(self.work.iterdir()), [])
        shutil.rmtree(pr.long_path(self.ud / "Default" / ("d" * 120)))    # so that tearDown can delete the rest

    def test_without_a_window_every_other_loss_still_counts(self):
        result = self.rehearse(lambda browser, copy, *a: write_bookmarks(copy, 1), headless=True)
        self.assertEqual(result.problems, ["Default: bookmarks 2 -> 1"])

    def test_a_copy_that_cannot_be_deleted_is_a_problem_that_names_it(self):
        def runner(browser, copy, seconds, headless, close_timeout):
            new_session(copy)
            self.copy = copy

        with mock.patch.object(pr.shutil, "rmtree", side_effect=OSError("in use")), \
                mock.patch.object(pr.time, "sleep"):
            result = self.rehearse(runner)
        self.assertEqual(len(result.problems), 1)
        self.assertIn("delete it yourself", result.problems[0])
        self.assertIn(str(self.copy.parent), result.problems[0])

    def test_a_copy_still_locked_after_the_run_is_a_problem(self):
        def runner(browser, copy, seconds, headless, close_timeout):
            new_session(copy)
            (copy / "lockfile").write_bytes(b"")

        with mock.patch.object(pr.time, "sleep"):
            result = self.rehearse(runner)
        self.assertEqual(len(result.problems), 1)
        self.assertIn("running", result.problems[0])
        self.assertEqual(list(self.work.iterdir()), [])


class MainTests(Scratch):
    def main(self, *more, runner=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(pr, "run", runner or self.keeps):
            code = pr.main(["--browser", str(self.browser), "--user-data", str(self.ud),
                            "--work", str(self.work), *more])
        return code, out.getvalue()

    @staticmethod
    def keeps(browser, copy, seconds, headless, close_timeout):
        new_session(copy)

    def test_kept_everything(self):
        code, text = self.main()
        self.assertEqual(code, 0)
        self.assertIn("2 bookmarks, 3 passwords", text)
        self.assertIn("kept everything", text)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_the_snapshot_from_before_can_be_kept(self):
        before = self.tmp / "before.json"
        code, _ = self.main("--before-out", str(before))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(before.read_text(encoding="utf-8"))["profiles"]["Default"]["passwords"], 3)

    def test_a_loss_gives_exit_status_1(self):
        def loses(browser, copy, seconds, headless, close_timeout):
            new_session(copy)
            write_bookmarks(copy, 0)

        code, text = self.main(runner=loses)
        self.assertEqual(code, 1)
        self.assertIn("bookmarks 2 -> 0", text)
        self.assertIn("Do not install", text)

    def test_a_refusal_gives_exit_status_2_and_copies_nothing(self):
        (self.ud / "lockfile").write_bytes(b"")
        code, text = self.main()
        self.assertEqual(code, 2)
        self.assertIn("refused", text)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_output_holds_no_address_and_no_secret(self):
        _, text = self.main()
        self.assertNotIn("example", text)
        self.assertNotIn("a2V5", text)


if __name__ == "__main__":
    unittest.main()
