#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad-blocking list updates, checked end to end and offline (ROADMAP P5.15).

Each scenario starts the browser headless on a fresh throwaway profile (sandbox on) with the
ThoronNativeAdblock feature and `--thoron-adblock-lists-url-for-testing`, which points the list updater
at a local server (the browser accepts only loopback addresses there). The server hands out the
browser's own bundled lists, changed per scenario, and a page that keeps loading a probe script from a
test host that no shipped list blocks. Host-resolver rules send that host to the local server and make
every other host fail.

    good       easylist gains "||update-probe.test^": the update is used, and the probe is blocked
    shrunk     easylist is cut to one rule: refused ("shrank"), the previous engine stays
    allow-all  easylist gains "@@*" as well: refused, the previous engine stays
    web-page   a sign-in page instead of easylist: refused, the previous engine stays
    unblocks   every rule for the browser's known ad and tracker probes is dropped from every list: the
               whole update is refused, as the new engine would let known ads through
    restart    the "good" profile starts again with no list server: the saved engine blocks the probe
               from the start, and no list is downloaded (the next check is not due)

    py -3 -I tools/qa/adblock_update_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every scenario passes.
"""
import argparse
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

MARKER = "! thoron-list: "
PROBE_HOST = "update-probe.test"
PROBE_RULE = f"||{PROBE_HOST}^"
STORE_DIR = "Thoron Adblock"
SCENARIOS = ("good", "shrunk", "allow-all", "web-page", "unblocks")
# Words of the browser's probe requests (list_store.cc): "unblocks" drops every rule holding one.
PROBE_WORDS = ("googlesyndication", "adsbygoogle", "doubleclick", "gpt.js", "amazon-adsystem", "apstag",
               "google-analytics", "analytics.js", "facebook.net", "fbevents", "ads-twitter", "uwt.js")
REFUSED = {"shrunk": "shrank from", "allow-all": "allows every request", "web-page": "a web page"}
LAST_ATTEMPTS = 5          # these final probe attempts decide whether the probe is blocked
AFTER_UPDATE_S = 9         # keep the page running this long after the update check finished
RESTART_S = 14
INTERVAL_MS = 1000
PAGE = """<!doctype html>
<meta charset="utf-8"><title>Thoron list update check</title>
<script>
let n = 0;
setInterval(() => {
  const i = n++;
  fetch("/tick?n=" + i).catch(() => {});
  const s = document.createElement("script");
  s.src = "http://%(host)s/probe.js?n=" + i;
  document.head.appendChild(s);
}, %(interval)d);
</script>
"""


def split_lists(text: str) -> dict[str, str]:
    """The bundled lists file, by list id (its "! thoron-list: <id>" lines)."""
    lists: dict[str, str] = {}
    current = None
    for line in text.splitlines(keepends=True):
        if line.startswith(MARKER):
            current = line[len(MARKER):].strip()
            lists[current] = ""
        elif current is not None:
            lists[current] += line
    return lists


def served_lists(bundled: dict[str, str], scenario: str) -> dict[str, str]:
    if scenario == "restart":
        return {}
    served = dict(bundled)
    easylist = bundled["easylist"].rstrip("\n")
    if scenario == "good":
        served["easylist"] = f"{easylist}\n{PROBE_RULE}\n"
    elif scenario == "shrunk":
        served["easylist"] = f"{PROBE_RULE}\n"
    elif scenario == "allow-all":
        served["easylist"] = f"{easylist}\n@@*\n{PROBE_RULE}\n"
    elif scenario == "web-page":
        served["easylist"] = "<!doctype html><html><body>Sign in to use this Wi-Fi</body></html>\n"
    elif scenario == "unblocks":
        for list_id, text in bundled.items():
            served[list_id] = "".join(line for line in text.splitlines(keepends=True)
                                      if not any(w in line for w in PROBE_WORDS))
        served["easylist"] = served["easylist"].rstrip("\n") + f"\n{PROBE_RULE}\n"
    else:
        raise ValueError(scenario)
    return served


def probe_blocked(seen: list[int], made: int, last: int = LAST_ATTEMPTS) -> bool:
    """True when the page made enough attempts and none of the last `last` reached the server."""
    if made < last:
        return False
    return not [n for n in seen if n >= made - last]


def problems(scenario: str, state: dict | None, probe_blocked: bool, list_requests: int) -> list[str]:
    if not isinstance(state, dict):
        return ["no state file: the update check did not run"]
    note = (((state.get("lists") or {}).get("easylist")) or {}).get("note", "")
    out = []
    if scenario == "good":
        if note != "updated":
            out.append(f"easylist was not updated: {note!r}")
        if not probe_blocked:
            out.append("the probe is not blocked after the update")
        if not list_requests:
            out.append("no list was downloaded")
    elif scenario in REFUSED:
        if not (note.startswith("kept: ") and REFUSED[scenario] in note):
            out.append(f"easylist was not refused for the expected reason: {note!r}")
        if probe_blocked:
            out.append("the probe is blocked: the refused list was used")
    elif scenario == "unblocks":
        if "all kept: the new engine no longer blocks" not in state.get("result", ""):
            out.append("an update that stops blocking known ads was not refused")
        if probe_blocked:
            out.append("the probe is blocked: the refused update was used")
    elif scenario == "restart":
        if list_requests:
            out.append(f"{list_requests} list downloads on restart, though no check was due")
        if not probe_blocked:
            out.append("the saved engine was not used: the probe is not blocked")
    else:
        raise ValueError(scenario)
    return out


class ListServer:
    def __init__(self, lists: dict[str, str]):
        self.lists = lists
        self.list_requests = 0
        self.ticks: list[int] = []
        self.probes: list[int] = []
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                n = urllib.parse.parse_qs(url.query).get("n", ["-1"])[0]
                if url.path == "/test.html":
                    page = PAGE % {"host": PROBE_HOST, "interval": INTERVAL_MS}
                    self._send(200, "text/html; charset=utf-8", page.encode())
                elif url.path == "/tick":
                    server.ticks.append(int(n) if n.isdigit() else -1)
                    self._send(200, "text/plain", b"ok")
                elif url.path == "/probe.js":
                    server.probes.append(int(n) if n.isdigit() else -1)
                    self._send(200, "text/javascript", b"window.__probe = 1;")
                elif url.path.startswith("/lists/") and url.path.endswith(".txt"):
                    server.list_requests += 1
                    text = server.lists.get(url.path[len("/lists/"):-len(".txt")])
                    if text is None:
                        self._send(404, "text/plain", b"not found")
                    else:
                        self._send(200, "text/plain; charset=utf-8", text.encode("utf-8"))
                else:
                    self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    @property
    def made(self) -> int:
        return max(self.ticks, default=-1) + 1

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _launch(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", "--enable-features=ThoronNativeAdblock",
            f"--thoron-adblock-lists-url-for-testing=http://127.0.0.1:{port}/lists/",
            f"--host-resolver-rules=MAP {PROBE_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"http://127.0.0.1:{port}/test.html"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _stop(proc: subprocess.Popen) -> None:
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


def _read_state(profile: Path) -> dict | None:
    try:
        return json.loads((profile / STORE_DIR / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_scenario(browser: Path, profile: Path, bundled: dict[str, str], scenario: str,
                 timeout_s: int = 120) -> dict:
    with ListServer(served_lists(bundled, scenario)) as server:
        before = _read_state(profile)
        proc = _launch(browser, profile, server.port)
        try:
            if scenario == "restart":
                time.sleep(RESTART_S)
            else:
                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline and _read_state(profile) in (None, before):
                    time.sleep(0.5)
                time.sleep(AFTER_UPDATE_S)
        finally:
            _stop(proc)
        state = _read_state(profile)
        blocked = probe_blocked(server.probes, server.made)
        found = problems(scenario, state, blocked, server.list_requests)
        return {"scenario": scenario, "passed": not found, "problems": found,
                "probe_attempts": server.made, "probes_seen": len(server.probes), "probe_blocked": blocked,
                "list_requests": server.list_requests,
                "result": (state or {}).get("result", "")}


def run_all(browser: Path, work: Path, lists_file: Path) -> list[dict]:
    bundled = split_lists(lists_file.read_text(encoding="utf-8"))
    if "easylist" not in bundled:
        raise SystemExit(f"{lists_file} has no list markers; build the browser with the marked lists first")
    work.mkdir(parents=True, exist_ok=True)
    results = []
    for scenario in SCENARIOS:
        profile = Path(tempfile.mkdtemp(prefix=f"update-{scenario}-", dir=work))
        try:
            results.append(run_scenario(browser, profile, bundled, scenario))
            if scenario == "good":
                results.append(run_scenario(browser, profile, bundled, "restart"))
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    parser.add_argument("--lists", type=Path, help="bundled lists (default: thoron_adblock_lists.txt next to it)")
    a = parser.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    results = run_all(a.browser, a.work, lists_file)
    print(json.dumps(results, indent=2))
    ok = all(r["passed"] for r in results)
    print("LIST UPDATE CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
