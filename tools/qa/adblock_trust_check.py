#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "Allow custom filters requiring trust" for My filters, checked end to end and offline
(ROADMAP P5.48).

As in uBlock Origin, the person's own filters may use the scriptlets that need trust only when this setting is
on. A local server serves a test page under a name of its own (host-resolver rules; every other name fails, so
nothing leaves the PC). My filters hold two rules for it: one with a scriptlet any list may use
(`set-local-storage-item`) and one with a scriptlet that needs trust (`trusted-set-local-storage-item`).
Steps:

    off      the plain scriptlet sets its item, the trusted one does not
    on       with the setting on, both set their item
    off      off again, the trusted one does not (the plain one still does)

    py -3 -I tools/qa/adblock_trust_check.py --browser <out>\\thoron.exe --work <scratch dir>
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

PAGE_HOST = "trust-check.test"
SETTINGS_URL = "chrome://adblock/"
BUILD_S = 5.0
SETTLE_S = 2.5
MY_FILTERS = (f"{PAGE_HOST}##+js(set-local-storage-item, thoron-plain, yes)\n"
              f"{PAGE_HOST}##+js(trusted-set-local-storage-item, thoron-trusted, yes)\n")
PAGE = "<!doctype html><title>Thoron trust check</title><p>trust</p>"
READ = ("JSON.stringify({plain: localStorage.getItem('thoron-plain'),"
        " trusted: localStorage.getItem('thoron-trusted')})")
CLEAR = "localStorage.clear(); 1"


def step_problems(step: str, trusted_on: bool, seen: dict) -> list[str]:
    out = []
    if seen.get("plain") != "yes":
        out.append(f"{step}: the plain scriptlet did not set its item ({seen.get('plain')!r})")
    want = "yes" if trusted_on else None
    if seen.get("trusted") != want:
        out.append(f"{step}: the trusted scriptlet {'did not set' if trusted_on else 'set'} its item "
                   f"({seen.get('trusted')!r}) with the setting {'on' if trusted_on else 'off'}")
    return out


class Server:
    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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
    return reply.get("result", {}).get("value")


def run(browser: Path, work: Path) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="trust-", dir=work))
    problems: list[str] = []
    with Server() as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST], native=True)
        port = None
        settings = page = None
        try:
            port = _devtools_port(profile)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            time.sleep(2)
            # typed, as a person would: the input event enables Save
            _eval(settings, f"(() => {{ const box = document.getElementById('my-filters');"
                            f" box.value = {json.dumps(MY_FILTERS)}; box.dispatchEvent(new Event('input'));"
                            " document.getElementById('save-filters').click(); return 1; })()")
            time.sleep(BUILD_S)
            page = WebSocket(_open(port, f"http://{PAGE_HOST}/page.html")["webSocketDebuggerUrl"])
            for step, on in (("off", False), ("on", True), ("off", False)):
                if _eval(settings, "document.getElementById('trust-filters').checked") != on:
                    _eval(settings, "document.getElementById('trust-filters').click(); 1")
                    time.sleep(BUILD_S)
                shown = _eval(settings, "document.getElementById('trust-filters').checked")
                _eval(page, CLEAR)
                page.call("Page.reload", ignoreCache=True)
                time.sleep(SETTLE_S)
                seen = json.loads(_eval(page, READ) or "{}")
                found = step_problems(step, on, seen)
                if shown is not on:
                    found.append(f"{step}: the setting reads {shown!r}, not {on}")
                print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
                problems += found
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            for ws in (settings, page):
                if ws:
                    try:
                        ws.close()
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
    print("TRUST CHECK: PASSED" if not problems else f"TRUST CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
