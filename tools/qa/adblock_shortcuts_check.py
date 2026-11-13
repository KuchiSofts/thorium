#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's keyboard shortcuts, checked end to end and offline (ROADMAP P5.50).

The shortcuts are set on chrome://adblock by pressing the keys in a box, as a person would; then the keys are
pressed on a page. A local server serves a test page under a name of its own (host-resolver rules; every other
name fails, so nothing leaves the PC) with a script that writes the title and an element to zap. Steps:

    set         Ctrl+Alt+Z for the zapper, Ctrl+Alt+J for JavaScript: the boxes show them
    zapper      Ctrl+Alt+Z on the page, then a click on the element: it is gone
    javascript  Ctrl+Alt+J: the page reloads without its script; again: with it
    unset       a key press that is no shortcut (Ctrl+Alt+Q) reaches the page; after Clear, Ctrl+Alt+Z too

    py -3 -I tools/qa/adblock_shortcuts_check.py --browser <out>\\thoron.exe --work <scratch dir>
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

PAGE_HOST = "shortcuts-check.test"
SETTINGS_URL = "chrome://adblock/"
SETTLE_S = 2.5
PAGE = ("<!doctype html><title>no script</title>"
        '<p id="zap-me" style="width:300px;height:80px;background:#c33">zap me</p><p id="keep">stays</p>'
        "<script>document.title = 'script ran'; window.keys = [];"
        "addEventListener('keydown', (e) => window.keys.push(e.code));</script>")
# CDP modifiers: Alt 1, Ctrl 2
CTRL_ALT = 3
KEYS = {"Z": ("KeyZ", 90), "J": ("KeyJ", 74), "Q": ("KeyQ", 81)}


def set_problems(shown: dict) -> list[str]:
    want = {"zapper": "Ctrl+Alt+Z", "javascript": "Ctrl+Alt+J"}
    return [f"set: the box for {name} shows {shown.get(name)!r}, not {keys!r}"
            for name, keys in want.items() if shown.get(name) != keys]


def page_problems(step: str, seen: dict, *, script: bool, zapped: bool | None = None,
                  page_keys: list | None = None) -> list[str]:
    out = []
    if (seen.get("title") == "script ran") != script:
        out.append(f"{step}: the page's script {'did not run' if script else 'ran'} ({seen.get('title')!r})")
    if zapped is not None and seen.get("zapped") != zapped:
        out.append(f"{step}: the element is {'gone' if seen.get('zapped') else 'still there'}")
    if page_keys is not None and seen.get("keys") != page_keys:
        out.append(f"{step}: the page got the keys {seen.get('keys')}, not {page_keys}")
    return out


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def _press(page: WebSocket, letter: str) -> None:
    code, vk = KEYS[letter]
    for kind in ("rawKeyDown", "keyUp"):
        page.call("Input.dispatchKeyEvent", type=kind, modifiers=CTRL_ALT, code=code, key=letter.lower(),
                  windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
        time.sleep(0.1)


def _set(settings: WebSocket, command: str, letter: str) -> None:
    code, _ = KEYS[letter]
    _eval(settings, f"(() => {{ const box = document.querySelector('#shortcuts input[data-command={json.dumps(command)}]');"
                    " box.focus(); box.dispatchEvent(new KeyboardEvent('keydown', {key: "
                    f"{json.dumps(letter.lower())}, code: {json.dumps(code)}, ctrlKey: true, altKey: true,"
                    " bubbles: true, cancelable: true})); return 1; })()")
    time.sleep(1.5)


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


READ_PAGE = ("JSON.stringify({title: document.title, zapped: !document.getElementById('zap-me'),"
             " keys: window.keys || []})")


def run(browser: Path, work: Path) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="shortcuts-", dir=work))
    problems: list[str] = []
    with Server() as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST], native=True)
        port = None
        settings = page = None
        try:
            port = _devtools_port(profile)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            time.sleep(2)
            _set(settings, "zapper", "Z")
            _set(settings, "javascript", "J")
            shown = json.loads(_eval(settings, "JSON.stringify(Object.fromEntries(Array.from("
                                               "document.querySelectorAll('#shortcuts input'))"
                                               ".map((i) => [i.dataset.command, i.value])))") or "{}")
            found = set_problems(shown)
            print(f"{'PASS' if not found else 'FAIL'}  set: {shown}")
            problems += found

            target = _open(port, f"http://{PAGE_HOST}/page.html")
            page = WebSocket(target["webSocketDebuggerUrl"])
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{target['id']}", timeout=10).read()
            time.sleep(SETTLE_S)

            # zapper: the shortcut, then a click on the element
            _press(page, "Z")
            time.sleep(1)
            box = json.loads(_eval(page, "JSON.stringify(document.getElementById('zap-me').getBoundingClientRect())"))
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
                time.sleep(0.2)
            time.sleep(0.5)
            seen = json.loads(_eval(page, READ_PAGE) or "{}")
            found = page_problems("zapper", seen, script=True, zapped=True)
            print(f"{'PASS' if not found else 'FAIL'}  zapper: {seen}")
            problems += found
            page.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape",
                      windowsVirtualKeyCode=27)

            # javascript: off, then on again (each reloads the page)
            for step, script in (("javascript-off", False), ("javascript-on", True)):
                _press(page, "J")
                time.sleep(SETTLE_S)
                seen = json.loads(_eval(page, READ_PAGE) or "{}")
                found = page_problems(step, seen, script=script)
                print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen['title']!r}")
                problems += found

            # keys that are no shortcut reach the page; after Clear, the zapper's too
            _eval(settings, "document.querySelector('#shortcuts input[data-command=\"zapper\"]')"
                            ".nextElementSibling.click(); 1")
            time.sleep(1.5)
            _press(page, "Q")
            _press(page, "Z")
            time.sleep(0.5)
            seen = json.loads(_eval(page, READ_PAGE) or "{}")
            found = page_problems("unset", seen, script=True, page_keys=["KeyQ", "KeyZ"])
            print(f"{'PASS' if not found else 'FAIL'}  unset: the page got {seen.get('keys')}")
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
    print("SHORTCUTS CHECK: PASSED" if not problems else f"SHORTCUTS CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
