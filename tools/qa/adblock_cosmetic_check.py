#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, scriptlets and hide rules, checked end to end and offline (ROADMAP P5.20).

The check uses the browser's own bundled lists. It looks in them for a site that has both a simple
scriptlet rule (`site##+js(set, name, true)`) and a simple hide rule (`site##.class` or `site###id`),
serves a small page under that site's name from a local server (host-resolver rules send the name to
127.0.0.1 and make every other name fail), and loads it on throwaway profiles:

    control    native blocking off: the property is not set, the elements show
    native     native blocking on: the scriptlet ran before the page's first script (the property has
               the rule's value) and the site's element is hidden; so are two elements with class names
               from generic rules (`##.name`), one there from the start and one the page adds a second
               after it has loaded
    frame      the same page inside a frame of a page on 127.0.0.1: all of it applies in the frame too
    site-off   ads allowed on that site (the per-site switch): nothing is touched

    py -3 -I tools/qa/adblock_cosmetic_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
"""
import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "frame", "site-off")
MARKER = "! thoron-list: "
SCRIPTLET_RE = re.compile(r"([a-z0-9.-]+)##\+js\((?:set|set-constant), ([A-Za-z_][A-Za-z0-9_]*), (true|false)\)")
HIDE_RE = re.compile(r"([a-z0-9.-]+)##([.#][A-Za-z][A-Za-z0-9_-]*)")
GENERIC_RE = re.compile(r"##\.([a-z][a-z0-9-]{5,40})")
# The test site's name ends up in reports: leave out names that do not belong there.
NOT_FOR_REPORTS = ("porn", "sex", "xxx", "hentai", "adult", "tube", "cam", "nude", "fap", "milf", "erotic",
                   "xnxx", "gay", "feet", "lewd", "rule34", "hamster", "pirate")
RESULT_TIMEOUT_S = 60
LATE_ELEMENT_MS = 1000     # the page adds its second generic element this long after it has loaded
REPORT_AFTER_MS = 6000     # and reports this long after: the browser looks again 1 s and 3 s after the load
NO_HTTPS_FIRST = "HttpsUpgrades,HttpsFirstBalancedModeAutoEnable"
MAX_CANDIDATES = 5


def generic_classes(lists_text: str) -> list[str]:
    """The first two class names with a plain generic hide rule (`##.name`)."""
    names = []
    for line in lists_text.splitlines():
        if (m := GENERIC_RE.fullmatch(line.strip())) and m.group(1) not in names:
            names.append(m.group(1))
            if len(names) == 2:
                break
    return names


def candidates(lists_text: str) -> list[dict]:
    """Sites with a simple scriptlet rule and a simple hide rule, by name, each with the two class names
    for the generic part of the check. Nothing without two generic class rules."""
    generic = generic_classes(lists_text)
    if len(generic) < 2:
        return []
    scriptlets, hides = {}, {}
    for line in lists_text.splitlines():
        line = line.strip()
        if m := SCRIPTLET_RE.fullmatch(line):
            scriptlets.setdefault(m.group(1), (m.group(2), m.group(3)))
        elif m := HIDE_RE.fullmatch(line):
            hides.setdefault(m.group(1), m.group(2))
    out = []
    for host in sorted(set(scriptlets) & set(hides)):
        if any(word in host for word in NOT_FOR_REPORTS):
            continue
        out.append({"host": host, "property": scriptlets[host][0], "value": scriptlets[host][1],
                    "selector": hides[host], "generic": generic[0], "late": generic[1]})
    return out


def page_html(c: dict) -> str:
    prop, sel = json.dumps(c["property"]), json.dumps(c["selector"])
    attr = f'id="{c["selector"][1:]}"' if c["selector"].startswith("#") else f'class="{c["selector"][1:]}"'
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron cosmetic check</title>'
            f"<script>window.__early = String(window[{prop}]);</script></head><body>"
            f'<div {attr} style="height:40px;width:200px">ad</div>'
            f'<div class="{c["generic"]}" id="thoron-generic" style="height:40px;width:200px">ad</div>'
            "<script>const gone = (e) => !!e && getComputedStyle(e).display === 'none';"
            "addEventListener('load', () => {"
            "setTimeout(() => { const late = document.createElement('div'); late.id = 'thoron-late';"
            f"late.className = {json.dumps(c['late'])}; late.style.height = '40px'; late.textContent = 'ad';"
            f"document.body.appendChild(late); }}, {LATE_ELEMENT_MS});"
            "setTimeout(() => {"
            f"const el = document.querySelector({sel});"
            "fetch('/result', {method: 'POST', body: JSON.stringify({early: window.__early, "
            "hidden: gone(el), height: el.offsetHeight, generic: gone(document.getElementById('thoron-generic')), "
            "late: gone(document.getElementById('thoron-late'))})});"
            f"}}, {REPORT_AFTER_MS}); }});</script></body></html>")


def parent_html(host: str) -> str:
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron cosmetic check, frame</title></head>'
            f'<body><iframe src="http://{host}/check.html?frame=1" width="400" height="200"></iframe></body></html>')


# Opened first so the engine is loaded before the page that is judged. It must not report anything: a late
# report from a warm-up page would be taken for the result of the real one.
WARM_HTML = ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron cosmetic check, warm-up</title></head>'
             "<body><p>warm-up</p></body></html>")


def problems(mode: str, c: dict, result: dict | None) -> list[str]:
    if not isinstance(result, dict):
        return ["the page gave no result"]
    early, hidden = result.get("early"), bool(result.get("hidden"))
    generic, late = bool(result.get("generic")), bool(result.get("late"))
    out = []
    if mode in ("native", "frame"):
        if early != c["value"]:
            out.append(f"the scriptlet did not run before the page's first script: {c['property']} was {early!r}, "
                       f"not {c['value']!r}")
        if not hidden:
            out.append(f"the element {c['selector']} is not hidden")
        if not generic:
            out.append(f"the element of the generic rule ##.{c['generic']} is not hidden")
        if not late:
            out.append(f"the element of the generic rule ##.{c['late']}, added later by the page, is not hidden")
    elif mode in ("control", "site-off"):
        if early != "undefined":
            out.append(f"a scriptlet ran though blocking is off here: {c['property']} was {early!r}")
        if hidden:
            out.append(f"the element {c['selector']} is hidden though blocking is off here")
        if generic or late:
            out.append("an element of a generic rule is hidden though blocking is off here")
    else:
        raise ValueError(mode)
    return out


class PageServer:
    def __init__(self, c: dict):
        self.result: dict | None = None
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

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if self.path != "/result" or length > 65536:
                    self._send(404, "text/plain", b"refused")
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeError):
                    data = None
                if isinstance(data, dict):
                    server.result = data
                self._send(200, "text/plain", b"ok")

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                host = (self.headers.get("Host") or "").split(":")[0]
                if path == "/check.html" and host == c["host"]:
                    self._send(200, "text/html; charset=utf-8", page_html(c).encode())
                elif path == "/parent.html" and host == "127.0.0.1":
                    self._send(200, "text/html; charset=utf-8", parent_html(c["host"]).encode())
                elif path == "/warm.html" and host == "127.0.0.1":
                    self._send(200, "text/html; charset=utf-8", WARM_HTML.encode())
                else:
                    self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _launch(browser: Path, profile: Path, port: int, host: str, native: bool) -> subprocess.Popen:
    # The test page is plain http, and the browser would first try https for a top-level visit: both
    # features that do that are switched off.
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            f"--host-resolver-rules=MAP {host} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
    if native:
        args.append("--enable-features=ThoronNativeAdblock")
    return subprocess.Popen(args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def run_mode(browser: Path, work: Path, c: dict, mode: str) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"cosmetic-{mode}-", dir=work))
    with PageServer(c) as server:
        proc = _launch(browser, profile, server.port, c["host"], native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    allow = [c["host"], "", "ads", "allow", False]
                    ws.call("Runtime.evaluate", expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                # the engine loads when the first page asks for it: let one page go by first
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            url = (f"http://127.0.0.1:{server.port}/parent.html" if mode == "frame"
                   else f"http://{c['host']}/check.html")
            _open(port, url)
            deadline = time.monotonic() + RESULT_TIMEOUT_S
            while server.result is None and time.monotonic() < deadline:
                time.sleep(0.2)
            result = server.result
        except (OSError, RuntimeError, ValueError) as e:
            result = None
            print(f"{mode}: {e}", file=sys.stderr)
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    found = problems(mode, c, result)
    return {"mode": mode, "passed": not found, "problems": found, "result": result}


def run_all(browser: Path, work: Path, lists_file: Path) -> dict:
    found = candidates(lists_file.read_text(encoding="utf-8"))
    if not found:
        raise SystemExit(f"{lists_file} has no site with both a simple scriptlet rule and a simple hide rule")
    work.mkdir(parents=True, exist_ok=True)
    for c in found[:MAX_CANDIDATES]:
        control = run_mode(browser, work, c, "control")
        if control["result"] is None:   # the name cannot be used (the browser forces https for it, say)
            continue
        results = [control] + [run_mode(browser, work, c, mode) for mode in MODES if mode != "control"]
        return {"site": c, "results": results}
    raise SystemExit("no candidate site could be loaded at all, even with blocking off")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    parser.add_argument("--lists", type=Path, help="bundled lists (default: thoron_adblock_lists.txt next to it)")
    a = parser.parse_args(argv)
    out = run_all(a.browser, a.work, a.lists or a.browser.parent / "thoron_adblock_lists.txt")
    print(json.dumps(out, indent=2))
    ok = all(r["passed"] for r in out["results"])
    print("COSMETIC CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
