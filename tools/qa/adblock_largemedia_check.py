#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "Temporarily allow large media", checked end to end and offline (ROADMAP P5.62).

As uBlock Origin: with "no large media" on for a site, a video over the size set is stopped, and gets a bar to
click; a real click lets large media through on that site until the browser closes, and the video loads. A
local server serves a page with a video of 200 kB (host-resolver rules; every other name fails, so nothing
leaves the PC). Steps:

    blocked   with the site's large media switch on, the video is stopped and a bar is put after it
    script    the page cannot reach what the bar calls, and a click the page makes itself changes nothing
    click     a person's click on the bar: the video is asked for again and let through (the logger)
    other     another site still has its large media stopped

    py -3 -I tools/qa/adblock_largemedia_check.py --browser <out>\\thoron.exe --work <scratch dir>
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

PAGE_HOST = "media-page.test"
OTHER_HOST = "other-media.test"
SETTINGS_URL = "chrome://adblock/"
SETTLE_S = 3.0
VIDEO_BYTES = 200 * 1024
PAGE = '<!doctype html><title>Thoron large media check</title><video id="v" src="/big.mp4" muted></video><p>after</p>'
READ_BAR = """JSON.stringify((() => { const bar = document.querySelector('thoron-large-media');
  if (!bar) return {bar: false};
  const r = bar.getBoundingClientRect();
  return {bar: true, x: r.x + 20, y: r.y + r.height / 2, next: bar.previousElementSibling === document.getElementById('v')};
})())"""


# `log`: for each request of the video in the logger, whether it was blocked. A request is put there as let
# through when it goes out, and as blocked too when its answer is over the size.
def blocked_problems(bar: dict, log: list[bool]) -> list[str]:
    out = []
    if not bar.get("bar") or not bar.get("next"):
        out.append(f"blocked: no bar after the stopped video ({bar})")
    if True not in log:
        out.append(f"blocked: the logger has the video as {log}, never blocked")
    return out


def script_problems(reachable: str, before: list[bool], log: list[bool]) -> list[str]:
    out = []
    if reachable != "undefined":
        out.append(f"script: the page sees thoronAllowMedia as {reachable!r}")
    if len(log) != len(before):
        out.append("script: the page's own click made the video load again")
    return out


def click_problems(before: list[bool], log: list[bool], bar: dict) -> list[str]:
    out = []
    if len(log) <= len(before):
        out.append(f"click: the video was not asked for again ({before} then {log})")
    elif log.count(True) != before.count(True):
        out.append(f"click: the video was blocked again ({before} then {log})")
    if bar.get("bar"):
        out.append("click: the bar is still there")
    return out


READ_LOG = """(async () => { const {sendWithPromise} = await import('chrome://resources/js/cr.js');
  const tab = (await sendWithPromise('getLog')).find((t) => t.url.includes(%s)) || {entries: []};
  return JSON.stringify(tab.entries.filter((e) => e.url.endsWith('/big.mp4')).map((e) => e.blocked !== false));
})()"""


class Server:
    def __init__(self):
        self.full: dict[str, int] = {}
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                if self.path.startswith("/big.mp4"):
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(VIDEO_BYTES))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    try:
                        for _ in range(VIDEO_BYTES // 4096):
                            self.wfile.write(b"\0" * 4096)
                        server.full[name] = server.full.get(name, 0) + 1  # every byte was taken
                    except OSError:
                        pass  # the browser stopped it
                    return
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
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="largemedia-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server() as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, OTHER_HOST], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            time.sleep(SETTLE_S)
            for host in (PAGE_HOST, OTHER_HOST):
                _eval(settings, "(async () => { const {sendWithPromise} = await import('chrome://resources/js/cr.js');"
                                f" return await sendWithPromise('setHostSwitches', {json.dumps(host)}, ['media']); }})()")
            # the settings page stays open: its logger keeps the requests let through too
            def media_log(host: str) -> list[bool]:
                return json.loads(_eval(settings, READ_LOG % json.dumps(host)) or "[]")

            target = _open(port, f"http://{PAGE_HOST}/page.html")
            page = WebSocket(target["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S + 1)
                bar = json.loads(_eval(page, READ_BAR) or "{}")
                time.sleep(2)  # the logger asks every two seconds
                report("blocked", blocked_problems(bar, media_log(PAGE_HOST)), bar)

                # the page's own world: the helper is not there; the bar is in a closed shadow tree, so the
                # page can only click its outside
                reachable = _eval(page, "typeof thoronAllowMedia")
                before = media_log(PAGE_HOST)
                _eval(page, "document.querySelector('thoron-large-media').click(); 1")
                time.sleep(3)
                log = media_log(PAGE_HOST)
                report("script", script_problems(reachable, before, log), [reachable, log])
                before = log

                if bar.get("bar"):
                    page.call("Page.bringToFront")
                    for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                        page.call("Input.dispatchMouseEvent", type=kind, x=bar["x"], y=bar["y"], button="left",
                                  clickCount=1)
                        time.sleep(0.1)
                    time.sleep(SETTLE_S)
                time.sleep(2)
                after = json.loads(_eval(page, READ_BAR) or "{}")
                log = media_log(PAGE_HOST)
                report("click", click_problems(before, log, after), [before, log])

                other = WebSocket(_open(port, f"http://{OTHER_HOST}/page.html")["webSocketDebuggerUrl"])
                time.sleep(SETTLE_S + 1)
                seen = json.loads(_eval(other, READ_BAR) or "{}")
                other.close()
                time.sleep(2)
                log = media_log(OTHER_HOST)
                found = [] if seen.get("bar") and True in log else [f"other: {OTHER_HOST} shows {seen}, {log}"]
                report("other", found, [seen.get("bar"), log])
            finally:
                page.close()
                settings.close()
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
    print("LARGE MEDIA CHECK: PASSED" if not problems else f"LARGE MEDIA CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
