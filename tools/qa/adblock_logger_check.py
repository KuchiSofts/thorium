#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the logger on chrome://adblock, checked end to end and offline (ROADMAP P5.42).

As uBlock Origin's logger: while it is open it shows the requests of the open tabs, blocked and let through, and
makes rules from them. A local server serves a test page under a name of its own (host-resolver rules; every
other name fails, so nothing leaves the PC) with an image from an ad host EasyList blocks and one from a plain
host. Steps:

    rows     the page's tab lists the ad image as blocked and the plain image as let through
    filter   "Let through" shows only the plain image
    allow    "Allow" on the ad image adds @@||<ad host>^$domain=<page site>, and the ad host is asked again
    block    "Block" on the plain image adds ||<plain host>^, and the plain host is not asked any more

    py -3 -I tools/qa/adblock_logger_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_earlyhints_check import ad_host  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "logger-check.test"
PLAIN_HOST = "plain-logger.test"
TITLE = "Thoron logger check"
SETTLE_S = 3.0


def page_html(host: str) -> str:
    return (f"<!doctype html><title>{TITLE}</title>"
            f'<img src="http://{host}/ad.png" alt=""><img src="http://{PLAIN_HOST}/pic.png" alt="">')


READ_ROWS = """JSON.stringify(Array.from(document.querySelectorAll('#log-rows tr')).map((tr) =>
  ({kind: tr.className, url: tr.querySelector('td.url').textContent,
    button: (tr.querySelector('td.act button') || {}).textContent || ''})))"""
CHOOSE_TAB = """(() => { const select = document.getElementById('log-tab');
  const option = Array.from(select.options).find((o) => o.textContent.includes(%s));
  if (!option) return false;
  select.value = option.value; select.dispatchEvent(new Event('change')); return true; })()""" % json.dumps(TITLE)


def rows_problems(rows: list[dict], host: str) -> list[str]:
    out = []
    if not any(r["kind"] == "blocked" and f"//{host}/ad.png" in r["url"] for r in rows):
        out.append("rows: the ad image is not listed as blocked")
    if not any(r["kind"] == "allowed" and f"//{PLAIN_HOST}/pic.png" in r["url"] for r in rows):
        out.append("rows: the plain image is not listed as let through")
    return out


def filter_problems(rows: list[dict]) -> list[str]:
    if rows and all(r["kind"] == "allowed" for r in rows):
        return []
    return [f"filter: 'Let through' shows {[r['kind'] for r in rows]}"]


class Server:
    def __init__(self, host: str):
        self.asked: set[str] = set()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                if name == "127.0.0.1" and self.path == "/warm.html":
                    body, ctype = WARM_HTML.encode(), "text/html; charset=utf-8"
                elif name == PAGE_HOST:
                    body, ctype = page_html(host).encode(), "text/html; charset=utf-8"
                else:
                    server.asked.add(name)
                    body, ctype = b"\x89PNG\r\n", "image/png"
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
    return ws.call("Runtime.evaluate", expression=expression, returnByValue=True).get("result", {}).get("value")


def run(browser: Path, work: Path, host: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="logger-", dir=work))
    problems: list[str] = []

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    def my_filters() -> str:
        try:
            return (profile / "Thoron Adblock" / "my-filters.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    with Server(host) as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, PLAIN_HOST, host], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            _open(port, f"http://127.0.0.1:{server.port}/warm.html")
            time.sleep(4)
            logger = WebSocket(_open(port, "chrome://adblock/#logger")["webSocketDebuggerUrl"])
            page = WebSocket(_open(port, "about:blank")["webSocketDebuggerUrl"])
            try:
                time.sleep(3)  # the logger has asked once: requests let through are kept from now on
                page.call("Page.navigate", url=f"http://{PAGE_HOST}/page.html")
                time.sleep(SETTLE_S + 2)  # the logger asks every two seconds
                _eval(logger, CHOOSE_TAB)
                rows = json.loads(_eval(logger, READ_ROWS) or "[]")
                report("rows", rows_problems(rows, host), rows)

                _eval(logger, "document.getElementById('log-kind').value = 'allowed';"
                              "document.getElementById('log-kind').dispatchEvent(new Event('change')); 1")
                rows = json.loads(_eval(logger, READ_ROWS) or "[]")
                report("filter", filter_problems(rows), [r["kind"] for r in rows])
                _eval(logger, "document.getElementById('log-kind').value = '';"
                              "document.getElementById('log-kind').dispatchEvent(new Event('change')); 1")

                def press(kind: str, url_part: str) -> None:
                    _eval(logger, "(() => { const tr = Array.from(document.querySelectorAll('#log-rows tr'))"
                                  f".find((t) => t.className === {json.dumps(kind)} && "
                                  f"t.querySelector('td.url').textContent.includes({json.dumps(url_part)}));"
                                  " if (tr) tr.querySelector('td.act button').click(); return !!tr; })()")
                    time.sleep(4)  # the rule is built in

                press("blocked", f"//{host}/ad.png")
                server.asked.clear()
                page.call("Page.reload", ignoreCache=True)
                time.sleep(SETTLE_S)
                mine = my_filters()
                found = [] if f"@@||{host}^$domain={PAGE_HOST}" in mine else [f"allow: My filters {mine!r}"]
                if host not in server.asked:
                    found.append("allow: the ad host was not asked after it was allowed")
                report("allow", found, mine.strip())

                time.sleep(SETTLE_S)
                _eval(logger, CHOOSE_TAB)
                press("allowed", f"//{PLAIN_HOST}/pic.png")
                server.asked.clear()
                page.call("Page.reload", ignoreCache=True)
                time.sleep(SETTLE_S)
                mine = my_filters()
                found = [] if f"||{PLAIN_HOST}^" in mine.splitlines() else [f"block: My filters {mine!r}"]
                if PLAIN_HOST in server.asked:
                    found.append("block: the plain host was still asked after it was blocked")
                report("block", found, mine.strip())
            finally:
                logger.close()
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
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    host = ad_host((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if not host:
        print("LOGGER CHECK: FAILED (EasyList holds no plain host rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, host)
    for problem in problems:
        print(problem)
    print("LOGGER CHECK: PASSED" if not problems else f"LOGGER CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
