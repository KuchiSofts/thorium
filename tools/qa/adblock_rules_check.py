#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "My rules" (uBlock Origin's dynamic filtering), checked end to end and offline (ROADMAP
P5.44).

A local server serves a test page under a name of its own (host-resolver rules; every other name fails, so
nothing leaves the PC): a script from a plain host of another site, an image from an ad host EasyList blocks,
an image of the page's own site, and a script written in the page. The rules are saved on chrome://adblock as
a person would. Steps:

    none     no rules: the other site's script runs, the ad image is blocked, the page's script runs
    rules    `* * 3p-script block`, `<page> <ad host> * allow`, `<page> * inline-script block`: the other
             site's script is not asked for, the ad image is asked for (the rule beats the lists), the
             page's own script does not run; a line that is not a rule is named
    noop     `<page> * 3p-script noop` added: the other site's script runs again (the lists decide)
    switch   the setting that blocks third-party scripts on every site turned on: the other site's script
             is blocked again (a noop leaves it to the lists and the switches)
    allow    `<page> <other host> * allow` added: the other site's script runs (an allow rule beats the
             switch, as in uBlock Origin, where the switch is a rule too)

    py -3 -I tools/qa/adblock_rules_check.py --browser <out>\\thoron.exe --work <scratch dir>
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

PAGE_HOST = "rules-check.test"
OTHER_HOST = "other-rules.test"
SETTLE_S = 3.0
NOT_A_RULE = "this is not a rule"


def page_html(host: str) -> str:
    return ("<!doctype html><title>Thoron rules check</title>"
            f'<img src="http://{host}/ad.png" alt=""><img src="/own.png" alt="">'
            "<script>window.inline = 'ran';</script>"
            f'<script src="http://{OTHER_HOST}/lib.js"></script>')


def rules_text(host: str, noop: bool, allow: bool = False) -> str:
    lines = ["# Thoron rules check", "* * 3p-script block", f"{PAGE_HOST} {host} * allow",
             f"{PAGE_HOST} * inline-script block", NOT_A_RULE]
    if noop:
        lines.append(f"{PAGE_HOST} * 3p-script noop")
    if allow:
        lines.append(f"{PAGE_HOST} {OTHER_HOST} * allow")
    return "\n".join(lines) + "\n"


def problems_for(step: str, seen: dict, host: str) -> list[str]:
    want = {"none": {"other": True, "ad": False, "inline": True},
            "rules": {"other": False, "ad": True, "inline": False},
            "noop": {"other": True, "ad": True, "inline": False},
            "switch": {"other": False, "ad": True, "inline": False},
            "allow": {"other": True, "ad": True, "inline": False}}[step]
    out = []
    if seen.get("other") != want["other"]:
        out.append(f"{step}: the other site's script was {'asked for' if seen.get('other') else 'not asked for'}")
    if seen.get("ad") != want["ad"]:
        out.append(f"{step}: the ad image of {host} was {'asked for' if seen.get('ad') else 'not asked for'}")
    if seen.get("inline") != want["inline"]:
        out.append(f"{step}: the page's own script {'ran' if seen.get('inline') else 'did not run'}")
    if not seen.get("own"):
        out.append(f"{step}: the page's own image was not asked for")
    return out


class Server:
    def __init__(self, host: str):
        self.asked: set[tuple[str, str]] = set()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                path = self.path.split("?")[0]
                if name == "127.0.0.1" and path == "/warm.html":
                    body, ctype = WARM_HTML.encode(), "text/html; charset=utf-8"
                elif name == PAGE_HOST and path == "/page.html":
                    body, ctype = page_html(host).encode(), "text/html; charset=utf-8"
                else:
                    server.asked.add((name, path))
                    body, ctype = ((b"window.other = 'ran';", "text/javascript") if path.endswith(".js")
                                   else (b"\x89PNG\r\n", "image/png"))
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
    return reply.get("result", {}).get("value")


def run(browser: Path, work: Path, host: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="rules-", dir=work))
    problems: list[str] = []
    with Server(host) as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, OTHER_HOST, host], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            _open(port, f"http://127.0.0.1:{server.port}/warm.html")
            time.sleep(4)
            settings = WebSocket(_open(port, "chrome://adblock/#rules")["webSocketDebuggerUrl"])
            page = WebSocket(_open(port, f"http://{PAGE_HOST}/page.html")["webSocketDebuggerUrl"])
            try:
                for step in ("none", "rules", "noop", "switch", "allow"):
                    named = []
                    if step == "switch":
                        _eval(settings, "document.querySelector('[data-setting=\"default-3p-script\"]').click(); 1")
                        time.sleep(1)
                        if not _eval(settings, "document.querySelector('[data-setting=\"default-3p-script\"]')"
                                               ".checked"):
                            named.append("switch: the setting for third-party scripts did not turn on")
                    if step != "none":
                        text = rules_text(host, noop=step != "rules", allow=step == "allow")
                        _eval(settings, f"document.getElementById('my-rules').value = {json.dumps(text)};"
                                        "document.getElementById('save-rules').click(); 1")
                        time.sleep(1.5)
                        message = _eval(settings, "document.getElementById('message').textContent") or ""
                        if NOT_A_RULE not in message:
                            named.append(f"{step}: the line that is not a rule was not named ({message!r})")
                    server.asked.clear()
                    page.call("Page.reload", ignoreCache=True)
                    time.sleep(SETTLE_S)
                    seen = {"other": (OTHER_HOST, "/lib.js") in server.asked,
                            "ad": (host, "/ad.png") in server.asked,
                            "own": (PAGE_HOST, "/own.png") in server.asked,
                            "inline": _eval(page, "window.inline === 'ran'")}
                    found = problems_for(step, seen, host) + named
                    print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
                    problems += found
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
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    host = ad_host((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if not host:
        print("RULES CHECK: FAILED (EasyList holds no plain host rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, host)
    for problem in problems:
        print(problem)
    print("RULES CHECK: PASSED" if not problems else f"RULES CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
