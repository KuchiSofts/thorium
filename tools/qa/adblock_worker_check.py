#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the scripts workers start from, prefetches and WebSockets, checked offline
(ROADMAP P5.27, P5.29).

Some requests are not made by a page's document the usual way: the script a worker or a shared worker is
started from, the scripts a service worker is started from and imports (it may import them from another
site, which is how push-advertising networks get onto a site), what a page asks the browser to fetch
ahead of time (`<link rel="prefetch">`), and WebSocket connections, which are not requests for a file at
all. This check serves a page from a local server on 127.0.0.1 (a service worker needs a trustworthy
address; host-resolver rules send the ad host there too and make every other name fail) that starts each
of them:

    a worker and a shared worker whose script has a path the lists block on every site (the first plain
        rule of that kind in the bundled lists): neither script is fetched, and neither worker starts
    a service worker of the site whose script imports one from an ad host: the import is not fetched,
        and the service worker is still registered
    a prefetch of a script on the ad host: not fetched
    a WebSocket to the ad host: not opened, and the server never hears of it
    a WebSocket to the site itself: opens, in every mode (the server answers the handshake)
    a plain worker, and a module worker that imports another file: both start, in every mode

in three modes: control (native blocking off: everything is fetched and runs), native, and site-off (ads
allowed on the site: as control).

    py -3 -I tools/qa/adblock_worker_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
"""
import argparse
import base64
import hashlib
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
from tools.build import mv2_check  # noqa: E402
from tools.qa import adblock_syntax_check as syntax  # noqa: E402
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
SITE = "127.0.0.1"
AD_HOST = mv2_check.AD_HOST                # EasyList blocks every request to it
PLAIN_PATH_RE = re.compile(r"/[a-z0-9_/-]+\.js")   # a rule that is nothing but a script's path
RESULT_TIMEOUT_S = 60
REPORT_AFTER_MS = 5000


def websocket_accept(key: str) -> str:
    """The Sec-WebSocket-Accept value that answers a handshake's Sec-WebSocket-Key (RFC 6455)."""
    digest = hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def blocked_path(lists_text: str) -> str | None:
    """The first rule that is only a script's path: the lists block it on every site."""
    for line in lists_text.splitlines():
        if PLAIN_PATH_RE.fullmatch(line.strip()):
            return line.strip()
    return None


def service_worker_js() -> str:
    """A service worker that imports a script from the ad host and goes on without it."""
    return (f"try {{ importScripts('http://{AD_HOST}/sw-import.js'); }} catch (e) {{ self.importRefused = true; }}\n"
            "self.addEventListener('install', () => self.skipWaiting());\n")


def page_html(path: str) -> str:
    """The page that starts every kind of worker and a prefetch. It reports to /result/page."""
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron worker check</title>'
            f'<link rel="prefetch" href="http://{AD_HOST}/prefetch.js" as="script"></head><body><p>workers</p>'
            "<script>const out = {plainWorker: false, moduleWorker: false, registered: false, "
            "blockedWorker: 'silent', blockedShared: 'silent', plainSocket: 'silent', adSocket: 'silent'};"
            "const watch = (name, socket) => {"
            "socket.onopen = () => { out[name] = 'open'; socket.close(); };"
            "socket.onerror = () => { if (out[name] !== 'open') { out[name] = 'failed'; } }; };"
            "try { watch('plainSocket', new WebSocket('ws://' + location.host + '/plain-socket')); }"
            " catch (e) { out.plainSocket = 'failed'; }"
            f"try {{ watch('adSocket', new WebSocket('ws://{AD_HOST}/ad-socket')); }}"
            " catch (e) { out.adSocket = 'failed'; }"
            "const plain = new Worker('/plain-worker.js');"
            "plain.onmessage = () => { out.plainWorker = true; };"
            "const module = new Worker('/module-worker.js', {type: 'module'});"
            "module.onmessage = (e) => { out.moduleWorker = e.data === 'ran with its import'; };"
            f"const worker = new Worker('{path}?kind=worker');"
            "worker.onmessage = () => { out.blockedWorker = 'ran'; };"
            "worker.onerror = () => { out.blockedWorker = 'failed'; };"
            f"try {{ const shared = new SharedWorker('{path}?kind=shared');"
            "shared.port.onmessage = () => { out.blockedShared = 'ran'; };"
            "shared.onerror = () => { out.blockedShared = 'failed'; };"
            "shared.port.start(); } catch (e) { out.blockedShared = 'failed'; }"
            "navigator.serviceWorker.register('/service.js').then(() => { out.registered = true; }, () => {});"
            "addEventListener('load', () => setTimeout(() => fetch('/result/page', {method: 'POST', "
            f"body: JSON.stringify(out)}}), {REPORT_AFTER_MS}));"
            "</script></body></html>")


def problems(mode: str, path: str, result: dict | None, seen: dict) -> list[str]:
    if mode not in MODES:
        raise ValueError(mode)
    if not isinstance(result, dict):
        return ["the page gave no result"]
    on = mode == "native"
    off = "though blocking is off here"
    out = []
    if not result.get("plainWorker"):
        out.append("the plain worker did not start")
    if not result.get("moduleWorker"):
        out.append("the module worker did not start, or did not get the file it imports")
    if not result.get("registered"):
        out.append("the site's own service worker was not registered")
    if result.get("plainSocket") != "open":
        out.append(f"the plain WebSocket to the site itself did not open ({result.get('plainSocket')})")
    heard, state = "/ad-socket" in seen.get("ad", []), result.get("adSocket")
    if on and (heard or state == "open"):
        out.append(f"the WebSocket to the ad host was opened (the server heard of it: {heard}, socket: {state})")
    if not on and (not heard or state != "open"):
        out.append(f"the WebSocket to the ad host did not open {off} (the server heard of it: {heard}, socket: {state})")
    asked = seen.get("page", {}).get(path, [])
    for kind, flag, what in (("kind=worker", "blockedWorker", "worker"), ("kind=shared", "blockedShared", "shared worker")):
        fetched, state = kind in asked, result.get(flag)
        if on and (fetched or state == "ran"):
            out.append(f"the {what}'s script {path} was fetched or ran (fetched: {fetched}, worker: {state})")
        if not on and (not fetched or state != "ran"):
            out.append(f"the {what} did not start {off} (fetched: {fetched}, worker: {state})")
    for ad_path, what in (("/sw-import.js", "the script the service worker imports from the ad host"),
                          ("/prefetch.js", "the prefetch of a script on the ad host")):
        fetched = ad_path in seen.get("ad", [])
        if on and fetched:
            out.append(f"{what} was fetched")
        if not on and not fetched:
            out.append(f"{what} was not fetched {off}")
    return out


class PageServer:
    def __init__(self, path: str):
        self.result: dict | None = None
        self.ad: set = set()
        self.page: dict = {}
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if self.path != "/result/page" or length > 65536:
                    self._send(404, "text/plain", b"refused")
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeError):
                    data = None
                if isinstance(data, dict):
                    server.result = data
                self._send(200, "text/plain", b"ok")

            def _open_socket(self):
                """Answers a WebSocket handshake, then waits until the page closes the connection."""
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", websocket_accept(self.headers.get("Sec-WebSocket-Key", "")))
                self.end_headers()
                self.close_connection = True
                self.connection.settimeout(10)
                try:
                    while self.rfile.read(1):
                        pass
                except OSError:
                    pass

            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                host = (self.headers.get("Host") or "").split(":")[0]
                script, html = "text/javascript", "text/html; charset=utf-8"
                socket = (self.headers.get("Upgrade") or "").lower() == "websocket"
                if host == AD_HOST:
                    server.ad.add(url.path)
                    if socket:
                        self._open_socket()
                    else:
                        self._send(200, script, b"self.adScript = true;")
                elif host == SITE and socket:
                    server.page.setdefault(url.path, []).append(url.query)
                    self._open_socket()
                elif host != SITE:
                    self._send(404, "text/plain", b"not found")
                elif url.path == "/warm.html":
                    self._send(200, html, WARM_HTML.encode())
                else:
                    server.page.setdefault(url.path, []).append(url.query)
                    if url.path == "/kinds.html":
                        self._send(200, html, page_html(path).encode())
                    elif url.path == "/plain-worker.js":
                        self._send(200, script, b"postMessage('ran');")
                    elif url.path == "/module-worker.js":
                        self._send(200, script, b"import {said} from './module-part.js'; postMessage(said);")
                    elif url.path == "/module-part.js":
                        self._send(200, script, b"export const said = 'ran with its import';")
                    elif url.path == "/service.js":
                        self._send(200, script, service_worker_js().encode())
                    elif url.path == path and url.query == "kind=shared":
                        self._send(200, script, b"onconnect = (e) => e.ports[0].postMessage('ran');")
                    elif url.path == path:
                        self._send(200, script, b"postMessage('ran');")
                    else:
                        self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def seen(self) -> dict:
        return {"ad": sorted(self.ad), "page": {p: list(q) for p, q in self.page.items()}}

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def run_mode(browser: Path, work: Path, path: str, mode: str) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"worker-{mode}-", dir=work))
    result, seen = None, {"ad": [], "page": {}}
    with PageServer(path) as server:
        proc = syntax._launch(browser, profile, server.port, [AD_HOST], native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    allow = [SITE, "", "ads", "allow", False]
                    ws.call("Runtime.evaluate",
                            expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                # the engine loads when the first page asks for it: let one page go by first
                _open(port, f"http://{SITE}:{server.port}/warm.html")
                time.sleep(4)
            _open(port, f"http://{SITE}:{server.port}/kinds.html")
            deadline = time.monotonic() + RESULT_TIMEOUT_S
            while server.result is None and time.monotonic() < deadline:
                time.sleep(0.2)
            time.sleep(1)
            result, seen = server.result, server.seen()
        except (OSError, RuntimeError, ValueError) as e:
            print(f"{mode}: {e}", file=sys.stderr)
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    found = problems(mode, path, result, seen)
    return {"mode": mode, "passed": not found, "problems": found, "result": result, "seen": seen}


def run_all(browser: Path, work: Path, lists_file: Path) -> dict:
    path = blocked_path(lists_file.read_text(encoding="utf-8"))
    if not path:
        raise SystemExit(f"{lists_file} has no plain rule for a script's path")
    work.mkdir(parents=True, exist_ok=True)
    return {"blocked_path": path, "ad_host": AD_HOST,
            "results": [run_mode(browser, work, path, mode) for mode in MODES]}


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
    print("WORKER CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
