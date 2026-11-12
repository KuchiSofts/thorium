#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, pop-ups: the lists' `$popup` rules and the menu's "no pop-ups" switch, checked end to end and
offline (ROADMAP P5.36).

A local server serves a test page under a name of its own (host-resolver rules; every other name fails, so nothing
leaves the PC). The page opens windows the way pop-up ads do, each from a click (a user gesture), so Chromium's own
pop-up blocker lets them through and only the ad blocker decides. The ad address is on the first host EasyList
blocks with a plain `||host^$popup` rule.

    control    native blocking off: window.open() of the ad address opens it
    native     window.open() of the ad address returns null and the ad host is never asked; a link with a target
               to it opens nothing; a blank window sent to it afterwards is closed; a window to a plain host opens;
               the menu counts the three on the page; with "no pop-ups" on for the site, neither a window nor a
               link to the plain host opens
    site-off   ads allowed on the page's site: the ad window opens

    py -3 -I tools/qa/adblock_popup_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import NOT_FOR_REPORTS, WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
PAGE_HOST = "popup-check.test"
PLAIN_HOST = "plain-popup.test"
MENU_URL = "chrome://adblock-menu.top-chrome/"
SETTLE_S = 2.5
POPUP_RULE = re.compile(r"\|\|([a-z0-9-]+(?:\.[a-z0-9-]+)+)\^\$popup")

PAGE_HTML = """<!doctype html><title>Thoron pop-up check</title>
<a id="ad-link" href="AD/link" target="_blank">a link to the ad</a>
<a id="plain-link" href="PLAIN/link.html" target="_blank">a plain link</a>
<script>
window.openAd = () => (window.open('AD/window') ? 'opened' : 'null');
window.openPlain = () => (window.open('PLAIN/window.html') ? 'opened' : 'null');
window.openBlank = () => {
  const w = window.open('about:blank');
  if (!w) return 'null';
  w.location.href = 'AD/later';
  return 'opened';
};
</script>
"""


def popup_host(lists_text: str) -> str | None:
    """The first rule of EasyList that blocks pop-ups to a whole host and nothing more."""
    current = ""
    for line in (line.strip() for line in lists_text.splitlines()):
        if line.startswith("! thoron-list: "):
            current = line.removeprefix("! thoron-list: ").strip()
        elif current == "easylist" and (m := POPUP_RULE.fullmatch(line)) and \
                not any(word in m.group(1) for word in NOT_FOR_REPORTS):
            return m.group(1)
    return None


def page_html(host: str) -> str:
    return PAGE_HTML.replace("AD/", f"http://{host}/").replace("PLAIN/", f"http://{PLAIN_HOST}/")


def opened_problems(seen: dict, host: str) -> list[str]:
    """control and site-off: the blocker lets the ad window open."""
    asked = {tuple(item) for item in seen.get("asked", [])}
    if seen.get("ad") == "opened" and (host, "/window") in asked:
        return []
    return [f"the ad window did not open (window.open: {seen.get('ad')}), though the blocker should let it"]


def native_problems(seen: dict, host: str) -> list[str]:
    asked = {tuple(item) for item in seen.get("asked", [])}
    out = []
    if seen.get("ad") != "null":
        out.append(f"window.open() of the ad address gave {seen.get('ad')!r}, not null")
    for path, what in (("/window", "the ad window"), ("/link", "the link to the ad"),
                       ("/later", "the blank window sent to the ad")):
        if (host, path) in asked:
            out.append(f"{what} reached the ad host")
    if seen.get("leftover"):
        out.append(f"windows left open: {seen['leftover']}")
    if (seen.get("count") or 0) < 3:
        out.append(f"the menu counts {seen.get('count')} blocked on the page, not 3")
    if seen.get("plain") != "opened" or (PLAIN_HOST, "/window.html") not in asked:
        out.append("the plain window did not open")
    if seen.get("switch_plain") != "null":
        out.append(f"with no pop-ups on, window.open() of the plain address gave {seen.get('switch_plain')!r}")
    if (PLAIN_HOST, "/link.html") in asked:
        out.append("with no pop-ups on, the plain link opened a window")
    return out


class Server:
    def __init__(self, host: str):
        self.asked: set[tuple[str, str]] = set()
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
                    return
                if name == PAGE_HOST and self.path == "/page.html":
                    self._send("text/html; charset=utf-8", page_html(host).encode())
                    return
                if name in (host, PLAIN_HOST):
                    server.asked.add((name, self.path.split("?")[0]))
                self._send("text/html; charset=utf-8", b"<!doctype html><title>window</title><p>a window</p>")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _click(ws: WebSocket, expression: str):
    """Runs `expression` in the page as a click would: with a user gesture, so Chromium's own pop-up blocker
    lets a window open."""
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, userGesture=True)
    return reply.get("result", {}).get("value")


def _pages(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as reply:
        return [t for t in json.loads(reply.read()) if t.get("type") == "page"]


def _activate(port: int, target_id: str) -> None:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{target_id}", timeout=10).read()
    time.sleep(1)


def _allow_ads_on_page_site(port: int) -> None:
    ws = WebSocket(_open(port, "chrome://settings/content/ads")["webSocketDebuggerUrl"])
    try:
        time.sleep(3)
        allow = [PAGE_HOST, "", "ads", "allow", False]
        ws.call("Runtime.evaluate", expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
        time.sleep(1)
    finally:
        ws.close()


def _native_steps(port: int, page: dict, ws: WebSocket, host: str, seen: dict) -> None:
    menu = WebSocket(_open(port, MENU_URL)["webSocketDebuggerUrl"])
    try:
        _activate(port, page["id"])
        before = {t["id"] for t in _pages(port)}  # the browser's own first tab is blank too
        _click(ws, "document.getElementById('ad-link').click(); 1")
        seen["blank"] = _click(ws, "window.openBlank()")
        time.sleep(SETTLE_S)
        seen["leftover"] = [t["url"] for t in _pages(port) if t["id"] not in before and
                            (t["url"] == "about:blank" or t["url"].startswith(f"http://{host}/"))]
        _activate(port, page["id"])
        time.sleep(1.5)  # the menu reads the page's count every second
        count = menu.call("Runtime.evaluate", returnByValue=True,
                          expression="document.getElementById('page-count').textContent")
        digits = re.sub(r"\D", "", count.get("result", {}).get("value") or "")
        seen["count"] = int(digits) if digits else 0
        seen["plain"] = _click(ws, "window.openPlain()")
        time.sleep(SETTLE_S)
        # "no pop-ups" for the page's site: the menu reloads the page
        _activate(port, page["id"])
        menu.call("Runtime.evaluate", expression="document.querySelector('[data-switch=popups]').click(); 1")
        time.sleep(SETTLE_S + 1)
        seen["switch_plain"] = _click(ws, "window.openPlain()")
        _click(ws, "document.getElementById('plain-link').click(); 1")
        time.sleep(SETTLE_S)
    finally:
        menu.close()


def run_mode(browser: Path, work: Path, host: str, mode: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix=f"popup-{mode}-", dir=work))
    seen: dict = {}
    found: list[str] = []
    with Server(host) as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, PLAIN_HOST, host], native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                _allow_ads_on_page_site(port)
            if mode != "control":
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            page = _open(port, f"http://{PAGE_HOST}/page.html")
            ws = WebSocket(page["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S)
                seen["ad"] = _click(ws, "window.openAd()")
                time.sleep(SETTLE_S)
                if mode == "native":
                    _native_steps(port, page, ws, host, seen)
            finally:
                ws.close()
            seen["asked"] = sorted(server.asked)
            found = native_problems(seen, host) if mode == "native" else opened_problems(seen, host)
        except (OSError, RuntimeError, ValueError, KeyError) as e:
            found = [f"the run failed: {e}"]
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    print(f"{'PASS' if not found else 'FAIL'}  {mode}: {json.dumps(seen, default=list)}"
          + (f"; {'; '.join(found)}" if found else ""))
    return [f"{mode}: {p}" for p in found]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    host = popup_host(lists_file.read_text(encoding="utf-8"))
    if host is None:
        print("POPUP CHECK: FAILED (EasyList holds no plain pop-up host rule)")
        return 1
    print(f"    pop-up ad host: {host}")
    a.work.mkdir(parents=True, exist_ok=True)
    found = [p for mode in MODES for p in run_mode(a.browser.resolve(), a.work, host, mode)]
    for problem in found:
        print(problem)
    print("POPUP CHECK: PASSED" if not found else f"POPUP CHECK: FAILED ({len(found)} problem(s))")
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
