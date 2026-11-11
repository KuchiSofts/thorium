#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Offline benchmark harness (ROADMAP Q.1): start-up time, memory (private bytes) with 1 and 20 tabs, idle CPU.

Every run uses a fresh throwaway profile in --work, the sandbox stays on, and every page comes from a
local server on 127.0.0.1, so nothing leaves the machine and no real profile is touched. Each value is
measured --runs times; the report gives the median and the spread ((max - min) / median), and marks a
value repeatable when the spread is within 3 %. The online suites (Speedometer 3, JetStream 2,
MotionMark) are a later step.
    py -3 -I tools/qa/bench.py --browser <out>\\thoron.exe --work C:\\thoron-build\\bench --runs 5
        --out docs/perf/<name>.json --md docs/perf/<name>.md
"""
import argparse
import http.server
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPEATABLE_PCT = 3.0
PAGE = ("<!doctype html><html><head><meta charset='utf-8'><title>bench</title></head><body>"
        "<h1>Thoron bench</h1><p>" + "Lorem ipsum dolor sit amet. " * 200 + "</p>"
        "<script>addEventListener('load', () => fetch('/ping').catch(() => {}));</script></body></html>")


class BenchError(Exception):
    pass


def tree(procs: list[dict], root: int) -> list[dict]:
    by_pid = {p["pid"]: p for p in procs}
    if root not in by_pid:
        raise BenchError(f"process {root} is not running")
    out, todo = [], [root]
    while todo:
        pid = todo.pop()
        out.append(by_pid[pid])
        todo += [p["pid"] for p in procs if p["ppid"] == pid and p["pid"] != pid]
    return out


def total(procs: list[dict], root: int, key: str):
    return sum(p[key] for p in tree(procs, root))


def summarise(values: list[float]) -> dict:
    if len(values) < 3:
        raise BenchError("at least 3 runs are needed")
    med = statistics.median(values)
    spread = (max(values) - min(values)) / med * 100 if med else 0.0
    return {"median": round(med, 1), "spread_pct": round(spread, 1), "runs": len(values),
            "repeatable": spread <= REPEATABLE_PCT, "values": [round(v, 1) for v in values]}


class PingServer:
    """Serves PAGE at /page and records the first /ping, on 127.0.0.1 only."""

    def __init__(self):
        outer = self
        self.first_ping = None
        self._event = threading.Event()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/ping"):
                    if outer.first_ping is None:
                        outer.first_ping = time.monotonic()
                        outer._event.set()
                    body, kind = b"ok", "text/plain"
                else:
                    body, kind = PAGE.encode("utf-8"), "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self._server.server_address[1]}"

    def url(self, name: str) -> str:
        return f"{self.base}/{name}"

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


def _processes() -> list[dict]:
    """pid, parent, private memory (bytes; working set on Linux) and CPU time (s) of every process."""
    if os.name == "nt":
        script = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,PrivatePageCount,"
                  "KernelModeTime,UserModeTime | ConvertTo-Json -Compress")
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout
        return [{"pid": p["ProcessId"], "ppid": p["ParentProcessId"], "ws": int(p.get("PrivatePageCount") or 0),
                 "cpu": (int(p.get("KernelModeTime") or 0) + int(p.get("UserModeTime") or 0)) / 1e7}
                for p in json.loads(out or "[]")]
    procs, tick, page = [], os.sysconf("SC_CLK_TCK"), os.sysconf("SC_PAGE_SIZE")
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                f = (d / "stat").read_text().rsplit(")", 1)[1].split()
                procs.append({"pid": int(d.name), "ppid": int(f[1]), "cpu": (int(f[11]) + int(f[12])) / tick,
                              "ws": int((d / "statm").read_text().split()[1]) * page})
            except (OSError, IndexError, ValueError):
                continue
    return procs


def _launch(browser: Path, profile: Path, urls: list[str], devtools: bool = False) -> subprocess.Popen:
    extra = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"] if devtools else []
    return subprocess.Popen([str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
                             "--no-default-browser-check", *extra, *urls],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt")


def _stop(proc: subprocess.Popen, profile: Path) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(2)
    shutil.rmtree(profile, ignore_errors=True)


def run_startup(browser: Path, work: Path, runs: int, timeout: float = 60) -> list[float]:
    values = []
    for _ in range(runs):
        profile = Path(tempfile.mkdtemp(prefix="bench-", dir=work))
        with PingServer() as server:
            start = time.monotonic()
            proc = _launch(browser, profile, [server.url("page")])
            try:
                if not server.wait(timeout):
                    raise BenchError(f"the page did not load within {timeout} s")
                values.append((server.first_ping - start) * 1000)
            finally:
                _stop(proc, profile)
    return values


def _open_tabs(profile: Path, urls: list[str], timeout: float = 30) -> None:
    """Open more tabs through the test profile's DevTools endpoint (127.0.0.1, random port): the headless
    browser does not open several command-line URLs."""
    import urllib.request
    port_file = profile / "DevToolsActivePort"
    deadline = time.monotonic() + timeout
    while not port_file.is_file():
        if time.monotonic() > deadline:
            raise BenchError("the browser did not open its DevTools port")
        time.sleep(0.2)
    port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
    for url in urls:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")
        urllib.request.urlopen(req, timeout=10).read()


def run_memory(browser: Path, work: Path, runs: int, tabs: int, settle: float = 20) -> list[float]:
    values = []
    for _ in range(runs):
        profile = Path(tempfile.mkdtemp(prefix="bench-", dir=work))
        with PingServer() as server:
            proc = _launch(browser, profile, [server.url("page?0")], devtools=tabs > 1)
            try:
                if tabs > 1:
                    _open_tabs(profile, [server.url(f"page?{i}") for i in range(1, tabs)])
                time.sleep(settle)
                values.append(total(_processes(), proc.pid, "ws") / 2**20)
            finally:
                _stop(proc, profile)
    return values


def run_idle_cpu(browser: Path, work: Path, runs: int, seconds: float = 30, settle: float = 15) -> list[float]:
    values, cpus = [], os.cpu_count() or 1
    for _ in range(runs):
        profile = Path(tempfile.mkdtemp(prefix="bench-", dir=work))
        with PingServer() as server:
            proc = _launch(browser, profile, [server.url("page")])
            try:
                time.sleep(settle)
                before = total(_processes(), proc.pid, "cpu")
                time.sleep(seconds)
                after = total(_processes(), proc.pid, "cpu")
                values.append((after - before) / seconds / cpus * 100)
            finally:
                _stop(proc, profile)
    return values


def to_markdown(results: dict) -> str:
    out = [f"# Benchmark: {results.get('browser', '')} {results.get('version', '')}".rstrip(), "",
           "| Measure | Median | Spread | Runs | Repeatable |", "|---|---|---|---|---|"]
    for key, s in results.items():
        if isinstance(s, dict) and "median" in s:
            out.append(f"| {key} | {s['median']} | {s['spread_pct']} % | {s['runs']} | "
                       f"{'yes' if s['repeatable'] else 'no'} |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--label", default="")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--md", type=Path)
    a = p.parse_args(argv)
    a.work.mkdir(parents=True, exist_ok=True)
    try:
        results = {"browser": a.label or a.browser.name, "version": "",
                   "startup_ms": summarise(run_startup(a.browser, a.work, a.runs)),
                   "memory_1_tab_mb": summarise(run_memory(a.browser, a.work, a.runs, 1)),
                   "memory_20_tabs_mb": summarise(run_memory(a.browser, a.work, a.runs, 20)),
                   "idle_cpu_pct": summarise(run_idle_cpu(a.browser, a.work, a.runs))}
    except BenchError as exc:
        print(f"bench: {exc}", file=sys.stderr)
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if a.md:
        a.md.write_text(to_markdown(results), encoding="utf-8", newline="\n")
    print(to_markdown(results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
