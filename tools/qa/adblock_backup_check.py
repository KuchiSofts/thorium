#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, back up to a file, reset and restore from the file, checked end to end and offline
(ROADMAP P5.40).

As uBlock Origin's Settings do: "Back up to file" saves the lists, the person's own rules, the allowed sites,
the menu's switches and the settings; "Reset to default settings" takes all of them back to the defaults;
"Restore from file" makes them as the file has them. Nothing is downloaded from the network: the check
changes no added lists. Steps:

    change   a few settings on, own rules, an allowed site, switches for a host, a built-in list off
    backup   the file is saved and holds every one of those
    reset    after "Reset to default settings" (confirmed), each is back to its default
    restore  after "Restore from file" with that file, each is as it was changed again

    py -3 -I tools/qa/adblock_backup_check.py --browser <out>\\thoron.exe --work <scratch dir>
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
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

SETTINGS_URL = "chrome://adblock/"
MINE = "||mine-backup.test^\n"
ALLOWED = "allowed-backup.test"
SWITCH_HOST = "switch-backup.test"
SWITCHES = ["-fonts", "popups"]
LIST_OFF = "easyprivacy"
TURNED_ON = ("block-csp-reports", "default-fonts")
# the settings that are on unless changed (P5.46: auto-update, the context menu, the menu's grid), and the
# largest media size unless changed
DEFAULT_ON = ("badge", "auto-update", "context-menu", "advanced")
DEFAULT_MEDIA_KB = 50

CHANGE = f"""(async () => {{
  const {{sendWithPromise}} = await import('chrome://resources/js/cr.js');
  for (const name of {json.dumps(list(TURNED_ON))}) await sendWithPromise('setSetting', name, true);
  await sendWithPromise('setMyFilters', {json.dumps(MINE)});
  await sendWithPromise('allowSite', {json.dumps(ALLOWED)});
  await sendWithPromise('setHostSwitches', {json.dumps(SWITCH_HOST)}, {json.dumps(SWITCHES)});
  await sendWithPromise('setListEnabled', {json.dumps(LIST_OFF)}, false);
  return 'changed';
}})()"""
READ = """(async () => {
  const {sendWithPromise} = await import('chrome://resources/js/cr.js');
  const [state, sites, settings] = await Promise.all(
      [sendWithPromise('getState'), sendWithPromise('getSites'), sendWithPromise('getSettings')]);
  return JSON.stringify({
    disabled: state.lists.filter((l) => l.builtin && !l.enabled).map((l) => l.id),
    myFilters: state.myFilters, allowed: sites.allowed,
    switches: Object.fromEntries(sites.switches.map((s) => [s.host, s.names])), settings});
})()"""


def changed_problems(step: str, got: dict) -> list[str]:
    """What differs from the changed state (`got` as READ gives it, or as the backup file holds it)."""
    out = []
    settings = got.get("settings", {})
    for name in TURNED_ON:
        if settings.get(name) is not True:
            out.append(f"{step}: the setting {name} is not on")
    if settings.get("badge") is not True:
        out.append(f"{step}: the badge setting is not on")
    if got.get("myFilters") != MINE:
        out.append(f"{step}: own rules are {got.get('myFilters')!r}")
    if not any(ALLOWED in pattern for pattern in got.get("allowed", [])):
        out.append(f"{step}: {ALLOWED} is not allowed")
    if sorted(got.get("switches", {}).get(SWITCH_HOST, [])) != sorted(SWITCHES):
        out.append(f"{step}: the switches of {SWITCH_HOST} are {got.get('switches', {}).get(SWITCH_HOST)}")
    if LIST_OFF not in got.get("disabled", []):
        out.append(f"{step}: the list {LIST_OFF} is not off")
    return out


def default_problems(got: dict) -> list[str]:
    out = []
    settings = got.get("settings", {})
    for name, on in settings.items():
        if name in ("shortcuts", "version"):
            # keyboard shortcuts are not settings a reset takes back (in uBlock Origin, the browser's); the
            # browser's version (P5.54, for the troubleshooting info) is no setting
            continue
        if name == "media-kb":
            if on != DEFAULT_MEDIA_KB:
                out.append(f"reset: the largest media size is {on} kB, not {DEFAULT_MEDIA_KB}")
        elif name == "theme":
            if on != "auto":  # P5.59: as the system unless chosen
                out.append(f"reset: the theme is {on!r}, not 'auto'")
        elif on != (name in DEFAULT_ON):
            out.append(f"reset: the setting {name} is {'on' if on else 'off'}")
    if got.get("myFilters"):
        out.append(f"reset: own rules are left: {got.get('myFilters')!r}")
    if got.get("allowed"):
        out.append(f"reset: sites are still allowed: {got.get('allowed')}")
    if got.get("switches"):
        out.append(f"reset: switches are left: {got.get('switches')}")
    if got.get("disabled"):
        out.append(f"reset: lists are still off: {got.get('disabled')}")
    return out


def backup_as_read(backup: dict) -> dict:
    """The backup file in the shape READ gives."""
    return {"disabled": backup.get("lists", {}).get("disabled", []), "myFilters": backup.get("myFilters"),
            "allowed": backup.get("allowed", []), "switches": backup.get("switches", {}),
            "settings": backup.get("settings", {})}


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def _wait_message(ws: WebSocket, words: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if words in (_eval(ws, "document.getElementById('message').textContent") or ""):
            return True
        time.sleep(0.5)
    return False


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="backup-", dir=work))
    downloads = Path(tempfile.mkdtemp(prefix="backup-files-", dir=work))
    # no page is opened; one name keeps the host rules well formed, every other name fails
    proc = _launch(browser, profile, 9, [ALLOWED], native=True)
    port = None

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    try:
        port = _devtools_port(profile)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=10) as reply:
            browser_ws = WebSocket(json.loads(reply.read())["webSocketDebuggerUrl"])
        # where downloads go holds only while this connection is open: it stays open for the run
        browser_ws.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads),
                        eventsEnabled=True)
        page = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
        try:
            time.sleep(3)
            _eval(page, CHANGE)
            got = json.loads(_eval(page, READ))
            report("change", changed_problems("change", got), got)

            _eval(page, "document.getElementById('backup').click(); 1")
            # the list switched off is still being built in: the backup waits for the browser's answers
            _wait_message(page, "saved as a file", 90)
            files: list[Path] = []
            for _ in range(40):
                files = [f for f in downloads.glob("*.json")]
                if files:
                    break
                time.sleep(0.5)
            time.sleep(1)
            if not files:
                report("backup", ["backup: no file was saved"], [])
                return problems
            backup = json.loads(files[0].read_text(encoding="utf-8"))
            found = changed_problems("backup", backup_as_read(backup))
            if backup.get("format") != "thoron-adblock-backup" or backup.get("version") != 1:
                found.append("backup: the file does not say what it is")
            report("backup", found, files[0].name)

            _eval(page, "window.confirm = () => true; document.getElementById('reset').click(); 1")
            if not _wait_message(page, "back to its defaults", 90):
                report("reset", ["reset: the page never said it was done"], {})
            got = json.loads(_eval(page, READ))
            report("reset", default_problems(got), got)

            page.call("DOM.enable")
            root = page.call("DOM.getDocument")["root"]["nodeId"]
            node = page.call("DOM.querySelector", nodeId=root, selector="#restore-file")["nodeId"]
            page.call("DOM.setFileInputFiles", files=[str(files[0])], nodeId=node)
            if not _wait_message(page, "was restored", 90):
                report("restore", ["restore: the page never said it was done"], {})
            got = json.loads(_eval(page, READ))
            report("restore", changed_problems("restore", got), got)
        finally:
            page.close()
            browser_ws.close()
    except (OSError, RuntimeError, ValueError, KeyError) as e:
        problems.append(f"the run failed: {e}")
    finally:
        if port is not None:
            _close_browser(port, proc)
        else:
            bench._stop(proc, profile)
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(downloads, ignore_errors=True)
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
    print("BACKUP CHECK: PASSED" if not problems else f"BACKUP CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
