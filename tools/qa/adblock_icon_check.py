#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the address bar's icon for blocked ads opens the blocker's own menu, checked end to end and
offline (ROADMAP P5.52). Windows only.

When the blocker stops something on a page, an icon shows in the address bar ("Ads and trackers blocked"). As
uBlock Origin's icon does, a click on it opens the blocker's menu (chrome://adblock-menu.top-chrome), the same
as the shield in the toolbar, not Chromium's small notice. The address bar is part of the window, which a
headless browser does not draw, so this check runs the browser with a window, placed off the screen, and
clicks the icon with Windows UI Automation. A local server serves a test page with an image from an ad host
EasyList blocks (host-resolver rules; every other name fails, so nothing leaves the PC). Steps:

    icon   after the page loads, the icon is in the address bar
    menu   a click on it opens the blocker's menu

    py -3 -I tools/qa/adblock_icon_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 when every step passes (or the check does not apply, on another system).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_earlyhints_check import ad_host  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.adblock_trust_check import Server  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "icon-check.test"
ICON = "Ads and trackers blocked"
MENU_URL = "chrome://adblock-menu.top-chrome/"
SETTLE_S = 3.0
# Finds the icon among the elements of the test browser (its process id in THORON_PID; no other program's
# windows are looked at), says whether it is there, and clicks it when asked.
UIA = """
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$mine = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$env:THORON_PID)
$icon = $null
for ($i = 0; $i -lt 24 -and -not $icon; $i++) {
  $icon = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $mine) |
      Where-Object { $_.Current.Name.StartsWith('%s') } | Select-Object -First 1
  if (-not $icon) { Start-Sleep -Milliseconds 250 }
}
if (-not $icon) { 'no icon'; exit 1 }
if ($env:THORON_CLICK -ne '1') { 'icon'; exit 0 }
$pattern = $null
if ($icon.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
  $pattern.Invoke()
} else {
  $legacy = $icon.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
  $legacy.DoDefaultAction()
}
'clicked'
""" % ICON


def ad_image(host: str) -> str:
    """What the page runs: an image from the ad host, which the blocker stops."""
    return (f"(() => {{ const i = new Image(); i.src = 'http://{host}/ad.png?' + Date.now(); "
            "document.body.append(i); return 1; })()")


def menu_problems(icon: str, clicked: str, targets: list[str]) -> list[str]:
    out = []
    if icon != "icon":
        out.append(f"icon: the address bar has no {ICON!r} icon ({icon!r})")
    elif clicked != "clicked":
        out.append(f"menu: the icon could not be clicked ({clicked!r})")
    elif not any(url.startswith(MENU_URL) for url in targets):
        out.append(f"menu: a click on the icon did not open the blocker's menu (open: {targets})")
    return out


def _launch_window(browser: Path, profile: Path, port: int, host: str) -> subprocess.Popen:
    args = [str(browser), f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
            "--disable-default-apps", "--disable-background-networking", "--disable-component-update",
            f"--disable-features={NO_HTTPS_FIRST}", "--enable-features=ThoronNativeAdblock",
            f"--host-resolver-rules=MAP {PAGE_HOST} 127.0.0.1:{port}, MAP {host} 127.0.0.1:{port}, "
            "MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            # off the screen: the check needs a real window, not the person's attention
            "--window-position=-4000,-4000", "--window-size=1000,700",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(browser: Path, work: Path, host: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="icon-", dir=work))
    problems: list[str] = []
    with Server() as server:
        proc = _launch_window(browser, profile, server.port, host)
        port = None
        try:
            port = _devtools_port(profile)
            target = _open(port, f"http://{PAGE_HOST}/page.html")
            time.sleep(SETTLE_S)

            def uia(click: bool) -> str:
                return subprocess.run(["powershell.exe", "-NoProfile", "-Command", UIA], capture_output=True,
                                      text=True, encoding="utf-8", errors="replace", timeout=60,
                                      env=dict(os.environ, THORON_PID=str(proc.pid),
                                               THORON_CLICK="1" if click else "0")).stdout.strip()

            # the ad image: the page asks for it, the blocker stops it, the icon shows
            ws = WebSocket(target["webSocketDebuggerUrl"])
            try:
                ws.call("Runtime.evaluate", expression=ad_image(host))
            finally:
                ws.close()
            time.sleep(SETTLE_S)
            icon = uia(click=False)
            clicked = uia(click=True) if icon == "icon" else ""
            time.sleep(2)
            targets = [t.get("url", "") for t in json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10).read())]
            found = menu_problems(icon, clicked, targets)
            print(f"{'PASS' if not found else 'FAIL'}  icon and menu: {icon!r}, {clicked!r}, "
                  f"menu open: {any(u.startswith(MENU_URL) for u in targets)}")
            problems += found
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
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    if os.name != "nt":
        print("ICON CHECK: does not apply (Windows only)")
        return 0
    host = ad_host((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if not host:
        print("ICON CHECK: FAILED (EasyList holds no plain host rule)")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, host)
    for problem in problems:
        print(problem)
    print("ICON CHECK: PASSED" if not problems else f"ICON CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
