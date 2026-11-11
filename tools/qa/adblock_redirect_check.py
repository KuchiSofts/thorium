#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, redirects, checked end to end and offline (ROADMAP P5.25).

A request the lists allow can be redirected by its server to something they block, or to an address with a
tracking parameter. The native blocker looks at every redirect again. This check serves a page from a local
server (host-resolver rules send two names to 127.0.0.1 and make every other name fail) whose requests all
go through a redirect first:

    to the ad host      a script, an image, a fetch, a frame, and a script through two redirects: none may
                        reach the ad host, and the script must not run
    to a parameter      a fetch and a frame redirected to an address with a parameter the lists take out
                        (`$removeparam`): the server is asked for the clean address
    harmless            a script and an image redirected within the site: both must still load, in every mode

and opens two more addresses in tabs of their own:

    landing             a redirect to a page address with the parameter: the server is asked for the clean
                        address, and the page itself sees the clean address
    insist              a site that answers the clean address by sending the browser back to the one with
                        the parameter: the page must still load (the browser gives way after one try)

in three modes: control (native blocking off: every redirect is followed as it is), native, and site-off
(ads allowed on the site: as control).

    py -3 -I tools/qa/adblock_redirect_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
"""
import argparse
import http.server
import json
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.build import mv2_check  # noqa: E402
from tools.qa import adblock_syntax_check as syntax  # noqa: E402
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
PAGE_HOST = "redirect-check.test"          # a site no list names
AD_HOST = mv2_check.AD_HOST                # EasyList blocks every request to it
AD_PATHS = ("/ad.js", "/ad.gif", "/data.json", "/frame.html", "/ad2.js")
CLEANED_PATHS = ("/data.json", "/inner.html", "/landing.html")
RESULTS = ("page", "landing", "insist")
RESULT_TIMEOUT_S = 60
REPORT_AFTER_MS = 2500
# where each hop sends the browser; {dirty} is the query with the parameter. The names say nothing about
# ads, so no list rule matches the hop itself.
HOPS = {
    "far-script": f"http://{AD_HOST}/ad.js",
    "far-image": f"http://{AD_HOST}/ad.gif",
    "far-data": f"http://{AD_HOST}/data.json",
    "far-frame": f"http://{AD_HOST}/frame.html",
    "chain": "/hop?to=far-chain",
    "far-chain": f"http://{AD_HOST}/ad2.js",
    "clean-data": "/data.json?{dirty}",
    "clean-frame": "/inner.html?{dirty}",
    "landing": "/landing.html?{dirty}",
    "ok-script": "/ok.js",
    "ok-image": "/shape.gif",
}


def dirty(name: str) -> str:
    return f"{name}=abc&keep=1"


def hop_target(to: str, name: str) -> str:
    """The Location a hop answers with."""
    return HOPS[to].replace("{dirty}", dirty(name))


def page_html() -> str:
    """The page whose requests all meet a redirect first. It reports to /result/page."""
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron redirect check</title></head><body>'
            '<script src="/hop?to=ok-script"></script>'
            '<script src="/hop?to=far-script"></script>'
            '<script src="/hop?to=chain"></script>'
            '<img id="ok-image" src="/hop?to=ok-image" width="1" height="1" alt="">'
            '<img src="/hop?to=far-image" width="1" height="1" alt="">'
            '<iframe src="/hop?to=far-frame" width="100" height="50"></iframe>'
            '<iframe src="/hop?to=clean-frame" width="100" height="50"></iframe>'
            "<script>fetch('/hop?to=far-data').catch(() => {});"
            "fetch('/hop?to=clean-data').catch(() => {});"
            "addEventListener('load', () => setTimeout(() => fetch('/result/page', {method: 'POST', "
            "body: JSON.stringify({okScript: window.okScript === true, "
            "okImage: document.getElementById('ok-image').naturalWidth > 0, "
            f"adScript: window.adScript === true}})}}), {REPORT_AFTER_MS}));"
            "</script></body></html>")


def report_html(name: str) -> str:
    """A page that reports the address it was loaded with to /result/<name>."""
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f"<title>Thoron redirect check, {name}</title></head><body><p>{name}</p>"
            f"<script>fetch('/result/{name}', {{method: 'POST', "
            "body: JSON.stringify({search: location.search})});</script></body></html>")


def problems(mode: str, name: str, results: dict, seen: dict) -> list[str]:
    if mode not in MODES:
        raise ValueError(mode)
    page = results.get("page")
    if not isinstance(page, dict):
        return ["the page gave no result"]
    on = mode == "native"
    off = "though blocking is off here"
    with_parameter, clean = dirty(name), "keep=1"
    out = []
    # A request that was blocked before its redirect would look like a redirect that was blocked.
    asked = seen.get("page", {}).get("/hop", [])
    out += [f"the hop {to} was never asked for, so its redirect was not judged" for to in HOPS
            if f"to={to}" not in asked]
    for flag, what in (("okScript", "script"), ("okImage", "image")):
        if not page.get(flag):
            out.append(f"a harmless redirect was broken: the {what} redirected within the site did not load")
    reached = [path for path in AD_PATHS if path in seen.get("ad", [])]
    if on:
        out += [f"a redirect reached the ad host: {path}" for path in reached]
        if page.get("adScript"):
            out.append("the ad host's script ran")
    else:
        out += [f"a redirect to the ad host was not followed {off}: {path}"
                for path in AD_PATHS if path not in reached]
        if not page.get("adScript"):
            out.append(f"the ad host's script did not run {off}")
    want = clean if on else with_parameter
    for path in CLEANED_PATHS:
        asked = seen.get("page", {}).get(path)
        if not asked or any(query != want for query in asked):
            out.append(f"after a redirect the server was asked for {path} with {asked}, not {want!r}")
    landing = (results.get("landing") or {}).get("search")
    if landing != "?" + want:
        out.append(f"after a redirect the page sees the address ending {landing!r}, not {'?' + want!r}")
    insist = (results.get("insist") or {}).get("search")
    if insist != "?" + with_parameter:
        out.append(f"the site that insists on its parameter did not load as it wants: {insist!r}")
    elif on and clean not in seen.get("page", {}).get("/insist.html", []):
        out.append("the site that insists on its parameter was never asked for the clean address")
    return out


class PageServer:
    def __init__(self, name: str):
        self.results: dict = {}
        self.ad: set = set()
        self.page: dict = {}
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes, location: str | None = None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                if location:
                    self.send_header("Location", location)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                kind = self.path.removeprefix("/result/")
                if not self.path.startswith("/result/") or kind not in RESULTS or length > 65536:
                    self._send(404, "text/plain", b"refused")
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeError):
                    data = None
                if isinstance(data, dict):
                    server.results[kind] = data
                self._send(200, "text/plain", b"ok")

            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                host = (self.headers.get("Host") or "").split(":")[0]
                html = "text/html; charset=utf-8"
                if host == AD_HOST:
                    server.ad.add(url.path)
                    if url.path.endswith(".js"):
                        self._send(200, "text/javascript", b"window.adScript = true;")
                    elif url.path.endswith(".gif"):
                        self._send(200, "image/gif", syntax.GIF)
                    elif url.path.endswith(".json"):
                        self._send(200, "application/json", b"{}")
                    else:
                        self._send(200, html, b"<!doctype html><title>ad</title><p>ad</p>")
                elif host == PAGE_HOST:
                    server.page.setdefault(url.path, []).append(url.query)
                    to = urllib.parse.parse_qs(url.query).get("to", [""])[0]
                    if url.path == "/hop" and to in HOPS:
                        self._send(302, "text/plain", b"redirect", location=hop_target(to, name))
                    elif url.path == "/page.html":
                        self._send(200, html, page_html().encode())
                    elif url.path == "/landing.html":
                        self._send(200, html, report_html("landing").encode())
                    elif url.path == "/insist.html":
                        if name + "=" in url.query:
                            self._send(200, html, report_html("insist").encode())
                        else:   # this site wants its parameter back
                            self._send(302, "text/plain", b"redirect", location=f"/insist.html?{dirty(name)}")
                    elif url.path == "/inner.html":
                        self._send(200, html, b"<!doctype html><title>inner</title><p>inner</p>")
                    elif url.path == "/data.json":
                        self._send(200, "application/json", b"{}")
                    elif url.path == "/ok.js":
                        self._send(200, "text/javascript", b"window.okScript = true;")
                    elif url.path == "/shape.gif":
                        self._send(200, "image/gif", syntax.GIF)
                    else:
                        self._send(404, "text/plain", b"not found")
                elif url.path == "/warm.html" and host == "127.0.0.1":
                    self._send(200, html, WARM_HTML.encode())
                else:
                    self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def seen(self) -> dict:
        return {"ad": sorted(self.ad), "page": {path: list(queries) for path, queries in self.page.items()}}

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def run_mode(browser: Path, work: Path, name: str, mode: str) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"redirect-{mode}-", dir=work))
    results, seen = {}, {"ad": [], "page": {}}
    with PageServer(name) as server:
        proc = syntax._launch(browser, profile, server.port, [PAGE_HOST, AD_HOST], native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    allow = [PAGE_HOST, "", "ads", "allow", False]
                    ws.call("Runtime.evaluate",
                            expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                # the engine loads when the first page asks for it: let one page go by first
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            for path in ("/page.html", "/hop?to=landing", f"/insist.html?{dirty(name)}"):
                syntax._navigate(port, f"http://{PAGE_HOST}{path}")
            deadline = time.monotonic() + RESULT_TIMEOUT_S
            while len(server.results) < len(RESULTS) and time.monotonic() < deadline:
                time.sleep(0.2)
            time.sleep(1)   # the last requests of the page
            results, seen = dict(server.results), server.seen()
        except (OSError, RuntimeError, ValueError) as e:
            print(f"{mode}: {e}", file=sys.stderr)
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    found = problems(mode, name, results, seen)
    return {"mode": mode, "passed": not found, "problems": found, "results": results, "seen": seen}


def run_all(browser: Path, work: Path, lists_file: Path) -> dict:
    case = syntax.cases(lists_file.read_text(encoding="utf-8")).get("removeparam")
    if not case:
        raise SystemExit(f"{lists_file} has no `$removeparam=name` rule for every site")
    work.mkdir(parents=True, exist_ok=True)
    return {"parameter": case["name"], "ad_host": AD_HOST,
            "results": [run_mode(browser, work, case["name"], mode) for mode in MODES]}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    parser.add_argument("--lists", type=Path, help="bundled lists (default: thoron_adblock_lists.txt next to it)")
    a = parser.parse_args(argv)
    browser = a.browser.resolve()
    out = run_all(browser, a.work, a.lists or browser.parent / "thoron_adblock_lists.txt")
    print(json.dumps(out, indent=2))
    ok = all(r["passed"] for r in out["results"])
    print("REDIRECT CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
