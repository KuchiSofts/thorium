#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's dynamic URL filtering in My rules, checked end to end and offline
(ROADMAP P5.60).

A rule `source address type action` decides for the requests whose address starts with `address`, before the
rules of hosts: the longest address first; `noop` leaves the request to the filter lists. A local server serves
a page that loads two scripts of one host, one under /lib/ and one under /extra/ (host-resolver rules; every other
name fails, so nothing leaves the PC). Steps:

    block     "* http://lib-host.test/extra/ * block": the /extra/ script is blocked, the /lib/ one loads
    allow     the host blocked, "page-host.test http://lib-host.test/lib/ * allow": only the /lib/ one loads
    noop      the host blocked, "* http://lib-host.test/extra/ * noop": only the /extra/ one loads (no list has it)
    why       the logger's "Why?" for the /extra/ script names the address rule
    problems  an address rule with another scheme or an unknown type is named as no rule

    py -3 -I tools/qa/adblock_urlrules_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "page-host.test"
LIB_HOST = "lib-host.test"
SETTINGS_URL = "chrome://adblock/"
SETTLE_S = 3.0
KEEP = f"http://{LIB_HOST}/lib/keep.js"
DROP = f"http://{LIB_HOST}/extra/more.js"
STEPS = {
    "block": (f"* http://{LIB_HOST}/extra/ * block\n", {"/lib/keep.js"}),
    "allow": (f"* {LIB_HOST} * block\n{PAGE_HOST} http://{LIB_HOST}/lib/ * allow\n", {"/lib/keep.js"}),
    "noop": (f"* {LIB_HOST} * block\n* http://{LIB_HOST}/extra/ * noop\n", {"/extra/more.js"}),
}
BAD = f"* ftp://{LIB_HOST}/ * block\n* http://{LIB_HOST}/ nosuchtype block\n"
PAGE = f'<!doctype html><title>Thoron URL rules check</title><script src="{KEEP}"></script><script src="{DROP}"></script>'


def step_problems(step: str, asked: set[str], want: set[str]) -> list[str]:
    return [] if asked == want else [f"{step}: the scripts asked for are {sorted(asked)}, not {sorted(want)}"]


def why_problems(answer: dict) -> list[str]:
    want = f"* http://{LIB_HOST}/extra/ * block"
    return [] if answer.get("myRule") == want else [f"why: the rule named is {answer.get('myRule')!r}, not {want!r}"]


def bad_problems(problems: list) -> list[str]:
    return [] if sorted(problems) == sorted(BAD.splitlines()) else [f"problems: named {problems}"]


class Server:
    def __init__(self):
        self.asked: set[str] = set()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                path = self.path.split("?")[0]
                if name == LIB_HOST:
                    server.asked.add(path)
                    body, ctype = b"window.loaded = (window.loaded || 0) + 1;", "text/javascript"
                else:
                    body, ctype = PAGE.encode(), "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
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


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def ask(ws: WebSocket, *args) -> object:
    call = ", ".join(json.dumps(a) for a in args)
    return json.loads(_eval(ws, "(async () => { const {sendWithPromise} = await import("
                                f"'chrome://resources/js/cr.js'); return JSON.stringify(await sendWithPromise({call})); }})()")
                      or "null")


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="urlrules-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server() as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, LIB_HOST], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            page = WebSocket(_open(port, "about:blank")["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S)
                for step, (rules, want) in STEPS.items():
                    ask(settings, "setMyRules", rules)
                    time.sleep(1)
                    server.asked.clear()
                    page.call("Page.navigate", url=f"http://{PAGE_HOST}/page.html")
                    time.sleep(SETTLE_S)
                    report(step, step_problems(step, set(server.asked), want), sorted(server.asked))
                    if step == "block":
                        answer = ask(settings, "explainRequest", DROP, "script", f"http://{PAGE_HOST}/page.html")
                        report("why", why_problems(answer or {}), (answer or {}).get("myRule"))
                found = ask(settings, "setMyRules", BAD) or []
                report("problems", bad_problems(found), found)
            finally:
                settings.close()
                page.close()
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
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
    print("URL RULES CHECK: PASSED" if not problems else f"URL RULES CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
