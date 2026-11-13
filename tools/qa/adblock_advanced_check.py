#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the settings uBlock Origin has that came last: "Auto-update filter lists", "I am an
advanced user" and "Block media elements larger than N kB", checked end to end and offline (ROADMAP P5.46).
("Make use of the context menu" is checked by adblock_context_check.py, which needs a window.)

A local server serves the filter lists (the updater is pointed at it, as in adblock_update_check.py) and a test
page under a name of its own with a WAV sound of about 88 kB (host-resolver rules; every other name fails, so
nothing leaves the PC). The profile starts with "Auto-update filter lists" off. Steps:

    autoupdate  no list is downloaded on its own; the setting reads off; "Update now" downloads them
    grid        the menu shows the grid of rules; with "I am an advanced user" off it does not; on, it does
    media       with "Block media elements larger than" on: at 50 kB the sound fails to load, at 200 kB it loads
    saved       options.json on disk has the size and auto-update off

    py -3 -I tools/qa/adblock_advanced_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_menu_check import wav_bytes  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "advanced-check.test"
SETTINGS_URL = "chrome://adblock/"
MENU_URL = "chrome://adblock-menu.top-chrome/"
QUIET_S = 8.0
SETTLE_S = 3.0
LIST_TEXT = "! Title: Thoron advanced check\n||never-used.test^\n"
SOUND_KB = len(wav_bytes()) // 1024


def page_html() -> str:
    return ("<!doctype html><title>Thoron advanced check</title>"
            '<audio id="sound" src="/sound.wav" preload="auto"></audio>'
            "<script>window.report = {sound: 'waiting'};"
            "const s = document.getElementById('sound');"
            "s.addEventListener('loadeddata', () => { window.report.sound = 'loaded'; });"
            "s.addEventListener('error', () => { window.report.sound = 'error'; });</script>")


def autoupdate_problems(before: int, setting, after: int) -> list[str]:
    out = []
    if before:
        out.append(f"autoupdate: {before} list(s) downloaded on their own with auto-update off")
    if setting is not False:
        out.append(f"autoupdate: the setting reads {setting!r}, not off")
    if not after:
        out.append("autoupdate: \"Update now\" downloaded nothing")
    return out


def grid_problems(shown: list) -> list[str]:
    want = [True, False, True]
    return [] if shown == want else [f"grid: the menu's grid was shown {shown}, not {want}"]


def media_problems(small, large) -> list[str]:
    out = []
    if small != "error":
        out.append(f"media: at 50 kB the {SOUND_KB} kB sound is {small!r}, not blocked")
    if large != "loaded":
        out.append(f"media: at 200 kB the {SOUND_KB} kB sound is {large!r}, not loaded")
    return out


def saved_problems(options: dict) -> list[str]:
    out = []
    if options.get("media-kb") != 200:
        out.append(f"saved: options.json has media-kb {options.get('media-kb')!r}, not 200")
    if options.get("auto-update") is not False:
        out.append(f"saved: options.json has auto-update {options.get('auto-update')!r}, not false")
    return out


class Server:
    def __init__(self):
        self.lists_asked = 0
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                if path.startswith("/lists/"):
                    server.lists_asked += 1
                    body, ctype = LIST_TEXT.encode(), "text/plain; charset=utf-8"
                elif path == "/sound.wav":
                    body, ctype = wav_bytes(), "audio/wav"
                else:
                    body, ctype = page_html().encode(), "text/html; charset=utf-8"
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


def _launch(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            "--enable-features=ThoronNativeAdblock",
            f"--thoron-adblock-lists-url-for-testing=http://127.0.0.1:{port}/lists/",
            f"--host-resolver-rules=MAP {PAGE_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def run(browser: Path, work: Path) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="advanced-", dir=work))
    store = profile / "Thoron Adblock"
    store.mkdir()
    (store / "options.json").write_text(json.dumps({"auto-update": False}), encoding="utf-8")
    problems: list[str] = []
    with Server() as server:
        proc = _launch(browser, profile, server.port)
        port = None
        settings = menu = page = None
        try:
            port = _devtools_port(profile)
            # autoupdate: nothing on its own (in testing the first check is a second after start)
            time.sleep(QUIET_S)
            before = server.lists_asked
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            time.sleep(1.5)
            setting = _eval(settings, "document.querySelector('[data-setting=\"auto-update\"]').checked")
            _eval(settings, "document.getElementById('update-now').click(); 1")
            for _ in range(30):
                time.sleep(0.5)
                if server.lists_asked > before:
                    break
            found = autoupdate_problems(before, setting, server.lists_asked - before)
            print(f"{'PASS' if not found else 'FAIL'}  autoupdate: on their own {before}, setting {setting}, "
                  f"after Update now {server.lists_asked - before}")
            problems += found

            # media first: the page, then the menu works on it
            page_target = _open(port, f"http://{PAGE_HOST}/page.html")
            page = WebSocket(page_target["webSocketDebuggerUrl"])
            _eval(settings, "document.querySelector('[data-setting=\"default-media\"]').click(); 1")
            sounds = []
            for kb in (50, 200):
                _eval(settings, f"(() => {{ const m = document.getElementById('media-kb'); m.value = '{kb}';"
                                "m.dispatchEvent(new Event('change')); return 1; })()")
                time.sleep(1)
                page.call("Page.reload", ignoreCache=True)
                time.sleep(SETTLE_S)
                sounds.append(_eval(page, "window.report && window.report.sound"))
            found = media_problems(*sounds)
            print(f"{'PASS' if not found else 'FAIL'}  media: at 50 kB {sounds[0]}, at 200 kB {sounds[1]}")
            problems += found

            # grid: the menu, opened as a tab, works on the active tab
            menu = WebSocket(_open(port, MENU_URL)["webSocketDebuggerUrl"])
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{page_target['id']}", timeout=10).read()
            shown = []
            for click in (False, True, True):
                if click:
                    _eval(settings, "document.querySelector('[data-setting=\"advanced\"]').click(); 1")
                time.sleep(2)
                shown.append(_eval(menu, "!document.getElementById('grid-box').hidden"))
            found = grid_problems(shown)
            print(f"{'PASS' if not found else 'FAIL'}  grid: shown {shown}")
            problems += found

            time.sleep(1)
            try:
                options = json.loads((store / "options.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                options = {}
            found = saved_problems(options)
            print(f"{'PASS' if not found else 'FAIL'}  saved: {options}")
            problems += found
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            for ws in (settings, menu, page):
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
    print("ADVANCED CHECK: PASSED" if not problems else f"ADVANCED CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
