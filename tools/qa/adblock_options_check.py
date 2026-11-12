#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the Settings section of chrome://adblock, checked end to end and offline (ROADMAP P5.38).

The Settings are uBlock Origin's: the badge, the privacy options, the default behavior for every site and
"ignore generic cosmetic filters". The check clicks them on chrome://adblock as a person would. A local server
serves a test page under a name of its own (host-resolver rules; every other name fails, so nothing leaves the
PC): an element a generic EasyList hide rule hides, a web font, an image its security policy forbids, which
makes the browser send a CSP report, and a script that sets the title. Steps:

    defaults   the badge is on and every other setting off; the element is hidden, the font and the report
               are asked for, the script runs
    on         every setting on reads as on; the report is not sent, the element is shown (generic rules
               ignored), the font is not asked for (remote fonts blocked for every site)
    site       the menu's "remote fonts" switch off for the page's site (it was on from the default): the
               font is asked for there again, and chrome://adblock lists the site as an exception
    script     "Disable JavaScript": the page's script does not run
    off        every setting off again reads as off

    py -3 -I tools/qa/adblock_options_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import http.server
import json
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_menu_check import generic_class  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "options-check.test"
SETTINGS_URL = "chrome://adblock/"
MENU_URL = "chrome://adblock-menu.top-chrome/"
SETTLE_S = 3.0
OPTIONS = ("badge", "prefetch", "hyperlink-auditing", "webrtc", "block-csp-reports", "default-cosmetic",
           "default-media", "default-fonts", "javascript", "ignore-generic", "default-3p-script",
           "default-3p-frame")
# the ones the steps turn on and check by what the page does; the rest are checked as read back
TURNED_ON = ("prefetch", "hyperlink-auditing", "webrtc", "block-csp-reports", "ignore-generic", "default-fonts")
POLICY = "img-src 'none'; report-uri /csp-report"


def page_html(generic: str) -> str:
    return ("<!doctype html><title>no script</title>"
            "<style>@font-face{font-family:Check;src:url(/check.woff2) format('woff2');}"
            "#text{font-family:Check,serif;}</style>"
            f'<div class="{generic}" id="generic">an ad</div><p id="text">text</p>'
            '<img src="/forbidden.png" alt="">'
            "<script>document.title = 'script ran';</script>")


READ_PAGE = """JSON.stringify({generic: (() => { const e = document.getElementById('generic');
  return !e ? 'gone' : getComputedStyle(e).display === 'none' ? 'hidden' : 'shown'; })()})"""
READ_SETTINGS = """JSON.stringify(Object.fromEntries(Array.from(document.querySelectorAll('[data-setting]'))
  .map((box) => [box.dataset.setting, box.checked])))"""


def settings_problems(step: str, got: dict, want_on: set[str]) -> list[str]:
    out = []
    for name in OPTIONS:
        if name not in got:
            out.append(f"{step}: the setting {name} is not on the page")
        elif got[name] != (name in want_on):
            out.append(f"{step}: {name} reads {'on' if got[name] else 'off'}")
    return out


def page_problems(step: str, seen: dict, *, hidden: bool, font: bool, report: bool) -> list[str]:
    out = []
    if seen.get("generic") != ("hidden" if hidden else "shown"):
        out.append(f"{step}: the element of the generic rule is {seen.get('generic')}, not "
                   f"{'hidden' if hidden else 'shown'}")
    if seen.get("font") != font:
        out.append(f"{step}: the font was {'asked for' if seen.get('font') else 'not asked for'}")
    if seen.get("report") != report:
        out.append(f"{step}: the CSP report was {'sent' if seen.get('report') else 'not sent'}")
    return out


class Server:
    def __init__(self, generic: str):
        self.asked: set[str] = set()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, ctype: str, body: bytes, extra: dict | None = None):
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for name, value in (extra or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                if name == "127.0.0.1" and self.path == "/warm.html":
                    self._send("text/html; charset=utf-8", WARM_HTML.encode())
                elif name == PAGE_HOST and self.path == "/page.html":
                    self._send("text/html; charset=utf-8", page_html(generic).encode(),
                               {"Content-Security-Policy": POLICY})
                else:
                    if name == PAGE_HOST:
                        server.asked.add(self.path)
                    self._send("application/octet-stream", b"\0" * 64)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(min(length, 65536))
                name = (self.headers.get("Host") or "").split(":")[0]
                if name == PAGE_HOST:
                    server.asked.add(self.path)
                self._send("text/plain", b"ok")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def _title(port: int, target_id: str) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as reply:
        for target in json.loads(reply.read()):
            if target.get("id") == target_id:
                return target.get("title", "")
    return ""


class Run:
    def __init__(self, browser: Path, work: Path, server: Server):
        self.server = server
        self.profile = Path(tempfile.mkdtemp(prefix="options-", dir=work))
        self.proc = _launch(browser, self.profile, server.port, [PAGE_HOST], native=True)
        self.port = _devtools_port(self.profile)
        _open(self.port, f"http://127.0.0.1:{server.port}/warm.html")
        time.sleep(4)
        self.settings = WebSocket(_open(self.port, SETTINGS_URL)["webSocketDebuggerUrl"])
        time.sleep(2)
        self.page_target = _open(self.port, f"http://{PAGE_HOST}/page.html")
        self.page = WebSocket(self.page_target["webSocketDebuggerUrl"])
        time.sleep(SETTLE_S)

    def read_settings(self) -> dict:
        return json.loads(_eval(self.settings, READ_SETTINGS) or "{}")

    def click(self, names) -> None:
        for name in names:
            _eval(self.settings, f"document.querySelector('[data-setting={json.dumps(name)}]').click(); 1")
            time.sleep(0.6)
        time.sleep(1)

    def load_page(self) -> dict:
        self.server.asked.clear()
        self.page.call("Page.reload", ignoreCache=True)
        time.sleep(SETTLE_S)
        seen = json.loads(_eval(self.page, READ_PAGE) or "{}")
        seen["font"] = "/check.woff2" in self.server.asked
        seen["report"] = "/csp-report" in self.server.asked
        seen["title"] = _title(self.port, self.page_target["id"])
        return seen

    def fonts_switch_off_for_the_site(self) -> None:
        menu = WebSocket(_open(self.port, MENU_URL)["webSocketDebuggerUrl"])
        try:
            time.sleep(2)
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/activate/{self.page_target['id']}",
                                   timeout=10).read()
            time.sleep(1.5)
            _eval(menu, "document.querySelector('[data-switch=fonts]').click(); 1")
            time.sleep(SETTLE_S)
        finally:
            menu.close()

    def listed_exception(self) -> bool:
        _eval(self.settings, "location.reload(); 1")
        time.sleep(3)
        text = _eval(self.settings, "document.getElementById('switches').innerText") or ""
        return PAGE_HOST in text and "remote fonts allowed" in text

    def close(self) -> None:
        for ws in (self.settings, self.page):
            try:
                ws.close()
            except OSError:
                pass
        _close_browser(self.port, self.proc)
        shutil.rmtree(self.profile, ignore_errors=True)


def run(browser: Path, work: Path, generic: str) -> list[str]:
    problems: list[str] = []

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server(generic) as server:
        r = None
        try:
            r = Run(browser, work, server)
            got = r.read_settings()
            seen = r.load_page()
            report("defaults", settings_problems("defaults", got, {"badge"})
                   + page_problems("defaults", seen, hidden=True, font=True, report=True)
                   + ([] if seen.get("title") == "script ran" else ["defaults: the script did not run"]), seen)
            r.click(("badge",) + TURNED_ON)
            got = r.read_settings()
            seen = r.load_page()
            report("on", settings_problems("on", got, set(TURNED_ON))
                   + page_problems("on", seen, hidden=False, font=False, report=False), seen)
            r.fonts_switch_off_for_the_site()
            seen = r.load_page()
            found = page_problems("site", seen, hidden=False, font=True, report=False)
            if not r.listed_exception():
                found.append("site: chrome://adblock does not list the site's exception")
            report("site", found, seen)
            r.click(("javascript",))
            seen = r.load_page()
            report("script", [] if seen.get("title") == "no script" else
                   [f"script: the page's script ran with JavaScript off (title {seen.get('title')!r})"], seen)
            r.click(("badge", "javascript") + TURNED_ON)
            got = r.read_settings()
            report("off", settings_problems("off", got, {"badge"}), got)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            if r is not None:
                r.close()
    return problems


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profile")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    generic = generic_class((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if not generic:
        print("OPTIONS CHECK: FAILED (EasyList holds no generic hide rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, generic)
    for problem in problems:
        print(problem)
    print("OPTIONS CHECK: PASSED" if not problems else f"OPTIONS CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
