#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, `$header` rules, checked end to end and offline (ROADMAP P5.26).

A `$header` rule ends a request when the server's answer carries a header the rule names. The check takes
real rules from the browser's bundled lists, one of each kind it can build a request for:

    name       a script whose answer has the header the rule names
    value      a script whose answer has the header with the text the rule names
    redirect   a script that is sent on to another address, by a redirect of the kind the rule names
    frame      a frame whose answer has the header the rule names

Every case has two sides: an address whose server answers as the rule says, and one of the same shape whose
server does not. The names are sent to a local server by host-resolver rules; every other name fails, so
nothing leaves the PC. A page on another site asks for both sides of every case and reports what became
of them, in three modes:

    control    native blocking off: everything loads
    native     native blocking on: the answer with the header ends the request, the other one loads
    site-off   ads allowed on the page's site (the per-site switch): everything loads

    py -3 -I tools/qa/adblock_header_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every case passes in every mode.
"""
import argparse
import http.server
import json
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch, _navigate  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
KINDS = ("name", "value", "redirect", "frame")
SIDES = ("with", "without")
RESULT_TIMEOUT_S = 60
REPORT_AFTER_MS = 3500     # the page reports this long after it has loaded
# ||host/*.min.js|$script,xhr,3p,header=name  and the same with  header=name:*text*
NAME_RE = re.compile(r"\|\|([a-z0-9.-]+)/\*\.min\.js\|\$script,xhr,3p,header=([a-z0-9-]+)")
VALUE_RE = re.compile(r"\|\|([a-z0-9.-]+)/\*\.min\.js\|\$script,xhr,3p,header=([a-z0-9-]+):\*([a-z0-9.-]+)\*")
# a script of any ".com" site that is sent on to an address starting as the rule says
REDIRECT_RE = re.compile(r"\|\|com/script/\*\.js\|\$script,3p,header=location:(https://[a-z]+\.)\*")
# a frame of a ".com" site with a long path of letters and digits, in a page of the sites the rule names
FRAME_RE = re.compile(r"/\^https\?:\\/\\/\[a-z\]\{7,\}\\\.com\\/\[\+\\/0-9a-zA-Z\]\{19,\}\$/"
                      r"\$frame,3p,match-case,header=([a-z0-9-]+),to=com,from=([a-z0-9.|~-]+)")
FRAME_PATH = "/A1b2C3d4E5f6G7h8I9j0"


def _sides(kind: str, site: str, path: str, headers: dict, other_headers: dict) -> dict:
    return {"with": {"host": f"with-{kind}.{site}", "path": path, "headers": headers},
            "without": {"host": f"without-{kind}.{site}", "path": path, "headers": other_headers}}


def cases(lists_text: str) -> dict:
    """The first usable rule of each kind in the lists, as the two requests to make for it."""
    out: dict = {}
    for line in (line.strip() for line in lists_text.splitlines()):
        if "name" not in out and (m := NAME_RE.fullmatch(line)):
            out["name"] = {"type": "script", **_sides("name", m.group(1), "/lib.min.js", {m.group(2): "1"}, {})}
        elif "value" not in out and (m := VALUE_RE.fullmatch(line)):
            name, text = m.group(2), m.group(3)
            link = name == "link"
            out["value"] = {"type": "script", **_sides(
                "value", m.group(1), "/lib.min.js",
                {name: f"<https://{text}/>;rel=preconnect" if link else text},
                {name: "<https://fonts.example/>;rel=preconnect" if link else "another value"})}
        elif "redirect" not in out and (m := REDIRECT_RE.fullmatch(line)):
            case = {"type": "script", **_sides("hop", "com", "/script/lib.js", {}, {})}
            # the address the browser is sent on to is one the local server answers; the rule looks for
            # its text anywhere in the header
            case["with"]["redirect"] = f"http://{case['with']['host']}/landed.js?from={m.group(1)}example"
            case["without"]["redirect"] = f"http://{case['without']['host']}/landed.js"
            out["redirect"] = case
        elif "frame" not in out and (m := FRAME_RE.fullmatch(line)):
            sites = [site for site in m.group(2).split("|") if re.fullmatch(r"[a-z]+", site)]
            if sites:
                out["frame"] = {"type": "frame", "site": sites[0],
                                "with": {"host": "withframe.com", "path": FRAME_PATH,
                                         "headers": {m.group(1): "FRA56-P1"}},
                                "without": {"host": "plainframe.com", "path": FRAME_PATH, "headers": {}}}
    return {kind: out[kind] for kind in KINDS if kind in out}


def page_host(found: dict) -> str:
    """The site of the page that asks: one the frame rule is for."""
    return f"hdr-check.{found.get('frame', {}).get('site', 'info')}"


def hosts(found: dict) -> list[str]:
    return [page_host(found)] + [case[side]["host"] for case in found.values() for side in SIDES]


def page_html(found: dict) -> str:
    asks = "".join(f"{case['type']}({json.dumps(f'{kind}:{side}')}, "
                   f"{json.dumps('http://' + case[side]['host'] + case[side]['path'])});"
                   for kind, case in found.items() for side in SIDES)
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron header check</title></head><body>'
            "<script>const results = {};"
            # a frame that was loaded says so itself
            "addEventListener('message', (e) => { if (typeof e.data === 'string') results[e.data] = 'loaded'; });"
            "function script(key, src) { const s = document.createElement('script'); s.src = src;"
            " s.onload = () => { results[key] = 'loaded'; }; s.onerror = () => { results[key] = 'blocked'; };"
            " document.head.appendChild(s); }"
            "function frame(key, src) { results[key] = 'blocked'; const f = document.createElement('iframe');"
            " f.src = src; document.body.appendChild(f); }"
            f"{asks}"
            "addEventListener('load', () => setTimeout(() => "
            f"fetch('/result', {{method: 'POST', body: JSON.stringify(results)}}), {REPORT_AFTER_MS}));"
            "</script></body></html>")


def answer(found: dict, host: str, target: str) -> tuple[int, dict, bytes]:
    """What the local server answers a request with: the status, the headers and the body."""
    path = urllib.parse.urlsplit(target).path
    html = {"Content-Type": "text/html; charset=utf-8"}
    script = {"Content-Type": "text/javascript"}
    if host == page_host(found) and path == "/page.html":
        return 200, html, page_html(found).encode()
    for kind, case in found.items():
        for side in SIDES:
            asked = case[side]
            if host != asked["host"]:
                continue
            if target == asked["path"]:
                if "redirect" in asked:
                    return 302, {**asked["headers"], "Location": asked["redirect"]}, b""
                if case["type"] == "frame":
                    body = ('<!doctype html><meta charset="utf-8"><title>frame</title>'
                            f'<script>parent.postMessage("{kind}:{side}", "*");</script>')
                    return 200, {**html, **asked["headers"]}, body.encode()
                return 200, {**script, **asked["headers"]}, b"// loaded\n"
            if "redirect" in asked and path == urllib.parse.urlsplit(asked["redirect"]).path:
                return 200, script, b"// landed\n"
    return 404, {"Content-Type": "text/plain"}, b"not found"


def problems(mode: str, found: dict, results: dict | None) -> list[str]:
    if mode not in MODES:
        raise ValueError(mode)
    on = mode == "native"
    out = []
    for kind in found:
        with_header, without = ((results or {}).get(f"{kind}:{side}") for side in SIDES)
        if with_header is None or without is None:
            out.append(f"{kind}: the page did not say what became of it")
        elif without != "loaded":
            out.append(f"{kind}: the answer without the header was stopped")
        elif on and with_header != "blocked":
            out.append(f"{kind}: the answer with the header was let through")
        elif not on and with_header != "loaded":
            out.append(f"{kind}: the answer with the header was stopped though blocking is off here")
    return out


class Server:
    def __init__(self, found: dict):
        self.results: dict | None = None
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status: int, headers: dict, body: bytes):
                self.send_response(status)
                for name, value in {**headers, "Cache-Control": "no-store", "Content-Length": str(len(body))}.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                host = (self.headers.get("Host") or "").split(":")[0]
                if host == "127.0.0.1" and self.path == "/warm.html":
                    self._send(200, {"Content-Type": "text/html; charset=utf-8"}, WARM_HTML.encode())
                else:
                    self._send(*answer(found, host, self.path))

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if self.path != "/result" or length > 65536:
                    self._send(404, {"Content-Type": "text/plain"}, b"refused")
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeError):
                    data = None
                if isinstance(data, dict):
                    server.results = data
                self._send(200, {"Content-Type": "text/plain"}, b"ok")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def run_mode(browser: Path, work: Path, found: dict, mode: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix=f"header-{mode}-", dir=work))
    results = None
    with Server(found) as server:
        proc = _launch(browser, profile, server.port, hosts(found), native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    allow = [page_host(found), "", "ads", "allow", False]
                    ws.call("Runtime.evaluate",
                            expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                # the engine loads when the first page asks for it: let one page go by first
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            _navigate(port, f"http://{page_host(found)}/page.html")
            deadline = time.monotonic() + RESULT_TIMEOUT_S
            while server.results is None and time.monotonic() < deadline:
                time.sleep(0.2)
            results = server.results
        except (OSError, RuntimeError, ValueError) as e:
            print(f"{mode}: {e}", file=sys.stderr)
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    found_problems = problems(mode, found, results)
    for kind in found:
        mine = [p for p in found_problems if p.startswith(f"{kind}: ")]
        sides = ", ".join(f"{side} the header {(results or {}).get(f'{kind}:{side}', 'no word')}" for side in SIDES)
        print(f"{'PASS' if not mine else 'FAIL'}  {mode} {kind}: {sides}")
    return [f"{mode} {p}" for p in found_problems]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    found = cases(lists_file.read_text(encoding="utf-8"))
    missing = [kind for kind in KINDS if kind not in found]
    if missing:
        print(f"HEADER CHECK: FAILED (the lists hold no rule the check can use of the kind: {', '.join(missing)})")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    found_problems = [p for mode in MODES for p in run_mode(a.browser.resolve(), a.work, found, mode)]
    for problem in found_problems:
        print(problem)
    print("HEADER CHECK: PASSED" if not found_problems else f"HEADER CHECK: FAILED ({len(found_problems)} problem(s))")
    return 0 if not found_problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
