#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, "Block element..." in the page's context menu, checked end to end and offline (ROADMAP
P5.41). Windows only.

A context menu is a window of its own, which a headless browser never shows, so this check runs the browser
with a window, placed off the screen. It right-clicks an element of a local test page (host-resolver rules;
every other name fails, so nothing leaves the PC), chooses "Block element..." in the menu with Windows UI
Automation, and checks that the picker opened on that very element: Enter puts a rule for it in My filters,
and after a reload the element is hidden. Then, with "Make use of the context menu" off on chrome://adblock
(P5.46), a right-click opens the menu without the item.

    py -3 -I tools/qa/adblock_context_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 when the step passes (or the check does not apply, on another system).
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
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "context-check.test"
ITEM = "Block element"  # the string ends in "...", which Chromium's menus show as one character
SETTLE_S = 2.5
PAGE = """<!doctype html><title>Thoron context menu check</title>
<p>text</p><div id="promo-box" class="promo" style="width:240px;height:90px;background:#c33;color:#fff">a promo</div>
<p id="keep">this stays</p>"""
# Finds the menu item by the start of its name among the menu items of the test browser (its process id in
# THORON_PID; no other program's windows are looked at) and chooses it.
INVOKE = """
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$mine = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$env:THORON_PID)
$items = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuItem)
$cond = New-Object System.Windows.Automation.AndCondition($mine, $items)
$item = $null
for ($i = 0; $i -lt 24 -and -not $item; $i++) {
  $item = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond) |
      Where-Object { $_.Current.Name.StartsWith('%s') } | Select-Object -First 1
  if (-not $item) { Start-Sleep -Milliseconds 250 }
}
if (-not $item) { 'no item'; exit 1 }
$item.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
'chosen'
""" % ITEM
# The names of the menu items of the test browser once a menu is open (waits a few seconds for one).
LIST = """
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$mine = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$env:THORON_PID)
$items = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuItem)
$cond = New-Object System.Windows.Automation.AndCondition($mine, $items)
$names = @()
for ($i = 0; $i -lt 24 -and $names.Count -eq 0; $i++) {
  $names = @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond) | ForEach-Object { $_.Current.Name })
  if ($names.Count -eq 0) { Start-Sleep -Milliseconds 250 }
}
$names -join "`n"
"""


def off_problems(names: list[str]) -> list[str]:
    """With "Make use of the context menu" off: the menu opens, without the item."""
    if not names:
        return ["off: the context menu did not open"]
    if any(name.startswith(ITEM) for name in names):
        return [f"off: {ITEM!r} is still in the menu with its setting off"]
    return []


def rule_problems(my_filters: str, hidden: str | None) -> list[str]:
    out = []
    lines = [line for line in my_filters.splitlines() if line.strip()]
    if not any(line.startswith(f"{PAGE_HOST}##") and ("promo" in line) for line in lines):
        out.append(f"no rule for the clicked element in My filters ({my_filters.strip()!r})")
    if hidden != "hidden":
        out.append(f"the clicked element is {hidden} after a reload")
    return out


class Server:
    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                body = (WARM_HTML if self.path == "/warm.html" else PAGE).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
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


def _launch_window(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    args = [str(browser), f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
            "--disable-default-apps", "--disable-background-networking", "--disable-component-update",
            f"--disable-features={NO_HTTPS_FIRST}", "--enable-features=ThoronNativeAdblock",
            f"--host-resolver-rules=MAP {PAGE_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            # off the screen: the check needs a real window, not the person's attention
            "--window-position=-4000,-4000", "--window-size=900,700",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _eval(ws: WebSocket, expression: str):
    return ws.call("Runtime.evaluate", expression=expression, returnByValue=True).get("result", {}).get("value")


def run(browser: Path, work: Path) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="context-", dir=work))
    problems: list[str] = []
    with Server() as server:
        proc = _launch_window(browser, profile, server.port)
        port = None
        try:
            port = _devtools_port(profile)
            _open(port, f"http://127.0.0.1:{server.port}/warm.html")
            time.sleep(3)
            page_target = _open(port, f"http://{PAGE_HOST}/page.html")
            page = WebSocket(page_target["webSocketDebuggerUrl"])

            def right_click(element_id: str) -> None:
                box = json.loads(_eval(page, f"JSON.stringify(document.getElementById({json.dumps(element_id)})"
                                             ".getBoundingClientRect())"))
                x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                    page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="right", clickCount=1)
                    time.sleep(0.2)

            def uia(script: str) -> str:
                return subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], capture_output=True,
                                      text=True, encoding="utf-8", errors="replace", timeout=60,
                                      env=dict(os.environ, THORON_PID=str(proc.pid))).stdout.strip()

            try:
                time.sleep(SETTLE_S)
                right_click("promo-box")
                chosen = uia(INVOKE)
                if chosen != "chosen":
                    problems.append(f"the menu item {ITEM!r} was not found ({chosen!r})")
                else:
                    time.sleep(1.5)
                    for kind in ("keyDown", "keyUp"):
                        page.call("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter",
                                  windowsVirtualKeyCode=13, text="\r" if kind == "keyDown" else "")
                    time.sleep(2)
                    page.call("Page.reload")
                    time.sleep(SETTLE_S)
                    hidden = _eval(page, "(() => { const e = document.getElementById('promo-box'); return !e ? "
                                         "'gone' : getComputedStyle(e).display === 'none' ? 'hidden' : 'shown'; })()")
                    try:
                        mine = (profile / "Thoron Adblock" / "my-filters.txt").read_text(encoding="utf-8")
                    except OSError:
                        mine = ""
                    problems += rule_problems(mine, hidden)
                    print(f"{'PASS' if not problems else 'FAIL'}  context menu: My filters {mine.strip()!r}, "
                          f"element {hidden}")
                # "Make use of the context menu" off on chrome://adblock: the item is gone
                settings = WebSocket(_open(port, "chrome://adblock/")["webSocketDebuggerUrl"])
                try:
                    time.sleep(1.5)
                    _eval(settings, "document.querySelector('[data-setting=\"context-menu\"]').click(); 1")
                    time.sleep(1)
                    off = _eval(settings, "document.querySelector('[data-setting=\"context-menu\"]').checked")
                finally:
                    settings.close()
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{page_target['id']}",
                                       timeout=10).read()
                time.sleep(1)
                right_click("keep")
                names = [n for n in uia(LIST).splitlines() if n.strip()]
                found = off_problems(names) + (["off: the setting did not turn off"] if off is not False else [])
                print(f"{'PASS' if not found else 'FAIL'}  off: {len(names)} menu items, none {ITEM!r}"
                      if not found else f"FAIL  off: {names}")
                problems += found
            finally:
                page.close()
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
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
    if sys.platform != "win32":
        print("CONTEXT CHECK: not on Windows, nothing to check")
        return 0
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work)
    for problem in problems:
        print(problem)
    print("CONTEXT CHECK: PASSED" if not problems else f"CONTEXT CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
