#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, preloads announced by "103 Early Hints", checked end to end and offline (ROADMAP P5.28).

While a server works on a page, it may send "103 Early Hints" with `Link: <...>; rel=preload` headers, and
the browser fetches those files at once, before the page arrives and without asking the page. The check
serves a page that announces two preloads this way: a script from an ad host the bundled lists block (the
first plain host rule of EasyList) and a style sheet from a plain host. The names are sent to a local
server by host-resolver rules; every other name fails, so nothing leaves the PC. The server writes down
which hosts were asked.

    native     native blocking on: the ad host is never asked, the plain host is
    control    native blocking off: both are asked (this also shows the browser acts on early hints)
    site-off   ads allowed on the page's site: both are asked

    py -3 -I tools/qa/adblock_earlyhints_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
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
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import NOT_FOR_REPORTS, WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch, _navigate  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
PAGE_HOST = "hints-check.test"
PLAIN_HOST = "plain-hints.test"
AD_PATH = "/early.js"
PLAIN_PATH = "/early.css"
HINT_WAIT_S = 1.5        # the page itself comes this long after its early hints
SETTLE_S = 4.0
HOST_RULE = re.compile(r"\|\|([a-z0-9-]+(?:\.[a-z0-9-]+)+)\^")


def ad_host(lists_text: str) -> str | None:
    """The first rule of EasyList that blocks a whole host and nothing more."""
    current = ""
    for line in (line.strip() for line in lists_text.splitlines()):
        if line.startswith("! thoron-list: "):
            current = line.removeprefix("! thoron-list: ").strip()
        elif current == "easylist" and (m := HOST_RULE.fullmatch(line)) and \
                not any(word in m.group(1) for word in NOT_FOR_REPORTS):
            return m.group(1)
    return None


def early_hints(ad_url: str, plain_url: str) -> bytes:
    return ("HTTP/1.1 103 Early Hints\r\n"
            f"Link: <{ad_url}>; rel=preload; as=script\r\n"
            f"Link: <{plain_url}>; rel=preload; as=style\r\n\r\n").encode()


def problems(native: bool, asked: dict, host: str) -> list[str]:
    out = []
    if not asked.get("page"):
        out.append("the page itself did not load")
    if native and asked.get(host):
        out.append("the preload from the ad host was made")
    if not native and not asked.get(host):
        out.append("the preload from the ad host was not made, though blocking is off")
    if not asked.get(PLAIN_HOST):
        out.append("the plain preload was not made")
    return out


class Server:
    def __init__(self, host: str):
        self.asked = {"page": False, host: False, PLAIN_HOST: False}
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, ctype: str, body: bytes):
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                if name == "127.0.0.1" and self.path == "/warm.html":
                    self._send("text/html; charset=utf-8", WARM_HTML.encode())
                elif name == PAGE_HOST and self.path == "/page.html":
                    self.wfile.write(early_hints(f"http://{host}{AD_PATH}", f"http://{PLAIN_HOST}{PLAIN_PATH}"))
                    self.wfile.flush()
                    time.sleep(HINT_WAIT_S)
                    server.asked["page"] = True
                    self._send("text/html; charset=utf-8",
                               b"<!doctype html><title>Thoron early hints check</title><p>page</p>")
                elif name == host and self.path == AD_PATH:
                    server.asked[host] = True
                    self._send("text/javascript", b"// ad\n")
                elif name == PLAIN_HOST and self.path == PLAIN_PATH:
                    server.asked[PLAIN_HOST] = True
                    self._send("text/css", b"p{color:inherit}\n")
                else:
                    self._send("text/plain", b"not here")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def run_mode(browser: Path, work: Path, host: str, mode: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix=f"hints-{mode}-", dir=work))
    found: list[str] = []
    with Server(host) as server:
        # Sites send early hints over HTTP/2 or 3; the local server speaks HTTP/1.1, for which Chromium
        # reads them only with this feature. What the browser then does with them is the same.
        proc = _launch(browser, profile, server.port, [PAGE_HOST, PLAIN_HOST, host], native=mode != "control",
                       enable=("EnableEarlyHintsOnHttp11",))
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
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            _navigate(port, f"http://{PAGE_HOST}/page.html")
            time.sleep(HINT_WAIT_S + SETTLE_S)
            found = problems(mode == "native", dict(server.asked), host)
        except (OSError, RuntimeError, ValueError) as e:
            found = [f"the run failed: {e}"]
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    print(f"{'PASS' if not found else 'FAIL'}  {mode}: ad host {'asked' if server.asked.get(host) else 'not asked'}, "
          f"plain host {'asked' if server.asked.get(PLAIN_HOST) else 'not asked'}" + (f"; {'; '.join(found)}" if found else ""))
    return [f"{mode}: {p}" for p in found]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    host = ad_host(lists_file.read_text(encoding="utf-8"))
    if host is None:
        print("EARLY HINTS CHECK: FAILED (EasyList holds no plain host rule)")
        return 1
    print(f"    ad host: {host}")
    a.work.mkdir(parents=True, exist_ok=True)
    found = [p for mode in MODES for p in run_mode(a.browser.resolve(), a.work, host, mode)]
    for problem in found:
        print(problem)
    print("EARLY HINTS CHECK: PASSED" if not found else f"EARLY HINTS CHECK: FAILED ({len(found)} problem(s))")
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
