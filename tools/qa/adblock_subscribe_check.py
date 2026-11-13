#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "subscribe" links of filter list sites, checked end to end and offline (ROADMAP P5.53).

As uBlock Origin handles them, a link abp:subscribe?location=<list>&title=<title> (or the same at
https://subscribe.adblockplus.org/) opens chrome://adblock, which asks whether to add the list; it is added
only when the person says so. A local server serves a test page with both kinds of link and the list itself
(host-resolver rules; every other name fails, so nothing leaves the PC; the updater is pointed at the server,
which lets a list at a local address be added). Steps:

    abp       a click on the abp: link opens the page asking about "Check list"; "Add the list" adds it
    org       a click on the subscribe.adblockplus.org link opens the page asking about "Org list"
    script    a page that goes to an abp: link on its own, without a click, opens nothing

    py -3 -I tools/qa/adblock_subscribe_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
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
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "subscribe-check.test"
SETTLE_S = 2.5
LIST_TEXT = "! Title: Thoron subscribe check\n||extra-list.test^\n"


def list_url(port: int, name: str) -> str:
    return f"http://127.0.0.1:{port}/lists/{name}.txt"


def page_html(port: int) -> str:
    def q(name: str, title: str) -> str:
        return urllib.parse.urlencode({"location": list_url(port, name), "title": title},
                                      quote_via=urllib.parse.quote)
    return ("<!doctype html><title>Thoron subscribe check</title><style>a{display:block;padding:20px}</style>"
            f'<a id="abp" href="abp:subscribe?{q("check", "Check list")}">Subscribe</a>'
            f'<a id="org" href="https://subscribe.adblockplus.org/?{q("org", "Org list")}">Subscribe here</a>')


def ask_problems(step: str, asked: dict, title: str, url: str) -> list[str]:
    out = []
    if not asked.get("shown"):
        return [f"{step}: no page asks whether to add the list"]
    if asked.get("title") != f'Add the filter list "{title}"?':
        out.append(f"{step}: the page asks {asked.get('title')!r}")
    if asked.get("url") != url:
        out.append(f"{step}: the page names {asked.get('url')!r}, not {url!r}")
    return out


class Server:
    def __init__(self):
        server = self
        self.port = 0

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                if path.startswith("/lists/"):
                    body, ctype = LIST_TEXT.encode(), "text/plain; charset=utf-8"
                else:
                    body, ctype = page_html(server.port).encode(), "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _launch(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            "--enable-features=ThoronNativeAdblock",
            f"--thoron-adblock-lists-url-for-testing=http://127.0.0.1:{port}/lists/",
            f"--host-resolver-rules=MAP {PAGE_HOST} 127.0.0.1:{port}, MAP subscribe.adblockplus.org "
            f"127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def _settings_tabs(port: int) -> list[dict]:
    return [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10).read())
            if t.get("url", "").startswith("chrome://adblock/")]


READ_ASK = ("JSON.stringify({shown: !document.getElementById('subscribe-box').hidden,"
            " title: document.getElementById('subscribe-title').textContent,"
            " url: document.getElementById('subscribe-url').textContent})")


def run(browser: Path, work: Path) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="subscribe-", dir=work))
    problems: list[str] = []
    with Server() as server:
        proc = _launch(browser, profile, server.port)
        port = None
        page = None
        try:
            port = _devtools_port(profile)
            page = WebSocket(_open(port, f"http://{PAGE_HOST}/page.html")["webSocketDebuggerUrl"])
            time.sleep(SETTLE_S)

            def click(element_id: str) -> None:
                box = json.loads(_eval(page, f"JSON.stringify(document.getElementById('{element_id}')"
                                             ".getBoundingClientRect())"))
                x, y = box["x"] + 10, box["y"] + box["height"] / 2
                for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                    page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
                    time.sleep(0.1)

            def asked(before: set[str]) -> tuple[dict, WebSocket | None]:
                for _ in range(20):
                    time.sleep(0.5)
                    new = [t for t in _settings_tabs(port) if t["id"] not in before]
                    if new:
                        ws = WebSocket(new[0]["webSocketDebuggerUrl"])
                        time.sleep(1.5)
                        return json.loads(_eval(ws, READ_ASK) or "{}"), ws
                return {}, None

            for step, element, name, title in (("abp", "abp", "check", "Check list"),
                                               ("org", "org", "org", "Org list")):
                before = {t["id"] for t in _settings_tabs(port)}
                click(element)
                seen, ws = asked(before)
                found = ask_problems(step, seen, title, list_url(server.port, name))
                if ws and step == "abp" and not found:
                    _eval(ws, "document.getElementById('subscribe-add').click(); 1")
                    time.sleep(4)
                    lists = json.loads(_eval(ws, "(async () => JSON.stringify((await (await import("
                                                 "'chrome://resources/js/cr.js')).sendWithPromise('getState'))"
                                                 ".lists.map((l) => l.url)))()") or "[]")
                    if list_url(server.port, name) not in lists:
                        found.append(f"abp: the list was not added ({lists})")
                if ws:
                    ws.close()
                print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
                problems += found

            # without a click: nothing opens
            before = {t["id"] for t in _settings_tabs(port)}
            _eval(page, "location.href = document.getElementById('abp').href; 1")
            time.sleep(3)
            opened = [t for t in _settings_tabs(port) if t["id"] not in before]
            found = [f"script: a page opened {len(opened)} tab(s) without a click"] if opened else []
            print(f"{'PASS' if not found else 'FAIL'}  script: {len(opened)} tab(s) opened")
            problems += found
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            if page:
                try:
                    page.close()
                except OSError:
                    pass
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    return problems


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profile")
    a = p.parse_args(argv)
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work)
    for problem in problems:
        print(problem)
    print("SUBSCRIBE CHECK: PASSED" if not problems else f"SUBSCRIBE CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
