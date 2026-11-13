#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, opening a page strict blocking stopped, as uBlock Origin's "Proceed", checked end to end
and offline (ROADMAP P5.49).

The choice is in the menu of the shield (chrome://adblock-menu.top-chrome, here opened as a tab, which works on
the active tab), not on the blocked page: a web page cannot press it. A local server answers for every name
used (host-resolver rules; every other name fails, so nothing leaves the PC). The hosts come from uBlock
Origin's badware list in the bundled lists: its first `$doc` rule and its first `$all` rule. Steps:

    blocked  the `$doc` host's page is blocked; the menu offers to open it
    now      "Open it now": the page opens, the menu no longer offers it, and no switch was saved
    other    the `$all` host's page is still blocked (only that site was opened)
    always   "Always on this site" on it: the page opens and the switch "no-strict" is saved for its host

    py -3 -I tools/qa/adblock_proceed_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_strict_check import PLAIN_HOST, Server, page_hosts  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MENU_URL = "chrome://adblock-menu.top-chrome/"
BLOCKED_TITLE = "Thoron blocked this page"
SETTLE_S = 3.0


def step_problems(step: str, title: str, offered, switches: dict, host: str) -> list[str]:
    want_open = step in ("now", "always")
    out = []
    if (title == BLOCKED_TITLE) == want_open:
        out.append(f"{step}: the page is {'blocked' if title == BLOCKED_TITLE else 'open'} ({title!r})")
    if offered is not (not want_open):
        out.append(f"{step}: the menu {'offers' if offered else 'does not offer'} to open it")
    saved = "no-strict" in switches.get(host, [])
    if saved != (step == "always"):
        out.append(f"{step}: the switch no-strict is {'saved' if saved else 'not saved'} for {host}")
    return out


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def run(browser: Path, work: Path, hosts: dict[str, str]) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix="proceed-", dir=work))
    problems: list[str] = []
    server_hosts = {"host": hosts["doc"], **hosts}
    with Server(server_hosts) as server:
        proc = _launch(browser, profile, server.port, [*hosts.values(), PLAIN_HOST], native=True)
        port = None
        page = menu = None
        try:
            port = _devtools_port(profile)
            time.sleep(3)
            target = _open(port, "about:blank")
            page = WebSocket(target["webSocketDebuggerUrl"])
            menu = WebSocket(_open(port, MENU_URL)["webSocketDebuggerUrl"])

            def show(url: str | None) -> None:
                if url:
                    page.call("Page.navigate", url=url)
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{target['id']}", timeout=10).read()
                time.sleep(SETTLE_S)

            def switches() -> dict:
                try:
                    data = json.loads((profile / "Thoron Adblock" / "site-switches.json").read_text("utf-8"))
                except (OSError, ValueError):
                    return {}
                return data if isinstance(data, dict) else {}

            def look(step: str, host: str) -> None:
                title = _eval(page, "document.title") or ""
                offered = _eval(menu, "!document.getElementById('blocked-box').hidden")
                found = step_problems(step, title, offered, switches(), host)
                print(f"{'PASS' if not found else 'FAIL'}  {step}: {host}: {title!r}, offered {offered}")
                problems.extend(found)

            show(f"http://{hosts['doc']}/page")
            look("blocked", hosts["doc"])
            _eval(menu, "document.getElementById('open-once').click(); 1")
            show(None)
            look("now", hosts["doc"])
            show(f"http://{hosts['all']}/page")
            look("other", hosts["all"])
            _eval(menu, "document.getElementById('open-always').click(); 1")
            show(None)
            time.sleep(1)
            look("always", hosts["all"])
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed: {e}")
        finally:
            for ws in (page, menu):
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
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    hosts = page_hosts((a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8"))
    if "doc" not in hosts or "all" not in hosts:
        print(f"PROCEED CHECK: FAILED (the badware list has no $doc or no $all rule for a host: {hosts})")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work, hosts)
    for problem in problems:
        print(problem)
    print("PROCEED CHECK: PASSED" if not problems else f"PROCEED CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
