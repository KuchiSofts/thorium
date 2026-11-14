#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's switch lines in My rules, checked end to end and offline (ROADMAP P5.58).

My rules as uBlock Origin exports them hold switch lines too ("no-large-media: example.com true"). Saved here,
each is applied to the switches of its site or to the setting for every site, as uBlock Origin has it, and the
export of My rules writes them again. A local server serves a page with a script under names of its own
(host-resolver rules; every other name fails, so nothing leaves the PC). Steps:

    apply     saving uBlock Origin's text applies its switch lines and keeps only the rules in the box
    sites     the sites' switches and settings are as the lines say
    unknown   a line that has no meaning here ("no-popups: * true") is named and not used
    script    "no-scripting: js-site.test true" stops the scripts of http://js-site.test and of a host under it
    export    the export of My rules has the rules and every switch line
    menu      the menu's JavaScript switch, off on that site, lets its scripts run again

    py -3 -I tools/qa/adblock_switchlines_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

SETTINGS_URL = "chrome://adblock/"
MENU_URL = "chrome://adblock-menu.top-chrome/"
JS_HOST = "js-site.test"
SUB_HOST = f"www.{JS_HOST}"
SETTLE_S = 3.0
RULES = "* ads-rule.test * block\nbehind-the-scene * * noop\nbehind-the-scene * 3p noop\n"
# as uBlock Origin writes them: its defaults, and a switch of each kind
SWITCHES = ("no-csp-reports: * true\nno-large-media: behind-the-scene false\nno-scripting: behind-the-scene false\n"
            "no-popups: popup-site.test true\nno-remote-fonts: font-site.test true\n"
            "no-large-media: media-site.test true\nno-cosmetic-filtering: * true\n"
            "no-cosmetic-filtering: hide-site.test false\nno-strict-blocking: strict-site.test true\n"
            f"no-scripting: {JS_HOST} true\n")
UNKNOWN = "no-popups: * true\nno-csp-reports: csp-site.test true\n"
WANT_SWITCHES = {"popup-site.test": ["popups"], "font-site.test": ["fonts"], "media-site.test": ["media"],
                 "hide-site.test": ["-cosmetic"], "strict-site.test": ["no-strict"]}
WANT_EXPORT = ("no-csp-reports: * true", "no-cosmetic-filtering: * true", "no-popups: popup-site.test true",
               "no-remote-fonts: font-site.test true", "no-large-media: media-site.test true",
               "no-cosmetic-filtering: hide-site.test false", "no-strict-blocking: strict-site.test true",
               f"no-scripting: {JS_HOST} true")
PAGE = "<!doctype html><title>still</title><script>document.title = 'ran';</script>"


def apply_problems(message: str, box: str) -> list[str]:
    out = []
    if not message.startswith("Your rules are saved and in use. ") or "switch lines were applied" not in message:
        out.append(f"apply: the page says {message!r}")
    if box.strip() != RULES.strip():
        out.append(f"apply: the box holds {box!r}")
    return out


def sites_problems(sites: dict, settings: dict) -> list[str]:
    out = []
    got = {s["host"]: sorted(s["names"]) for s in sites.get("switches", [])}
    for host, names in WANT_SWITCHES.items():
        if got.get(host) != names:
            out.append(f"sites: {host} has {got.get(host)}, not {names}")
    if JS_HOST not in sites.get("javascript", []):
        out.append(f"sites: JavaScript is not off on {JS_HOST}: {sites.get('javascript')}")
    for name in ("block-csp-reports", "default-cosmetic"):
        if settings.get(name) is not True:
            out.append(f"sites: the setting {name} is not on")
    if "behind-the-scene" in got:
        out.append("sites: behind-the-scene got switches")
    return out


def unknown_problems(message: str) -> list[str]:
    if not message.startswith("These lines are not rules and are not used: "):
        return [f"unknown: the page says {message!r}"]
    return [f"unknown: {line} is not named" for line in UNKNOWN.splitlines() if line not in message]


def script_problems(titles: dict) -> list[str]:
    return [f"script: on {host} the script ran" for host, title in titles.items() if title != "still"]


def export_problems(text: str) -> list[str]:
    lines = text.splitlines()
    out = [f"export: no {line!r}" for line in (*RULES.splitlines(), *WANT_EXPORT) if line not in lines]
    if any(line.startswith("no-") and "behind-the-scene" in line for line in lines):
        out.append("export: it has a behind-the-scene switch")
    return out


def menu_problems(title: str) -> list[str]:
    return [] if title == "ran" else [f"menu: with JavaScript on again the page's title is {title!r}"]


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
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def _wait_message(ws: WebSocket, words: str, seconds: float = 30) -> str:
    deadline = time.monotonic() + seconds
    text = ""
    while time.monotonic() < deadline:
        text = _eval(ws, "document.getElementById('message').textContent") or ""
        if words in text:
            break
        time.sleep(0.5)
    return text


ASK = """(async () => {{ const {{sendWithPromise}} = await import('chrome://resources/js/cr.js');
  return JSON.stringify(await sendWithPromise({what})); }})()"""


def save(ws: WebSocket, text: str) -> None:
    _eval(ws, "(() => { const box = document.getElementById('my-rules');"
              f" box.value = {json.dumps(text)}; document.getElementById('message').textContent = '';"
              " document.getElementById('save-rules').click(); return 1; })()")


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="switchlines-", dir=work))
    downloads = Path(tempfile.mkdtemp(prefix="switchlines-saved-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server() as server:
        proc = _launch(browser, profile, server.port, [JS_HOST, SUB_HOST], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=10) as reply:
                browser_ws = WebSocket(json.loads(reply.read())["webSocketDebuggerUrl"])
            browser_ws.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads),
                            eventsEnabled=True)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S)
                save(settings, RULES + SWITCHES)
                message = _wait_message(settings, "Your rules are saved")
                box = _eval(settings, "document.getElementById('my-rules').value") or ""
                report("apply", apply_problems(message, box), message)

                sites = json.loads(_eval(settings, ASK.format(what="'getSites'")) or "{}")
                values = json.loads(_eval(settings, ASK.format(what="'getSettings'")) or "{}")
                report("sites", sites_problems(sites, values), sites.get("switches"))

                save(settings, RULES + UNKNOWN)
                message = _wait_message(settings, "These lines")
                report("unknown", unknown_problems(message), message)

                titles = {}
                for host in (JS_HOST, SUB_HOST):
                    page = WebSocket(_open(port, f"http://{host}/page.html")["webSocketDebuggerUrl"])
                    time.sleep(SETTLE_S)
                    titles[host] = _eval(page, "document.title")
                    page.close()
                report("script", script_problems(titles), titles)

                _eval(settings, "document.getElementById('export-rules').click(); 1")
                text = ""
                for _ in range(40):
                    files = [f for f in downloads.glob("my-rules-*.txt") if not f.name.endswith(".crdownload")]
                    if files:
                        time.sleep(0.5)
                        text = files[0].read_text(encoding="utf-8")
                        break
                    time.sleep(0.5)
                report("export", export_problems(text), text.strip().splitlines())

                # the menu, a tab of its own, works on the active tab: the page in front
                target = _open(port, f"http://{JS_HOST}/page.html")
                page = WebSocket(target["webSocketDebuggerUrl"])
                time.sleep(SETTLE_S)
                menu = WebSocket(_open(port, MENU_URL)["webSocketDebuggerUrl"])
                time.sleep(2)
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{target['id']}", timeout=10).read()
                time.sleep(1)
                _eval(menu, "document.querySelector('[data-switch=javascript]').click(); 1")
                time.sleep(SETTLE_S)  # the menu reloads the page
                page.call("Page.reload", ignoreCache=True)
                time.sleep(SETTLE_S)
                title = _eval(page, "document.title")
                report("menu", menu_problems(title), title)
                menu.close()
                page.close()
            finally:
                settings.close()
                browser_ws.close()
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            for folder in (profile, downloads):
                shutil.rmtree(folder, ignore_errors=True)
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
    print("SWITCH LINES CHECK: PASSED" if not problems else f"SWITCH LINES CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
