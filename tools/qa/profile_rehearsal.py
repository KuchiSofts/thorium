#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Rehearsal of a browser update on a copy of the profile (ROADMAP Q.7; docs/build/WINDOWS.md, "Upgrading").

A profile that a newer version has opened cannot be opened by an older one. So before a new build is
installed over a browser someone uses, this tries the new build on a COPY of that browser's `User Data`
folder:

  1. it copies the folder (its browser must be closed) to a new folder under --work;
  2. it takes a snapshot of the copy (`profile_check.py`: counts only, nothing is decrypted);
  3. it opens the copy with the new build, fully offline, so the copy can neither sync nor make a
     website rotate a login cookie (which could sign out the real browser); the build runs for a while,
     so it migrates what it migrates, and is then asked to close the way a person closes it;
  4. it takes a second snapshot and compares: open tabs, tab groups, bookmarks, saved passwords,
     cookies and enabled extensions must all still be there;
  5. it deletes the copy, whatever happened: the copy holds cookies and saved passwords.

The real folder is only read. The new build never sees it: it only ever gets the copy made here.

    py -3 -I tools/qa/profile_rehearsal.py --browser <out>\\thoron.exe \\
        --user-data "%LOCALAPPDATA%\\Thoron\\User Data" --work D:\\scratch [--before-out before.json]

Tabs and tab groups are checked only with a window (the default) and when the browser is set to
continue where it left off; with --headless they are not checked, and the tool says so. A build that
does not close when asked is stopped by force and does not count as a pass.

It refuses to start while the browser of that profile is running, when --work is inside the profile,
inside a git repository or in a folder that looks cloud-synced (judged by its name: a best effort, the
choice of a private local folder stays yours), or when the drive has too little room for the copy.

Exit status: 0 the new build kept everything, 1 it did not (or did not run cleanly), 2 refused.
"""
import argparse
import dataclasses
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import profile_check  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

# docs/build/WINDOWS.md, "Upgrading": nothing leaves the machine, nothing but 127.0.0.1 resolves.
OFFLINE = ("--no-first-run", "--no-default-browser-check", "--disable-sync", "--disable-background-networking",
           "--disable-component-update", "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
           "--host-resolver-rules=MAP * ~NOTFOUND", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
START_TIMEOUT = 120    # seconds until the build must answer on its DevTools port
CLOSE_TIMEOUT = 180    # seconds a build with a large profile may take to close
CLOUD_NAMES = ("google drive", "googledrive", "my drive", "onedrive", "dropbox", "icloud")
TABS_NOT_CHECKED = "tabs and tab groups were not checked: a browser without a window does not restore them"


class Refused(Exception):
    """Nothing was copied and nothing was started."""


@dataclasses.dataclass
class Result:
    problems: list
    notes: list
    before: dict
    after: dict | None = None


def launch_arguments(browser: Path, copy: Path, headless: bool = False) -> list[str]:
    args = [str(browser), f"--user-data-dir={copy}", *OFFLINE,
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
    return args + ["--headless=new"] if headless else args


def long_path(path: Path) -> str:
    """The path as text; on Windows in the form that has no limit of 260 characters."""
    text = str(Path(path).resolve())
    return "\\\\?\\" + text if os.name == "nt" and not text.startswith("\\\\") else text


def _size(folder: Path) -> int:
    total = 0
    for parent, _, files in os.walk(long_path(folder)):
        for name in files:
            try:
                total += os.lstat(os.path.join(parent, name)).st_size
            except OSError:
                pass                        # the copy will say which file cannot be read
    return total


def refusal(browser: Path, user_data: Path, work: Path) -> str | None:
    """Why the rehearsal must not start, or None."""
    browser, user_data, work = Path(browser), Path(user_data).resolve(), Path(work).resolve()
    if not browser.is_file():
        return f"no browser at {browser}"
    if not (user_data / "Local State").is_file():
        return f"{user_data} is not a 'User Data' folder (no 'Local State')"
    if (user_data / "lockfile").exists():
        return (f"the browser of {user_data} is running; close it completely first "
                f"(the profile of a running browser is never copied)")
    if not work.is_dir():
        return f"no work folder at {work}"
    if work == user_data or user_data in work.parents:
        return f"the work folder {work} is inside the profile"
    for folder in (work, *work.parents):
        if (folder / ".git").exists():
            return (f"the work folder is in a git repository ({folder}); a copy of a profile holds cookies "
                    f"and saved passwords and never belongs there")
        if any(name in folder.name.lower() for name in CLOUD_NAMES):
            return (f"the work folder looks cloud-synced ('{folder.name}'); a copy of a profile holds cookies "
                    f"and saved passwords: use a private folder on a local drive")
    need = _size(user_data)
    if shutil.disk_usage(work).free < need + need // 10:
        return f"too little room on the drive of {work}: the copy needs {need / 2**30:.1f} GB"
    return None


def devtools_port(copy: Path, proc, timeout: float = START_TIMEOUT) -> int:
    port_file = copy / "DevToolsActivePort"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            # the browser may still be writing it (Windows refuses the read then)
            lines = port_file.read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip().isdigit():
                return int(lines[0])
        except OSError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(f"it ended at once (exit code {proc.returncode})")
        time.sleep(0.2)
    raise RuntimeError(f"no DevTools port after {timeout:.0f} s")


def ask_to_close(port: int) -> None:
    """The exit a person causes by closing the browser, so the profile is saved the same way."""
    version = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=30).read())
    ws = WebSocket(version["webSocketDebuggerUrl"])
    try:
        ws.call("Browser.close")
    except (ConnectionError, OSError, ValueError):
        pass                                # the browser may drop the connection instead of answering
    finally:
        ws.close()


def stop_tree(proc) -> None:
    """By force. Only ever for the browser this tool started itself, on its own copy."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def run(browser: Path, copy: Path, seconds: int, headless: bool = False, close_timeout: int = CLOSE_TIMEOUT, *,
        start=None, port_of=devtools_port, ask_to_close=ask_to_close, sleep=time.sleep, stop=stop_tree) -> str | None:
    """Open the copy with the new build, let it work, ask it to close. Returns what went wrong, or None."""
    (copy / "DevToolsActivePort").unlink(missing_ok=True)       # left by the browser the copy came from
    start = start or (lambda args: subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    proc = start(launch_arguments(browser, copy, headless))
    try:
        port = port_of(copy, proc, START_TIMEOUT)
    except RuntimeError as exc:
        stop(proc)
        return f"the new build did not start on the copy: {exc}"
    sleep(seconds)
    if proc.poll() is not None:
        return f"the new build ended by itself within {seconds} s (exit code {proc.returncode})"
    forced = "it was stopped by force, so this rehearsal does not count"
    try:
        ask_to_close(port)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        stop(proc)
        return f"the new build could not be asked to close ({type(exc).__name__}); {forced}"
    try:
        proc.wait(timeout=close_timeout)
    except subprocess.TimeoutExpired:
        stop(proc)
        return f"the new build did not close within {close_timeout} s of being asked; {forced}"
    return None


def _snapshot_when_closed(copy: Path) -> dict:
    for _ in range(40):                     # the last helper processes let go of the folder a moment later
        if not (copy / "lockfile").exists():
            break
        time.sleep(0.5)
    return profile_check.snapshot(copy)     # refuses a folder that is still locked


def _on_copy(browser: Path, copy: Path, seconds: int, headless: bool, close_timeout: int, runner, say) -> Result:
    try:
        result = Result([], [], profile_check.snapshot(copy))
    except profile_check.SnapshotError as exc:
        return Result([str(exc)], [], {})
    for name, profile in result.before["profiles"].items():
        say(f"before: {profile_check.summary_line(name, profile)}")
    say(f"the new build runs on the copy for {seconds} s, offline" +
        ("" if headless else "; a window opens and closes by itself, do not use it"))
    problem = runner(browser, copy, seconds, headless, close_timeout)
    if problem:
        result.problems.append(problem)
        return result
    try:
        result.after = _snapshot_when_closed(copy)
    except profile_check.SnapshotError as exc:
        result.problems.append(str(exc))
        return result
    for name, profile in result.after["profiles"].items():
        say(f"after:  {profile_check.summary_line(name, profile)}")
    problems = profile_check.compare(result.before, result.after)
    if headless:
        problems = [p for p in problems if profile_check.NO_NEW_SESSION not in p]
        result.notes.append(TABS_NOT_CHECKED)
    result.problems += problems
    return result


def _not_copied(exc: OSError) -> str:
    failures = exc.args[0] if isinstance(exc, shutil.Error) and exc.args and isinstance(exc.args[0], list) \
        else [(getattr(exc, "filename", None) or "", "", str(exc))]
    first = failures[0]
    return (f"the profile could not be copied completely: {len(failures)} file(s) could not be copied, "
            f"the first: {first[0]} ({first[2]}); the new build was not started")


def _writable_then_again(function, path, _):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _delete(root: Path) -> str | None:
    """Delete the folder this run made. Returns what to tell the person when that fails."""
    handler = {"onexc" if sys.version_info >= (3, 12) else "onerror": _writable_then_again}
    for _ in range(10):
        try:
            shutil.rmtree(long_path(root), **handler)
            return None
        except OSError:
            time.sleep(1)                   # a helper process of the browser may hold a file for a moment
    return f"the copy could not be deleted; it holds cookies and saved passwords, delete it yourself: {root}"


def rehearse(browser: Path, user_data: Path, work: Path, seconds: int = 60, headless: bool = False,
             close_timeout: int = CLOSE_TIMEOUT, runner=None, say=lambda text: None) -> Result:
    """Steps 1 to 5 of the module text. Raises Refused before anything is copied or started."""
    why = refusal(browser, user_data, work)
    if why:
        raise Refused(why)
    root = Path(tempfile.mkdtemp(prefix="rehearsal-", dir=work))     # new, and only this user can open it
    result = None
    try:
        say("copying the profile")
        copy = root / "User Data"
        try:
            shutil.copytree(long_path(user_data), long_path(copy), symlinks=True)
        except OSError as exc:              # shutil.Error too: some files could not be copied
            result = Result([_not_copied(exc)], [], {})
        else:
            result = _on_copy(Path(browser), copy, seconds, headless, close_timeout, runner or run, say)
    finally:
        left = _delete(root)
        if left and result is not None:
            result.problems.append(left)
        elif left:
            print(f"profile rehearsal: {left}", file=sys.stderr)
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path, help="the new build's browser executable")
    parser.add_argument("--user-data", required=True, type=Path, help="the 'User Data' folder to rehearse on")
    parser.add_argument("--work", required=True, type=Path, help="a private local folder for the copy")
    parser.add_argument("--seconds", type=int, default=60, help="how long the new build runs on the copy")
    parser.add_argument("--close-timeout", type=int, default=CLOSE_TIMEOUT)
    parser.add_argument("--headless", action="store_true", help="no window; tabs and tab groups are not checked")
    parser.add_argument("--before-out", type=Path, help="keep the snapshot from before (counts only) in this file")
    a = parser.parse_args(argv)
    say = lambda text: print(f"profile rehearsal: {text}", flush=True)
    try:
        result = rehearse(a.browser, a.user_data, a.work, a.seconds, a.headless, a.close_timeout, say=say)
    except Refused as exc:
        say(f"refused: {exc}")
        return 2
    if a.before_out and result.before:
        a.before_out.write_text(json.dumps(result.before, indent=2, ensure_ascii=False), encoding="utf-8")
    for line in result.problems + result.notes:
        print(line)
    if result.problems:
        say(f"{len(result.problems)} problem(s). Do not install this build over that profile.")
        return 1
    say("the new build kept everything (1:1 on every checked item); the copy is deleted")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
