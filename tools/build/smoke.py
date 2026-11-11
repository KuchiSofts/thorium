#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Smoke-test a freshly built browser: fresh throwaway profile, sandbox always on, local page only.

Fails on a non-zero exit, any crash dump, a missing or empty smoke result (the page script did not
run), any required capability (JS, WebGL, H.264, HEVC, AV1, JPEG XL) not reported true, or (on
Windows) a sandbox that is not in force: every renderer of the browser must run below Medium
integrity and no child process may carry --no-sandbox. The sandbox is checked by reading each
process's security token, not by trusting switches.
    py -3 -I tools/build/smoke.py --browser out\\thoron\\chrome.exe --work C:\\thoron-build\\smoke\\win
        --jxl-sample <chromium src>\\third_party\\libjxl\\src\\testdata\\...\\<small>.jxl
"""
import argparse
import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = {"js": True, "webgl": True, "h264": True, "hevc": True, "av1": True, "jxl": True}
PAGE_TEMPLATE = Path(__file__).with_name("smoke_page.html")
RESULT_RE = re.compile(r'<pre id="result">(.*?)</pre>', re.S)
CRASH_DIRS = (("Crashpad", "reports"), ("Crash Reports",))  # Windows, Linux


def _render_page(work_dir: Path, jxl_sample: Path | None) -> Path:
    sample = base64.b64encode(jxl_sample.read_bytes()).decode("ascii") if jxl_sample else ""
    page = work_dir / "smoke_page.html"
    page.write_text(PAGE_TEMPLATE.read_text(encoding="utf-8").replace("__JXL_BASE64__", sample), encoding="utf-8")
    return page


MEDIUM_INTEGRITY = 0x2000
_LEVELS = {0x0000: "Untrusted", 0x1000: "Low", 0x2000: "Medium", 0x3000: "High", 0x4000: "System"}


def _integrity_rid(pid: int) -> int | None:
    """Mandatory integrity level of a Windows process (0x0000 Untrusted ... 0x4000 System), or None."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    a32 = ctypes.WinDLL("advapi32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    a32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    a32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    process = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        return None
    try:
        token = wintypes.HANDLE()
        if not a32.OpenProcessToken(process, 0x0008, ctypes.byref(token)):   # TOKEN_QUERY
            return None
        try:
            size = wintypes.DWORD()
            a32.GetTokenInformation(token, 25, None, 0, ctypes.byref(size))  # TokenIntegrityLevel
            buf = ctypes.create_string_buffer(size.value)
            if not a32.GetTokenInformation(token, 25, buf, size, ctypes.byref(size)):
                return None
            sid = ctypes.c_void_p(ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0])
            count = a32.GetSidSubAuthorityCount(sid)[0]
            return int(a32.GetSidSubAuthority(sid, count - 1)[0])
        finally:
            k32.CloseHandle(token)
    finally:
        k32.CloseHandle(process)


def _list_processes() -> list[dict]:
    """All processes with pid, parent pid and command line (Windows, via CIM)."""
    script = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine | "
              "ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout
    return [{"pid": p["ProcessId"], "ppid": p["ParentProcessId"], "cmd": p.get("CommandLine") or ""}
            for p in json.loads(out or "[]")]


def sandbox_report(browser_pid: int, list_processes, integrity) -> list[str]:
    """Problems with the sandbox of the browser's process tree (empty list: sandbox in force)."""
    procs = list_processes()
    children: dict[int, list[dict]] = {}
    for p in procs:
        children.setdefault(p["ppid"], []).append(p)
    tree, todo = [], [browser_pid]
    while todo:
        for child in children.get(todo.pop(), []):
            if child["pid"] != browser_pid and child not in tree:
                tree.append(child)
                todo.append(child["pid"])
    problems = [f"process {p['pid']} runs with --no-sandbox" for p in tree if "--no-sandbox" in p["cmd"]]
    renderers = [p for p in tree if "--type=renderer" in p["cmd"]]
    if not renderers:
        problems.append("no renderer process found, so the sandbox could not be checked")
    for r in renderers:
        level = integrity(r["pid"])
        if level is None:
            problems.append(f"renderer {r['pid']}: integrity level could not be read")
        elif level >= MEDIUM_INTEGRITY:
            problems.append(f"renderer {r['pid']} runs at {_LEVELS.get(level, hex(level))} integrity (not sandboxed)")
    return problems


def _linux_processes() -> list[dict]:
    procs = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            procs.append({"pid": int(d.name), "ppid": ppid, "cmd": cmd})
        except (OSError, ValueError, IndexError):
            continue
    return procs


def _linux_proc_info(pid: int) -> dict | None:
    try:
        status = Path(f"/proc/{pid}/status").read_text()
        seccomp = int(re.search(r"^Seccomp:\s*(\d+)", status, re.M).group(1))
        return {"seccomp": seccomp, "pidns": os.readlink(f"/proc/{pid}/ns/pid")}
    except (OSError, AttributeError, ValueError):
        return None


def linux_sandbox_report(browser_pid: int, list_processes, proc_info) -> list[str]:
    """Linux: every renderer must run under a seccomp-BPF filter (Seccomp: 2) and in its own PID
    namespace (not the browser's), and no child may carry --no-sandbox."""
    procs = list_processes()
    children: dict[int, list[dict]] = {}
    for p in procs:
        children.setdefault(p["ppid"], []).append(p)
    tree, todo = [], [browser_pid]
    while todo:
        for child in children.get(todo.pop(), []):
            if child["pid"] != browser_pid and child not in tree:
                tree.append(child)
                todo.append(child["pid"])
    problems = [f"process {p['pid']} runs with --no-sandbox" for p in tree if "--no-sandbox" in p["cmd"]]
    renderers = [p for p in tree if "--type=renderer" in p["cmd"]]
    if not renderers:
        problems.append("no renderer process found, so the sandbox could not be checked")
    browser = proc_info(browser_pid)
    for r in renderers:
        info = proc_info(r["pid"])
        if info is None or browser is None:
            problems.append(f"renderer {r['pid']}: sandbox state could not be read")
            continue
        if info["seccomp"] != 2:
            problems.append(f"renderer {r['pid']} has no seccomp-BPF filter (Seccomp: {info['seccomp']})")
        if info["pidns"] == browser["pidns"]:
            problems.append(f"renderer {r['pid']} shares the browser's PID namespace (no namespace sandbox)")
    return problems


def check_sandbox(browser: Path, work_dir: Path, settle_s: float = 5.0) -> list[str]:
    """Start the browser (headless, fresh profile, about:blank) and inspect its live process tree."""
    import time
    windows = os.name == "nt"
    profile = Path(tempfile.mkdtemp(prefix="sandbox-", dir=work_dir))
    proc = subprocess.Popen([str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
                             "--no-default-browser-check", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=not windows)
    try:
        time.sleep(settle_s)
        if windows:
            return sandbox_report(proc.pid, _list_processes, _integrity_rid)
        return linux_sandbox_report(proc.pid, _linux_processes, _linux_proc_info)
    finally:
        for _ in range(3):        # closing must never hide the result; try a few times, then move on
            if windows:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            else:
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                proc.wait(timeout=20)
                break
            except subprocess.TimeoutExpired:
                continue
        time.sleep(2)
        import shutil
        shutil.rmtree(profile, ignore_errors=True)


def _crash_dumps(profile: Path) -> list[str]:
    dumps = []
    for parts in CRASH_DIRS:
        folder = profile.joinpath(*parts)
        if folder.is_dir():
            dumps += sorted(p.name for p in folder.rglob("*") if p.is_file())
    return dumps


def run_smoke(browser: Path, work_dir: Path, timeout_s: int = 90, jxl_sample: Path | None = None,
              sandbox_check=None) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="profile-", dir=work_dir))  # fresh and empty every run
    page = _render_page(work_dir, jxl_sample)
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--dump-dom", page.resolve().as_uri()]
    failures, results = [], {}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout_s)
        exit_code, output = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        exit_code, output = None, ""
        failures.append(f"timed out after {timeout_s} s")
    if exit_code not in (0, None):
        failures.append(f"exit code {exit_code}")
    match = RESULT_RE.search(output)
    if match:
        try:
            results = json.loads(html.unescape(match.group(1)))
        except ValueError:
            failures.append("smoke result is not valid JSON")
    else:
        failures.append("no smoke result in browser output")
    if match and not isinstance(results, dict):
        failures.append(f"smoke result is not an object: {results!r}")
        results = {}
    if match and not results:
        failures.append("smoke result is empty: the page script did not run")
    for key, wanted in REQUIRED.items():
        if match and results and results.get(key) is not wanted:
            failures.append(f"capability {key} is {results.get(key)!r}, expected {wanted}")
    dumps = _crash_dumps(profile)
    if dumps:
        failures.append(f"crash dump(s) written: {', '.join(dumps)}")
    failures += (sandbox_check or check_sandbox)(browser, work_dir)
    return {"exit_code": exit_code, "results": results, "crash_dumps": dumps,
            "passed": not failures, "failures": failures}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--jxl-sample", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    a = parser.parse_args(argv)
    result = run_smoke(a.browser, a.work, a.timeout, a.jxl_sample)
    print(json.dumps(result, indent=2))
    print("SMOKE: PASSED" if result["passed"] else "SMOKE: FAILED")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
