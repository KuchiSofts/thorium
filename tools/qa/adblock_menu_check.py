#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the toolbar menu, its switches, the element picker and the zapper, checked end to end and
offline (ROADMAP P5.31).

The menu (chrome://adblock-menu.top-chrome) normally opens from the shield in the toolbar; opened as a tab, it
works on the tab before it, which is how this check drives it. A local server serves a test page under a name
of its own (host-resolver rules; every other name fails, so nothing leaves the PC). The page has an image from
an ad host EasyList blocks, an element a generic EasyList hide rule hides, a web font, a WAV sound larger than
the large-media limit, an element to pick and one to zap. Steps:

    menu      the menu names the page's site, counts the blocked image, lists the ad host
    collapse  a blocked 300x250 ad image and ad frame take up no space on the page
    fonts     with "Remote fonts" on, the font is never asked for; off again, it is
    media     with "Large media" on, the sound fails to load; off again, it loads
    cosmetic  with "No hiding" on, the generic hide rule hides nothing; off again, it hides
    power     with the big switch off, the ad host is asked for; on again, it is not
    picker    "Block element", a click on the element and Enter: a rule for the site is in My filters and
              the element is hidden after a reload
    zapper    "Zapper" and a click on an element: it is gone, the rest of the page stays

    py -3 -I tools/qa/adblock_menu_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import http.server
import json
import re
import shutil
import struct
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import NOT_FOR_REPORTS, WARM_HTML  # noqa: E402
from tools.qa.adblock_earlyhints_check import ad_host  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "menu-check.test"
MENU_URL = "chrome://adblock-menu.top-chrome/"
MEDIA_LIMIT = 50 * 1024
SETTLE_S = 3.0
GENERIC_RE = re.compile(r"##\.([A-Za-z][A-Za-z0-9_-]{2,40})")


def generic_class(lists_text: str) -> str | None:
    """The class of the first plain generic hide rule of EasyList (`##.name`)."""
    current = ""
    for line in (line.strip() for line in lists_text.splitlines()):
        if line.startswith("! thoron-list: "):
            current = line.removeprefix("! thoron-list: ").strip()
        elif current == "easylist" and (m := GENERIC_RE.fullmatch(line)) and \
                not any(word in m.group(1).lower() for word in NOT_FOR_REPORTS):
            return m.group(1)
    return None


def wav_bytes(seconds: float = 2.0, rate: int = 22050) -> bytes:
    """A real, silent, mono 16-bit WAV file, larger than the large-media limit."""
    frames = int(seconds * rate)
    data = b"\x00\x00" * frames
    header = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
              struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(data)))
    return header + data


FONT_CSS = b"@font-face{font-family:Check;src:url(/check.woff2) format('woff2');}#text{font-family:Check,serif;}"


def page_html(host: str, generic: str) -> str:
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron menu check</title>'
            '<link rel="stylesheet" href="/font.css">'
            '<style>#pick-target{width:300px;height:80px;background:#fd0;margin:20px}'
            '#zap-me{width:300px;height:60px;background:#0cf;margin:20px}</style></head><body>'
            '<p id="text">Text in a web font</p>'
            '<div id="pick-target" class="thoron-offer">Special offer</div>'
            '<div id="zap-me">Zap me</div><p id="keep">Stays</p>'
            f'<div class="{generic}" id="generic">generic ad</div>'
            f'<img id="ad" src="http://{host}/banner.gif" width="1" height="1" alt="">'
            f'<img id="ad-box" src="http://{host}/box.gif" width="300" height="250" alt="">'
            f'<iframe id="ad-frame" src="http://{host}/frame.html" width="300" height="250"></iframe>'
            '<audio id="sound" src="/sound.wav" preload="auto"></audio>'
            '<script>window.report = {sound: "waiting"};'
            "const s = document.getElementById('sound');"
            "s.addEventListener('loadeddata', () => { window.report.sound = 'loaded'; });"
            "s.addEventListener('error', () => { window.report.sound = 'error'; });"
            "</script></body></html>")


def menu_problems(menu: dict, host: str) -> list[str]:
    out = []
    if menu.get("site") != PAGE_HOST:
        out.append(f"the menu names {menu.get('site')!r}, not {PAGE_HOST}")
    if not menu.get("pageCount"):
        out.append("the menu counts nothing blocked on the page")
    if not any(site == host for site, _ in menu.get("sites") or []):
        out.append(f"the menu does not list {host}")
    return out


def collapse_problems(seen: dict) -> list[str]:
    return [f"the blocked {what} still takes {seen.get(key)} px" for what, key in
            (("ad image", "box"), ("ad frame", "frame")) if seen.get(key) != 0]


def switch_problems(name: str, on: bool, seen: dict) -> list[str]:
    state = "on" if on else "off"
    if name == "fonts" and seen.get("font") == on:
        return [f"with Remote fonts {state}, the font was " + ("asked for" if on else "not asked for")]
    if name == "media" and seen.get("sound") != ("error" if on else "loaded"):
        return [f"with Large media {state}, the sound is {seen.get('sound')!r}"]
    if name == "cosmetic" and seen.get("generic") != ("shown" if on else "hidden"):
        return [f"with No hiding {state}, the generic ad is {seen.get('generic')!r}"]
    if name == "power" and seen.get("ad") != on:
        return [f"with blocking {'off' if on else 'on'} for the site, the ad host was " +
                ("not asked for" if on else "asked for")]
    return []


def picker_problems(my_filters: str, element: str) -> list[str]:
    out = []
    if not any(line.startswith(f"{PAGE_HOST}##") for line in my_filters.splitlines()):
        out.append("the picker added no rule for the site to My filters")
    if element != "hidden":
        out.append(f"after a reload the picked element is {element!r}")
    return out


def zapper_problems(result: dict) -> list[str]:
    out = []
    if not result.get("zapped"):
        out.append("the zapped element is still in the page")
    if not result.get("kept"):
        out.append("the zapper took more than the element")
    return out


class Server:
    def __init__(self, host: str, generic: str):
        self.asked: list[tuple[str, str]] = []
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, ctype: str, body: bytes):
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                path = self.path.split("?")[0]
                server.asked.append((name, path))
                if name == "127.0.0.1" and path == "/warm.html":
                    self._send("text/html; charset=utf-8", WARM_HTML.encode())
                elif name == PAGE_HOST and path == "/page.html":
                    self._send("text/html; charset=utf-8", page_html(host, generic).encode())
                elif name == PAGE_HOST and path == "/font.css":
                    self._send("text/css", FONT_CSS)
                elif name == PAGE_HOST and path == "/check.woff2":
                    self._send("font/woff2", b"wOF2" + b"\x00" * 60)
                elif name == PAGE_HOST and path == "/sound.wav":
                    self._send("audio/wav", wav_bytes())
                else:
                    self._send("image/gif", b"GIF89a")

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


READ_MENU = """JSON.stringify({site: document.getElementById('site').textContent,
  power: document.getElementById('power').getAttribute('aria-pressed'),
  pageCount: Number(document.getElementById('page-count').textContent.replace(/\\D/g, '')),
  sites: Array.from(document.querySelectorAll('#sites li')).map((li) =>
    [li.querySelector('.host').textContent, Number(li.querySelector('.n').textContent.replace(/\\D/g, ''))])})"""
READ_PAGE = """JSON.stringify({sound: window.report && window.report.sound,
  generic: (() => { const e = document.getElementById('generic');
    return !e ? 'gone' : getComputedStyle(e).display === 'none' ? 'hidden' : 'shown'; })(),
  promo: (() => { const e = document.getElementById('pick-target');
    return !e ? 'gone' : getComputedStyle(e).display === 'none' ? 'hidden' : 'shown'; })(),
  zapped: !document.getElementById('zap-me'), kept: !!document.getElementById('keep'),
  box: Math.round(document.getElementById('ad-box').getBoundingClientRect().width),
  frame: Math.round(document.getElementById('ad-frame').getBoundingClientRect().width)})"""


class Run:
    def __init__(self, browser: Path, work: Path, server: Server, host: str):
        self.server, self.host = server, host
        self.profile = Path(tempfile.mkdtemp(prefix="menu-", dir=work))
        self.proc = _launch(browser, self.profile, server.port, [PAGE_HOST, host], native=True)
        self.port = _devtools_port(self.profile)
        _open(self.port, f"http://127.0.0.1:{server.port}/warm.html")
        time.sleep(4)
        page = _open(self.port, f"http://{PAGE_HOST}/page.html")
        self.page = WebSocket(page["webSocketDebuggerUrl"])
        time.sleep(SETTLE_S)
        self.menu = WebSocket(_open(self.port, MENU_URL)["webSocketDebuggerUrl"])
        time.sleep(2)
        # The page stays in front: a tab behind another gets no mouse input and loads no media. The menu,
        # a tab of its own here, then works on the active tab, as it does from the toolbar.
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/activate/{page['id']}", timeout=10).read()
        time.sleep(1)

    def read_menu(self) -> dict:
        return json.loads(_eval(self.menu, READ_MENU) or "{}")

    def read_page(self) -> dict:
        return json.loads(_eval(self.page, READ_PAGE) or "{}")

    def click_menu(self, selector: str) -> None:
        _eval(self.menu, f"document.querySelector({json.dumps(selector)}).click(); 1")

    def after_reload(self) -> dict:
        """What the page and the server saw after the menu reloaded the page."""
        self.server.asked.clear()
        time.sleep(SETTLE_S + 1)
        seen = self.read_page()
        seen["font"] = (PAGE_HOST, "/check.woff2") in self.server.asked
        seen["ad"] = any(name == self.host for name, _ in self.server.asked)
        return seen

    def click_page(self, element_id: str) -> None:
        box = json.loads(_eval(self.page, f"JSON.stringify(document.getElementById({json.dumps(element_id)})"
                                          ".getBoundingClientRect())"))
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
            time.sleep(0.2)

    def press_enter(self) -> None:
        for kind in ("keyDown", "keyUp"):
            self.page.call("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter",
                           windowsVirtualKeyCode=13, text="\r" if kind == "keyDown" else "")

    def my_filters(self) -> str:
        try:
            return (self.profile / "Thoron Adblock" / "my-filters.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def close(self) -> None:
        for ws in (self.menu, self.page):
            try:
                ws.close()
            except OSError:
                pass
        _close_browser(self.port, self.proc)
        shutil.rmtree(self.profile, ignore_errors=True)


def run(browser: Path, work: Path, host: str, generic: str) -> list[str]:
    problems: list[str] = []
    with Server(host, generic) as server:
        r = None
        try:
            r = Run(browser, work, server, host)
            menu = r.read_menu()
            found = menu_problems(menu, host)
            print(f"{'PASS' if not found else 'FAIL'}  menu: {menu}")
            problems += [f"menu: {p}" for p in found]
            seen = r.read_page()
            found = collapse_problems(seen)
            print(f"{'PASS' if not found else 'FAIL'}  collapse: image {seen.get('box')} px, frame {seen.get('frame')} px")
            problems += [f"collapse: {p}" for p in found]
            for name, selector in (("fonts", "[data-switch=fonts]"), ("media", "[data-switch=media]"),
                                   ("cosmetic", "[data-switch=cosmetic]"), ("power", "#power")):
                for on in (True, False):
                    r.click_menu(selector)
                    seen = r.after_reload()
                    found = switch_problems(name, on, seen)
                    print(f"{'PASS' if not found else 'FAIL'}  {name} {'on' if on else 'off'}: {seen}")
                    problems += [f"{name}: {p}" for p in found]
            # the picker: the menu starts it in the page; a click picks; Enter creates the rule
            r.click_menu("#picker")
            time.sleep(1)
            r.click_page("pick-target")
            time.sleep(0.5)
            r.press_enter()
            time.sleep(2)
            r.page.call("Page.reload")
            time.sleep(SETTLE_S)
            mine = r.my_filters()
            found = picker_problems(mine, r.read_page().get("promo"))
            print(f"{'PASS' if not found else 'FAIL'}  picker: My filters {mine.strip()!r}")
            problems += [f"picker: {p}" for p in found]
            # the zapper
            r.click_menu("#zapper")
            time.sleep(1)
            r.click_page("zap-me")
            time.sleep(0.5)
            r.page.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape",
                        windowsVirtualKeyCode=27)
            result = r.read_page()
            found = zapper_problems(result)
            print(f"{'PASS' if not found else 'FAIL'}  zapper: {result}")
            problems += [f"zapper: {p}" for p in found]
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
    text = (a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8")
    host, generic = ad_host(text), generic_class(text)
    if not host or not generic:
        print("MENU CHECK: FAILED (EasyList holds no plain host rule or generic hide rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, host, generic)
    for problem in problems:
        print(problem)
    print("MENU CHECK: PASSED" if not problems else f"MENU CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
