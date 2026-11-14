#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the tools of chrome://adblock that uBlock Origin has too, checked end to end and offline
(ROADMAP P5.54).

A local server serves a test page under a name of its own (host-resolver rules; every other name fails, so
nothing leaves the PC) with an image of a host My filters block, an image and a script of a plain host. Files
the page saves go to a folder of the run. Steps:

    filters     saving My filters with a line that is no filter names that line, and only that line
    types       the logger's type filter offers the page's types; "script" shows only the script
    hidden      (P5.61) the logger lists the site's and the generic hide rule that hid an element of the
                page, as "hidden", and not the one that hid nothing
    pause       while paused, a new request of the page is not shown; after "Resume" it is
    clear       after "Clear" nothing is shown, and a request made after it is
    export      the logger's "Export" saves what it shows, one request a line
    sites       "Import" of allowed sites adds a site, a pattern and an address; "Export" saves all three
    rules       "Import and append" of My rules adds the file's lines below; "Export" saves the box
    colorblind  "Color-blind friendly" colours the menu's grid blue and orange; off, the menu is as before
    info        "Copy troubleshooting info" gives the version, the lists and the changed settings, and no
                address of a page visited or a site allowed

    py -3 -I tools/qa/adblock_tools_check.py --browser <out>\\thoron.exe --work <scratch dir>
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

PAGE_HOST = "tools-check.test"
BLOCKED_HOST = "blocked-tools.test"
PLAIN_HOST = "plain-tools.test"
TITLE = "Thoron tools check"
SETTINGS_URL = "chrome://adblock/"
MENU_URL = "chrome://adblock-menu.top-chrome/"
SETTLE_S = 3.0
GOOD_FILTER = f"||{BLOCKED_HOST}^"
BAD_FILTER = "||bad-tools.test^$nosuchoption"
# hide rules of the site and for every site, and one that hides nothing on the page
HIDE_RULES = f"{PAGE_HOST}##.thoron-promo\n##.thoron-generic-ad\n{PAGE_HOST}##.not-on-the-page\n"
HIDDEN = {"##.thoron-promo", "##.thoron-generic-ad"}
IMPORTED_SITES = "imported-one.test\n[*.]imported-two.test\n# a note\nhttps://imported-three.test/page\n"
WANTED_SITES = ("[*.]imported-one.test", "[*.]imported-two.test", "[*.]imported-three.test")
IMPORTED_RULES = "* imported-rule.test * block\n"
# the colours of the menu's grid with "Color-blind friendly" on: light, dark
COLORBLIND_ALLOW = ("#1a73e8", "#8ab4f8")


def page_html() -> str:
    return (f"<!doctype html><title>{TITLE}</title>"
            f'<img src="http://{BLOCKED_HOST}/ad.png" alt=""><img src="http://{PLAIN_HOST}/pic.png" alt="">'
            f'<script src="http://{PLAIN_HOST}/plain.js"></script>'
            '<div class="thoron-promo">promo</div><div class="thoron-generic-ad">ad</div>')


READ_ROWS = """JSON.stringify(Array.from(document.querySelectorAll('#log-rows tr')).map((tr) =>
  ({kind: tr.className, type: tr.querySelector('td.type').textContent,
    shown: tr.querySelector('td.kind').textContent,
    url: tr.querySelector('td.url').firstChild.textContent})))"""
CHOOSE_TAB = """(() => { const select = document.getElementById('log-tab');
  const option = Array.from(select.options).find((o) => o.textContent.includes(%s));
  if (!option) return false;
  select.value = option.value; select.dispatchEvent(new Event('change')); return true; })()""" % json.dumps(TITLE)
READ_TYPES = ("JSON.stringify(Array.from(document.getElementById('log-type').options)"
              ".map((o) => o.value).filter((v) => v))")
MESSAGE = "document.getElementById('message').textContent"
READ_COLORS = ("JSON.stringify({class: document.body.classList.contains('colorblind'),"
               " allow: getComputedStyle(document.body).getPropertyValue('--allow').trim()})")


def choose_type(value: str) -> str:
    return (f"(() => {{ const s = document.getElementById('log-type'); s.value = {json.dumps(value)};"
            " s.dispatchEvent(new Event('change')); return s.value; })()")


def request(name: str) -> str:
    """A script for the test page: one more request of the plain host, as an image."""
    return f"new Image().src = 'http://{PLAIN_HOST}/{name}.png'; 1"


def filters_problems(message: str) -> list[str]:
    head = "These lines are not filters this blocker can use: "
    if not message.startswith(head):
        return [f"filters: the page says {message!r}"]
    named = message[len(head):]
    out = []
    if f"{BAD_FILTER} (" not in named:
        out.append(f"filters: the line that is no filter is not named: {named!r}")
    if GOOD_FILTER in named.replace(BAD_FILTER, ""):
        out.append(f"filters: a good filter is named as a problem: {named!r}")
    return out


def types_problems(options: list[str], rows: list[dict], script_rows: list[dict]) -> list[str]:
    out = []
    if not any(r["kind"] == "blocked" and f"//{BLOCKED_HOST}/ad.png" in r["url"] for r in rows):
        out.append("types: the image My filters block is not listed as blocked")
    for kind in ("image", "script"):
        if kind not in options:
            out.append(f"types: the type filter does not offer {kind} ({options})")
    if not script_rows or any(r["type"] != "script" for r in script_rows):
        out.append(f"types: 'script' shows {[r['type'] for r in script_rows]}")
    elif not any(f"//{PLAIN_HOST}/plain.js" in r["url"] for r in script_rows):
        out.append("types: 'script' does not show the page's script")
    return out


def hidden_problems(rows: list[dict]) -> list[str]:
    cosmetic = [r for r in rows if r["type"] == "cosmetic"]
    out = []
    if {r["url"] for r in cosmetic} != HIDDEN:
        out.append(f"hidden: the hide rules listed are {sorted(r['url'] for r in cosmetic)}, not {sorted(HIDDEN)}")
    if any(r.get("shown") != "hidden" for r in cosmetic):
        out.append(f"hidden: they are shown as {sorted({r.get('shown') for r in cosmetic})}")
    return out


def _has(rows: list[dict], name: str) -> bool:
    return any(f"//{PLAIN_HOST}/{name}.png" in r["url"] for r in rows)


def pause_problems(paused: list[dict], resumed: list[dict], label: str) -> list[str]:
    out = []
    if label != "Resume":
        out.append(f"pause: the button says {label!r} while paused")
    if _has(paused, "while-paused"):
        out.append("pause: a request made while paused is shown")
    if not _has(resumed, "while-paused"):
        out.append("pause: after 'Resume' the request made while paused is not shown")
    return out


def clear_problems(cleared: list[dict], after: list[dict]) -> list[str]:
    out = []
    if cleared:
        out.append(f"clear: {len(cleared)} requests are still shown")
    if not _has(after, "after-clear"):
        out.append("clear: a request made after 'Clear' is not shown")
    if _has(after, "while-paused"):
        out.append("clear: a request from before 'Clear' is shown again")
    return out


def export_problems(text: str, rows: list[dict]) -> list[str]:
    lines = [line.split("\t") for line in text.splitlines() if line]
    out = []
    if len(lines) != len(rows):
        out.append(f"export: {len(lines)} lines for {len(rows)} requests shown")
    if any(len(fields) != 5 for fields in lines):
        out.append("export: a line is not time, blocked or let through, type, party and address")
    if sorted(fields[-1] for fields in lines) != sorted(r["url"] for r in rows):
        out.append("export: the addresses are not the ones shown")
    return out


def sites_problems(message: str, allowed: list[str], exported: str) -> list[str]:
    out = []
    if message != f"{len(WANTED_SITES)} sites were allowed.":
        out.append(f"sites: the page says {message!r}")
    for pattern in WANTED_SITES:
        if pattern not in allowed:
            out.append(f"sites: {pattern} is not allowed ({allowed})")
        if pattern not in exported.splitlines():
            out.append(f"sites: {pattern} is not in the exported file")
    return out


def rules_problems(box: str, exported: str) -> list[str]:
    out = []
    if IMPORTED_RULES.strip() not in box.splitlines():
        out.append(f"rules: the imported rule is not in the box ({box!r})")
    if exported != box:
        out.append("rules: the exported file is not what the box holds")
    return out


def colorblind_problems(on: bool, seen: dict) -> list[str]:
    if on:
        ok = seen.get("class") is True and seen.get("allow") in COLORBLIND_ALLOW
    else:
        ok = seen.get("class") is False and seen.get("allow") not in COLORBLIND_ALLOW
    return [] if ok else [f"colorblind: with the setting {'on' if on else 'off'} the menu has {seen}"]


def info_problems(text: str) -> list[str]:
    out = []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Thoron 158."):
        out.append(f"info: the first line is {lines[:1]}")
    for part in ("Lists in use:", "My filters: ", f"Allowed sites: {len(WANTED_SITES)},", "Settings changed: ",
                 "colorblind: true", "Last looked for updates: "):
        if part not in text:
            out.append(f"info: no {part!r}")
    # nothing about the pages visited, the sites allowed, or what My filters and My rules say
    for private in (PAGE_HOST, BLOCKED_HOST, PLAIN_HOST, "imported-", "bad-tools"):
        if private in text:
            out.append(f"info: it names {private}")
    return out


class Server:
    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                if name == PAGE_HOST:
                    body, ctype = page_html().encode(), "text/html; charset=utf-8"
                elif self.path.endswith(".js"):
                    body, ctype = b"window.plainScript = 1;", "text/javascript"
                else:
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
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def _wait_message(ws: WebSocket, words: str, seconds: float) -> str:
    deadline = time.monotonic() + seconds
    text = ""
    while time.monotonic() < deadline:
        text = _eval(ws, MESSAGE) or ""
        if words in text:
            break
        time.sleep(0.5)
    return text


def _wait_file(folder: Path, pattern: str, seconds: float = 20) -> str:
    """The text of the file the page saved as `pattern`, once it is complete; "" when none came."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        files = [f for f in folder.glob(pattern) if not f.name.endswith(".crdownload")]
        if files:
            time.sleep(0.5)
            return files[0].read_text(encoding="utf-8")
        time.sleep(0.5)
    return ""


def _pick_file(ws: WebSocket, selector: str, path: Path) -> None:
    ws.call("DOM.enable")
    root = ws.call("DOM.getDocument")["root"]["nodeId"]
    node = ws.call("DOM.querySelector", nodeId=root, selector=selector)["nodeId"]
    ws.call("DOM.setFileInputFiles", files=[str(path)], nodeId=node)


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="tools-", dir=work))
    downloads = Path(tempfile.mkdtemp(prefix="tools-saved-", dir=work))
    picked = Path(tempfile.mkdtemp(prefix="tools-picked-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server() as server:
        proc = _launch(browser, profile, server.port, [PAGE_HOST, BLOCKED_HOST, PLAIN_HOST], native=True)
        port = None
        try:
            port = _devtools_port(profile)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=10) as reply:
                browser_ws = WebSocket(json.loads(reply.read())["webSocketDebuggerUrl"])
            # where saved files go holds only while this connection is open: it stays open for the run
            browser_ws.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads),
                            eventsEnabled=True)
            settings = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            page = WebSocket(_open(port, "about:blank")["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S)

                # filters: the line that is no filter is named after saving
                _eval(settings, "(() => { const box = document.getElementById('my-filters');"
                                f" box.value = {json.dumps(GOOD_FILTER + chr(10) + BAD_FILTER + chr(10) + HIDE_RULES)};"
                                " box.dispatchEvent(new Event('input'));"
                                " document.getElementById('save-filters').click(); return 1; })()")
                message = _wait_message(settings, "not filters", 30)
                report("filters", filters_problems(message), message)
                time.sleep(SETTLE_S)  # the rules are built in

                # types: the page's requests, and only its script
                page.call("Page.navigate", url=f"http://{PAGE_HOST}/page.html")
                time.sleep(SETTLE_S + 2)  # the logger asks every two seconds
                _eval(settings, CHOOSE_TAB)
                rows = json.loads(_eval(settings, READ_ROWS) or "[]")
                options = json.loads(_eval(settings, READ_TYPES) or "[]")
                _eval(settings, choose_type("script"))
                script_rows = json.loads(_eval(settings, READ_ROWS) or "[]")
                _eval(settings, choose_type(""))
                report("types", types_problems(options, rows, script_rows), options)
                report("hidden", hidden_problems(rows), sorted(r["url"] for r in rows if r["type"] == "cosmetic"))

                # pause: what is shown stays as it is until "Resume"
                _eval(settings, "document.getElementById('log-pause').click(); 1")
                label = _eval(settings, "document.getElementById('log-pause').textContent")
                _eval(page, request("while-paused"))
                time.sleep(SETTLE_S + 2)
                paused = json.loads(_eval(settings, READ_ROWS) or "[]")
                _eval(settings, "document.getElementById('log-pause').click(); 1")
                time.sleep(SETTLE_S)
                _eval(settings, CHOOSE_TAB)
                resumed = json.loads(_eval(settings, READ_ROWS) or "[]")
                report("pause", pause_problems(paused, resumed, label), f"{len(paused)} then {len(resumed)} shown")

                # clear: only what comes after it is shown
                _eval(settings, "document.getElementById('log-clear').click(); 1")
                cleared = json.loads(_eval(settings, READ_ROWS) or "[]")
                time.sleep(0.5)
                _eval(page, request("after-clear"))
                time.sleep(SETTLE_S + 2)
                _eval(settings, CHOOSE_TAB)
                after = json.loads(_eval(settings, READ_ROWS) or "[]")
                report("clear", clear_problems(cleared, after), f"{len(cleared)} then {[r['url'] for r in after]}")

                # export: what is shown, one request a line
                _eval(settings, "document.getElementById('log-export').click(); 1")
                text = _wait_file(downloads, "thoron-logger-*.txt")
                report("export", export_problems(text, after), text.strip())

                # sites: import a site, a pattern and an address, then export them
                (picked / "sites.txt").write_text(IMPORTED_SITES, encoding="utf-8")
                _pick_file(settings, "#import-sites-file", picked / "sites.txt")
                message = _wait_message(settings, "sites were allowed", 30)
                allowed = _eval(settings, "(async () => (await (await import('chrome://resources/js/cr.js'))"
                                          ".sendWithPromise('getSites')).allowed)()") or []
                _eval(settings, "document.getElementById('export-sites').click(); 1")
                exported = _wait_file(downloads, "allowed-sites-*.txt")
                report("sites", sites_problems(message, allowed, exported), allowed)

                # rules: import and append, then export the box
                (picked / "rules.txt").write_text(IMPORTED_RULES, encoding="utf-8")
                _pick_file(settings, "#import-rules-file", picked / "rules.txt")
                _wait_message(settings, "added below your rules", 30)
                box = _eval(settings, "document.getElementById('my-rules').value") or ""
                _eval(settings, "document.getElementById('export-rules').click(); 1")
                exported = _wait_file(downloads, "my-rules-*.txt")
                report("rules", rules_problems(box, exported), box.strip())

                # colorblind: the menu's colours follow the setting (on, off, then on again for the
                # troubleshooting info, which names the settings changed)
                for on in (True, False, True):
                    _eval(settings, "document.querySelector('[data-setting=\"colorblind\"]').click(); 1")
                    time.sleep(1)
                    menu = WebSocket(_open(port, MENU_URL)["webSocketDebuggerUrl"])
                    try:
                        time.sleep(SETTLE_S)
                        seen = json.loads(_eval(menu, READ_COLORS) or "{}")
                    finally:
                        menu.close()
                    report("colorblind", colorblind_problems(on, seen), seen)

                # info: what was copied, read where the page puts it
                _eval(settings, "navigator.clipboard.writeText = async (text) => { window.copiedInfo = text; }; 1")
                _eval(settings, "document.getElementById('copy-info').click(); 1")
                _wait_message(settings, "troubleshooting info was", 30)
                text = _eval(settings, "window.copiedInfo || ''") or ""
                report("info", info_problems(text), text.strip())
            finally:
                settings.close()
                page.close()
                browser_ws.close()
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            for folder in (profile, downloads, picked):
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
    print("TOOLS CHECK: PASSED" if not problems else f"TOOLS CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
