#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, uBlock Origin's theme choice for its pages, checked end to end and offline (ROADMAP P5.59).

"Theme" on chrome://adblock: as the system, light or dark. The settings page and the menu are served with the
choice, so they open in its colours; "as the system" follows the system's light or dark. The system's choice is
emulated (DevTools), nothing leaves the PC. Steps:

    auto      as the system: the pages are light with a light system and dark with a dark one
    dark      "Dark" with a light system: both pages are dark, also when opened again
    light     "Light" with a dark system: both pages are light
    kept      the choice is in the settings after the browser starts again

    py -3 -I tools/qa/adblock_theme_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGES = {"settings": "chrome://adblock/", "menu": "chrome://adblock-menu.top-chrome/"}
LIGHT, DARK = "#7235da", "#b097fa"  # the pages' accent colour in each
SETTLE_S = 2.5
READ = ("JSON.stringify({theme: document.documentElement.getAttribute('data-theme') || '',"
        " accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()})")


def colour_problems(step: str, page: str, seen: dict, want: str, theme: str) -> list[str]:
    out = []
    if seen.get("accent") != want:
        out.append(f"{step}: the {page} is {'dark' if seen.get('accent') == DARK else 'light'}, "
                   f"not {'dark' if want == DARK else 'light'} ({seen})")
    if seen.get("theme") != theme:
        out.append(f"{step}: the {page} was served with the theme {seen.get('theme')!r}, not {theme!r}")
    return out


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def look(port: int, page: str, system: str) -> dict:
    """The page as it opens, with the system's `system` ("light" or "dark") emulated."""
    ws = WebSocket(_open(port, "about:blank")["webSocketDebuggerUrl"])
    try:
        ws.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": system}])
        ws.call("Page.navigate", url=PAGES[page])
        time.sleep(SETTLE_S)
        return json.loads(_eval(ws, READ) or "{}")
    finally:
        ws.close()


def choose(port: int, theme: str) -> str:
    ws = WebSocket(_open(port, PAGES["settings"])["webSocketDebuggerUrl"])
    try:
        time.sleep(SETTLE_S)
        _eval(ws, "(() => { const s = document.getElementById('theme');"
                  f" s.value = {json.dumps(theme)}; s.dispatchEvent(new Event('change')); return 1; }})()")
        time.sleep(1.5)
        return _eval(ws, "document.getElementById('message').textContent") or ""
    finally:
        ws.close()


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="theme-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    proc = None
    port = None
    try:
        for start in (1, 2):
            # the port file of the run before names a port that is closed now
            (profile / "DevToolsActivePort").unlink(missing_ok=True)
            proc = _launch(browser, profile, 9, ["theme-check.test"], native=True)
            port = _devtools_port(profile)
            time.sleep(SETTLE_S)
            if start == 2:
                seen = {page: look(port, page, "light") for page in PAGES}
                found = []
                for page in PAGES:
                    found += colour_problems("kept", page, seen[page], DARK, "dark")
                report("kept", found, seen)
                break
            found, seen = [], {}
            for system, want in (("light", LIGHT), ("dark", DARK)):
                for page in PAGES:
                    seen[f"{page}/{system}"] = look(port, page, system)
                    found += colour_problems("auto", page, seen[f"{page}/{system}"], want, "")
            report("auto", found, seen)

            for step, theme, system, want in (("light", "light", "dark", LIGHT), ("dark", "dark", "light", DARK)):
                message = choose(port, theme)
                found = [] if message == "The theme was changed." else [f"{step}: the page says {message!r}"]
                seen = {page: look(port, page, system) for page in PAGES}
                for page in PAGES:
                    found += colour_problems(step, page, seen[page], want, theme)
                report(step, found, seen)
            _close_browser(port, proc)
            port = None
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
        problems.append(f"the run failed: {e}")
    finally:
        if port is not None:
            _close_browser(port, proc)
        elif proc is not None and proc.poll() is None:
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
    print("THEME CHECK: PASSED" if not problems else f"THEME CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
