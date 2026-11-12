#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, `$urlskip`, checked end to end and offline (ROADMAP P5.26).

A `$urlskip` rule sends a navigation to a tracking redirector straight to the address that is written
inside the redirector's own address. The check takes real rules from the browser's bundled lists: the
first one that reads the destination from a parameter, and the first one that also decodes it from
base64. Each rule's site name and a destination name are sent to a local server by host-resolver rules;
every other name fails, so nothing leaves the PC. The server writes down every request it gets.

With native blocking on:

    param    a navigation to the redirector: the destination is reached, the redirector is never asked
    base64   the same with a destination written in base64
    post     a form sent to the redirector with POST: it goes to the redirector as it is
    frame    the redirector inside a frame of a page: the frame goes to the redirector as it is

With native blocking off (control), a navigation to the redirector goes to the redirector.

    py -3 -I tools/qa/adblock_urlskip_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every scenario passes in both modes.
"""
import argparse
import base64
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

DEST = "dest.test"
# The test server speaks plain HTTP: the browser must not try HTTPS first (as adblock_cosmetic_check.py).
NO_HTTPS_FIRST = "HttpsUpgrades,HttpsFirstBalancedModeAutoEnable"
SETTLE_S = 3.0
# ||host^$urlskip=?name  and  ||host/path?name=$urlskip=?name -base64 (with or without "doc,")
PARAM_RE = re.compile(r"\|\|([a-z0-9.-]+)\^\$(?:doc,|document,)?urlskip=\?([A-Za-z_][A-Za-z0-9_]*)")
BASE64_RE = re.compile(r"\|\|([a-z0-9.-]+)((?:/[A-Za-z0-9_.-]+)+)\?([A-Za-z_][A-Za-z0-9_]*)="
                       r"\$(?:doc,|document,)?urlskip=\?\3 -base64")
SCENARIOS = [
    {"name": "param", "case": "param", "skipped": True, "how": "open"},
    {"name": "base64", "case": "base64", "skipped": True, "how": "open"},
    {"name": "post", "case": "param", "skipped": False, "how": "post"},
    {"name": "frame", "case": "param", "skipped": False, "how": "frame"},
]


def cases(lists_text: str) -> dict:
    """The first usable rule of each kind in the lists. A kind without one is left out."""
    out = {}
    for line in (line.strip() for line in lists_text.splitlines()):
        if "param" not in out and (m := PARAM_RE.fullmatch(line)):
            out["param"] = {"host": m.group(1), "path": "/", "name": m.group(2), "base64": False}
        elif "base64" not in out and (m := BASE64_RE.fullmatch(line)):
            out["base64"] = {"host": m.group(1), "path": m.group(2), "name": m.group(3), "base64": True}
    return out


def hosts(found: dict) -> list[str]:
    return sorted({case["host"] for case in found.values()} | {DEST})


def redirector_url(case: dict, destination: str) -> str:
    value = base64.b64encode(destination.encode()).decode() if case["base64"] else destination
    return f"http://{case['host']}{case['path']}?{case['name']}={urllib.parse.quote(value, safe='')}"


def problems(name: str, skipped: bool, host: str, seen: list, method: str = "GET") -> list[str]:
    """`seen`: the requests the server got, as (host, path with query, method)."""
    asked = any(h == host and m == method for h, _, m in seen)
    landed = any(h == DEST and f"case={name}" in p for h, p, _ in seen)
    out = []
    if skipped:
        if any(h == host for h, _, _ in seen):
            out.append(f"the redirector was asked ({host})")
        if not landed:
            out.append("the destination was not reached")
    else:
        if not asked:
            out.append(f"the redirector was not asked with {method} ({host})")
        if landed:
            out.append("the navigation was sent on to the destination")
    return out


class Server:
    def __init__(self):
        self.seen: list[tuple[str, str, str]] = []
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self):
                host = (self.headers.get("Host") or "").split(":")[0]
                server.seen.append((host, self.path, self.command))
                url = urllib.parse.urlsplit(self.path)
                to = urllib.parse.parse_qs(url.query).get("to", [""])[0]
                if host == "127.0.0.1" and url.path == "/post.html":
                    body = (f'<form id="f" method="post" action="{to}"><input name="a" value="1"></form>'
                            '<script>document.getElementById("f").submit();</script>')
                elif host == "127.0.0.1" and url.path == "/frame.html":
                    body = f'<iframe src="{to}" width="300" height="100"></iframe>'
                else:
                    body = f"<p>{'landed' if host == DEST else 'redirector'}</p>"
                data = f"<!doctype html><meta charset=\"utf-8\"><title>urlskip check</title>{body}".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._answer()

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self._answer()

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def run_mode(browser: Path, work: Path, found: dict, native: bool) -> list[str]:
    out: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="urlskip-", dir=work))
    with Server() as server:
        rules = ", ".join(f"MAP {h} 127.0.0.1:{server.port}" for h in hosts(found))
        args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
                "--disable-component-update",
                *(["--enable-features=ThoronNativeAdblock", f"--disable-features={NO_HTTPS_FIRST}"] if native
                  else [f"--disable-features=ThoronNativeAdblock,{NO_HTTPS_FIRST}"]),
                f"--host-resolver-rules={rules}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        devtools = _devtools_port(profile)
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{devtools}/json/new?about:blank", method="PUT")
            tab = WebSocket(json.loads(urllib.request.urlopen(req, timeout=20).read())["webSocketDebuggerUrl"])
            # the engine is loaded by the first page; give it a moment before the scenarios
            tab.call("Page.navigate", url=f"http://{DEST}/landed.html?case=warm-up")
            time.sleep(SETTLE_S + 2)
            for scenario in SCENARIOS:
                case = found[scenario["case"]]
                to = redirector_url(case, f"http://{DEST}/landed.html?case={scenario['name']}")
                url = to if scenario["how"] == "open" else (
                    f"http://127.0.0.1:{server.port}/{scenario['how']}.html?to={urllib.parse.quote(to, safe='')}")
                server.seen.clear()
                tab.call("Page.navigate", url=url)
                time.sleep(SETTLE_S)
                skipped = scenario["skipped"] and native
                found_here = problems(scenario["name"], skipped, case["host"], list(server.seen),
                                      method="POST" if scenario["how"] == "post" else "GET")
                mode = "native" if native else "control"
                print(f"{'PASS' if not found_here else 'FAIL'}  {mode} {scenario['name']}: "
                      + ("the destination, the redirector never asked" if skipped and not found_here
                         else "the redirector" if not found_here else "; ".join(found_here)))
                out += [f"{mode} {scenario['name']}: {p}" for p in found_here]
            tab.close()
        finally:
            _close_browser(devtools, proc)
    shutil.rmtree(profile, ignore_errors=True)
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path)
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    found = cases(lists_file.read_text(encoding="utf-8"))
    missing = [kind for kind in ("param", "base64") if kind not in found]
    if missing:
        print(f"URLSKIP CHECK: FAILED (the lists hold no simple rule of the kind: {', '.join(missing)})")
        return 1
    for kind, case in found.items():
        print(f"{kind}: ||{case['host']}{'' if case['path'] == '/' else case['path']} reads ?{case['name']}")
    a.work.mkdir(parents=True, exist_ok=True)
    found_problems = run_mode(a.browser, a.work, found, native=True) + run_mode(a.browser, a.work, found, native=False)
    for problem in found_problems:
        print(problem)
    print("URLSKIP CHECK: PASSED" if not found_problems else f"URLSKIP CHECK: FAILED ({len(found_problems)} problem(s))")
    return 1 if found_problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
