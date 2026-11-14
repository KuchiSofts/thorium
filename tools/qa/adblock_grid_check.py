#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the menu's grid of rules (uBlock Origin's dynamic filtering pane), checked end to end and
offline (ROADMAP P5.45).

The menu (chrome://adblock-menu.top-chrome), opened as a tab, works on the active tab before it, as the menu
check drives it. A local server serves a test page under a name of its own (host-resolver rules; every other
name fails, so nothing leaves the PC): an image from an ad host EasyList blocks and a script from a plain host
of another site. Steps:

    rows      the grid has the seven type rows and a row for the page's host, the other host and the ad host,
              with what each was asked and blocked
    block     "Block" for the other host on this site: in force at once (after a reload its script is not
              asked for) but only for now: the grid says "not saved" and My rules on disk do not have it
    save      Save (uBlock Origin's padlock): My rules on disk have `<page> <other host> * block`
    allow     "Allow" for the ad host on this site: after a reload the ad image is asked for (the rule beats
              EasyList), not saved
    revert    Revert (the eraser): the allow is gone, the ad image is blocked again, the saved block stays
    inherit   "Block" for the other host on every site, and the saved rule for this site taken out: the
              cell for this site shows the block light (from the broader rule); Revert, Save: My rules
              on disk have no rule for the other host, and its script is asked for again
    for-now   (P5.63) a block not saved shows on chrome://adblock under "Changed in the menu for now";
              "Save them" saves it, and the section goes

    py -3 -I tools/qa/adblock_grid_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_earlyhints_check import ad_host  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "grid-check.test"
OTHER_HOST = "other-grid.test"
MENU_URL = "chrome://adblock-menu.top-chrome/"
SETTLE_S = 3.0
TYPE_ROWS = 7


def page_html(host: str) -> str:
    return ("<!doctype html><title>Thoron grid check</title>"
            f'<img src="http://{host}/ad.png" alt="">'
            f'<script src="http://{OTHER_HOST}/lib.js"></script>')


def saved_rule(source: str, destination: str, action: str) -> str:
    return f"{source} {destination} * {action}"


READ_GRID = """JSON.stringify({open: document.getElementById('grid-box').open,
  hidden: document.getElementById('grid-box').hidden,
  changed: !document.getElementById('grid-changed').hidden,
  rows: Array.from(document.querySelectorAll('#grid .grid-row')).map((row) => {
    const cell = (i) => { const b = row.querySelectorAll('.cell')[i].querySelector('.set, .inherited');
                          return b ? b.className : ''; };
    return {name: row.querySelector('.name').textContent, n: row.querySelector('.n').textContent,
            type: row.classList.contains('type'), global: cell(0), local: cell(1)};
  })})"""


def row_of(grid: dict, name: str) -> dict | None:
    return next((r for r in grid.get("rows", []) if r["name"] == name and not r["type"]), None)


def rows_problems(grid: dict, host: str) -> list[str]:
    out = []
    if grid.get("hidden"):
        return ["rows: the grid is not shown"]
    types = [r for r in grid.get("rows", []) if r["type"]]
    if len(types) != TYPE_ROWS:
        out.append(f"rows: {len(types)} type rows, not {TYPE_ROWS}")
    hosts = [r["name"] for r in grid.get("rows", []) if not r["type"]]
    if not hosts or hosts[0] != PAGE_HOST:
        out.append(f"rows: the page's own host is not the first ({hosts[:3]})")
    other, ad = row_of(grid, OTHER_HOST), row_of(grid, host)
    if not other or not other["n"]:
        out.append(f"rows: no row with requests for the other host ({other})")
    if not ad or "/" not in ad["n"]:
        out.append(f"rows: the ad host's row does not show it blocked ({ad})")
    if grid.get("changed"):
        out.append("rows: the grid says something is not saved before anything was changed")
    return out


def for_now_problems(before: dict, saved: str, after: dict) -> list[str]:
    want = f"+ {saved_rule(PAGE_HOST, OTHER_HOST, 'block')}"
    out = []
    if not before.get("shown") or want not in before.get("lines", "").splitlines():
        out.append(f"for-now: the settings page shows {before}, not {want!r}")
    if saved_rule(PAGE_HOST, OTHER_HOST, "block") not in saved.splitlines():
        out.append(f"for-now: after 'Save them' My rules on disk are {saved!r}")
    if after.get("shown"):
        out.append("for-now: the section is still there after 'Save them'")
    return out


READ_FOR_NOW = ("JSON.stringify({shown: !document.getElementById('for-now').hidden,"
                " lines: document.getElementById('for-now-lines').textContent})")


def step_problems(step: str, seen: dict, host: str) -> list[str]:
    """`seen`: other, ad (asked for after a reload), changed, saved (My rules on disk), local and global (the
    class of the marked button of the other host's cells; for allow and revert, the ad host's)."""
    block = saved_rule(PAGE_HOST, OTHER_HOST, "block")
    allow = saved_rule(PAGE_HOST, host, "allow")
    want = {
        "block": {"other": False, "ad": False, "changed": True, "saved_has": [], "saved_not": [block],
                  "local": "block set"},
        "save": {"changed": False, "saved_has": [block], "saved_not": [], "local": "block set"},
        "allow": {"ad": True, "other": False, "changed": True, "saved_has": [block], "saved_not": [allow],
                  "local": "allow set"},
        "revert": {"ad": False, "other": False, "changed": False, "saved_has": [block], "saved_not": [allow],
                   "local": ""},
        "inherit": {"local": "block inherited", "global": "block set", "changed": True},
        "cleared": {"other": True, "changed": False, "saved_has": [], "saved_not": [OTHER_HOST], "local": ""},
    }[step]
    out = []
    for key in ("other", "ad", "changed"):
        if key in want and seen.get(key) != want[key]:
            out.append(f"{step}: {key} is {seen.get(key)!r}, not {want[key]!r}")
    for key in ("local", "global"):
        if key in want and seen.get(key) != want[key]:
            out.append(f"{step}: the {key} cell shows {seen.get(key)!r}, not {want[key]!r}")
    saved = seen.get("saved", "")
    for line in want.get("saved_has", []):
        if line not in saved:
            out.append(f"{step}: My rules on disk do not have {line!r}")
    for text in want.get("saved_not", []):
        if text in saved:
            out.append(f"{step}: My rules on disk have {text!r}")
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


class Run:
    def __init__(self, browser: Path, work: Path, server: Server, host: str):
        self.server, self.host = server, host
        self.profile = Path(tempfile.mkdtemp(prefix="grid-", dir=work))
        self.proc = _launch(browser, self.profile, server.port, [PAGE_HOST, OTHER_HOST, host], native=True)
        self.port = None
        self.menu = self.page = None
        self.port = _devtools_port(self.profile)
        _open(self.port, f"http://127.0.0.1:{server.port}/warm.html")
        time.sleep(4)
        page = _open(self.port, f"http://{PAGE_HOST}/page.html")
        self.page = WebSocket(page["webSocketDebuggerUrl"])
        time.sleep(SETTLE_S)
        self.menu = WebSocket(_open(self.port, MENU_URL)["webSocketDebuggerUrl"])
        time.sleep(2)
        # the menu works on the active tab, as from the toolbar
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/activate/{page['id']}", timeout=10).read()
        time.sleep(1)
        _eval(self.menu, "document.getElementById('grid-box').open = true; 1")

    def grid(self) -> dict:
        return json.loads(_eval(self.menu, READ_GRID) or "{}")

    def click(self, selector: str) -> bool:
        return bool(_eval(self.menu, f"(() => {{ const b = document.querySelector({json.dumps(selector)});"
                                     " if (!b || b.disabled) return false; b.click(); return true; })()"))

    def cell(self, destination: str, kind: str, scope: str, action: int) -> bool:
        return self.click(f'.cell button[data-key="{destination} {kind} {scope} {action}"]')

    def saved(self) -> str:
        try:
            return (self.profile / "Thoron Adblock" / "my-rules.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def reload_and_see(self, row: str) -> dict:
        self.server.asked.clear()
        self.click("#grid-reload")
        time.sleep(SETTLE_S + 1)
        return self.see(row)

    def see(self, row: str) -> dict:
        time.sleep(1.5)
        grid = self.grid()
        cells = row_of(grid, row) or {}
        return {"other": (OTHER_HOST, "/lib.js") in self.server.asked,
                "ad": any(name == self.host for name, _ in self.server.asked),
                "changed": grid.get("changed"), "saved": self.saved(),
                "local": cells.get("local", ""), "global": cells.get("global", "")}

    def close(self) -> None:
        for ws in (self.menu, self.page):
            try:
                if ws:
                    ws.close()
            except OSError:
                pass
        if self.port is not None:
            _close_browser(self.port, self.proc)
        else:
            bench._stop(self.proc, self.profile)
        shutil.rmtree(self.profile, ignore_errors=True)


def run(browser: Path, work: Path, host: str) -> list[str]:
    problems: list[str] = []
    with Server(host) as server:
        r = None
        try:
            r = Run(browser, work, server, host)
            grid = r.grid()
            found = rows_problems(grid, host)
            print(f"{'PASS' if not found else 'FAIL'}  rows: "
                  f"{[(x['name'], x['n']) for x in grid.get('rows', []) if not x['type']]}")
            problems += found

            def step(name: str, clicks: list, row: str, reload: bool) -> None:
                missing = []
                for c in clicks:
                    if not c():
                        missing.append(c)
                    # the menu shows the new state before the next click (a click acts on what is shown)
                    time.sleep(1.5)
                seen = r.reload_and_see(row) if reload else r.see(row)
                found = step_problems(name, seen, host)
                if missing:
                    found.append(f"{name}: {len(missing)} button(s) not found or not enabled")
                shown = {k: v for k, v in seen.items() if k != "saved"}
                print(f"{'PASS' if not found else 'FAIL'}  {name}: {shown}")
                problems.extend(found)

            step("block", [lambda: r.cell(OTHER_HOST, "*", "local", 1)], OTHER_HOST, reload=True)
            step("save", [lambda: r.click("#grid-save")], OTHER_HOST, reload=False)
            step("allow", [lambda: r.cell(host, "*", "local", 2)], host, reload=True)
            step("revert", [lambda: r.click("#grid-revert")], host, reload=True)
            step("inherit", [lambda: r.cell(OTHER_HOST, "*", "global", 1),
                             lambda: r.cell(OTHER_HOST, "*", "local", 1)], OTHER_HOST, reload=False)
            step("cleared", [lambda: r.click("#grid-revert"), lambda: r.cell(OTHER_HOST, "*", "local", 1),
                             lambda: r.click("#grid-save")], OTHER_HOST, reload=True)

            # a block for now, seen and saved from the settings page
            r.cell(OTHER_HOST, "*", "local", 1)
            time.sleep(1.5)
            settings = WebSocket(_open(r.port, "chrome://adblock/#rules")["webSocketDebuggerUrl"])
            try:
                time.sleep(3)
                before = json.loads(_eval(settings, READ_FOR_NOW) or "{}")
                _eval(settings, "document.getElementById('save-for-now').click(); 1")
                time.sleep(2)
                after = json.loads(_eval(settings, READ_FOR_NOW) or "{}")
            finally:
                settings.close()
            found = for_now_problems(before, r.saved(), after)
            print(f"{'PASS' if not found else 'FAIL'}  for-now: {before} then {after}")
            problems += found
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
    host = ad_host((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if not host:
        print("GRID CHECK: FAILED (EasyList holds no plain host rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, host)
    for problem in problems:
        print(problem)
    print("GRID CHECK: PASSED" if not problems else f"GRID CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
