#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the list viewer of chrome://adblock, checked end to end and offline (ROADMAP P5.55).

As uBlock Origin shows a list when its name is clicked: "View" next to a list in use shows its rules as the
engine uses them, read only, with what the list says about itself and a box that shows only the lines with
some words. A local server serves one list to add (the updater is pointed at the server, which lets a list
at a local address be added; every other list it asks for is not found, so the shipped copies stay; every
other name fails, so nothing leaves the PC). Steps:

    builtin   "View" on EasyList shows its rules, all of its thousands of lines
    find      "Show only lines with" shows only the lines with the words, and how many of all
    added     a list added from the server shows exactly its text, its name and its "Expires" line
    off       a built-in list switched off has no "View"
    refused   an id of no list in use, or something that is no id, gives nothing

    py -3 -I tools/qa/adblock_viewer_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

SETTINGS_URL = "chrome://adblock/"
SETTLE_S = 3.0
LIST_NAME = "viewer"
LIST_TEXT = ("! Title: Viewer check\n! Expires: 2 days\n! Homepage: https://lists.example/\n"
             "||viewer-check.test^\nexample.com##.viewer-check\n")
FIND = "doubleclick"
LIST_OFF = "easyprivacy"


def list_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/lists/{LIST_NAME}.txt"


def read_viewer(word: str = "") -> str:
    return f"""JSON.stringify((() => {{
  const lines = document.getElementById('viewer-text').value.split('\\n');
  const word = {json.dumps(word)};
  return {{open: document.getElementById('viewer').open,
          title: document.getElementById('viewer-title').textContent,
          about: document.getElementById('viewer-about').textContent,
          count: document.getElementById('viewer-count').textContent,
          more: !document.getElementById('viewer-more').hidden,
          lines: lines.length, rules: lines.filter((l) => l && !l.startsWith('!')).length,
          every: !!word && lines.every((l) => l.toLowerCase().includes(word)),
          text: lines.length < 50 ? lines.join('\\n') : ''}};
}})())"""


def view(list_id: str) -> str:
    return (f"(() => {{ const b = document.querySelector('[data-id={json.dumps(list_id)}] button.view');"
            " if (b) b.click(); return !!b; })()")


def builtin_problems(seen: dict) -> list[str]:
    out = []
    if not seen.get("open"):
        return ["builtin: the viewer did not open"]
    if seen.get("title") != "EasyList":
        out.append(f"builtin: the viewer is titled {seen.get('title')!r}")
    if seen.get("rules", 0) < 1000:
        out.append(f"builtin: only {seen.get('rules')} rules are shown")
    if not re.fullmatch(r"[\d,]+ lines", seen.get("count", "")):
        out.append(f"builtin: the count says {seen.get('count')!r}")
    if seen.get("more"):
        out.append("builtin: EasyList is said to have more lines than are shown")
    if "Expires: " not in seen.get("about", ""):
        out.append(f"builtin: what the list says of itself is {seen.get('about')!r}")
    return out


def find_problems(seen: dict, total: str) -> list[str]:
    out = []
    m = re.fullmatch(r"([\d,]+) of ([\d,]+) lines", seen.get("count", ""))
    if not m:
        return [f"find: the count says {seen.get('count')!r}"]
    shown, of = int(m.group(1).replace(",", "")), m.group(2)
    if not (0 < shown < int(of.replace(",", ""))):
        out.append(f"find: {shown} of {of} lines are shown")
    if f"{of} lines" != total:
        out.append(f"find: of {of} lines, but the list has {total}")
    if not seen.get("every"):
        out.append(f"find: a line shown does not have {FIND!r}")
    return out


def added_problems(seen: dict) -> list[str]:
    out = []
    if not seen.get("open"):
        return ["added: the viewer did not open"]
    if seen.get("title") != "Viewer check":
        out.append(f"added: the viewer is titled {seen.get('title')!r}")
    if seen.get("text") != LIST_TEXT.rstrip("\n"):
        out.append(f"added: it shows {seen.get('text')!r}")
    if "Expires: 2 days" not in seen.get("about", "") or "Homepage: " not in seen.get("about", ""):
        out.append(f"added: what the list says of itself is {seen.get('about')!r}")
    return out


def refused_problems(answers: list) -> list[str]:
    return [] if answers == [None, None, None] else [f"refused: the answers are {answers}"]


class Server:
    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path.split("?")[0] == f"/lists/{LIST_NAME}.txt":
                    body, status = LIST_TEXT.encode(), 200
                else:
                    body, status = b"not found", 404  # the shipped lists stay
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
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


def _launch(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            "--enable-features=ThoronNativeAdblock",
            f"--thoron-adblock-lists-url-for-testing=http://127.0.0.1:{port}/lists/",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in reply:
        raise RuntimeError(reply["exceptionDetails"].get("text", "the page threw"))
    return reply.get("result", {}).get("value")


def _wait_viewer(ws: WebSocket, word: str = "") -> dict:
    seen: dict = {}
    for _ in range(60):
        time.sleep(0.5)
        seen = json.loads(_eval(ws, read_viewer(word)) or "{}")
        if seen.get("count") and seen.get("count") != "Loading...":
            break
    return seen


ASK = """(async () => {{ const {{sendWithPromise}} = await import('chrome://resources/js/cr.js');
  return {action}; }})()"""


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    profile = Path(tempfile.mkdtemp(prefix="viewer-", dir=work))

    def report(step: str, found: list[str], seen) -> None:
        print(f"{'PASS' if not found else 'FAIL'}  {step}: {seen}")
        problems.extend(found)

    with Server() as server:
        proc = _launch(browser, profile, server.port)
        port = None
        try:
            port = _devtools_port(profile)
            page = WebSocket(_open(port, SETTINGS_URL)["webSocketDebuggerUrl"])
            try:
                time.sleep(SETTLE_S)
                _eval(page, view("easylist"))
                seen = _wait_viewer(page)
                report("builtin", builtin_problems(seen), {k: seen.get(k) for k in ("title", "count", "rules")})
                total = seen.get("count", "")

                _eval(page, "(() => { const f = document.getElementById('viewer-find');"
                            f" f.value = {json.dumps(FIND)}; f.dispatchEvent(new Event('input')); return 1; }})()")
                seen = json.loads(_eval(page, read_viewer(FIND)) or "{}")
                report("find", find_problems(seen, total), seen.get("count"))
                _eval(page, "document.getElementById('viewer-close').click(); 1")

                error = _eval(page, ASK.format(action=f"sendWithPromise('addList', {json.dumps(list_url(server.port))})"))
                if error:
                    report("added", [f"added: the list was not added: {error}"], error)
                else:
                    page.call("Page.reload")
                    time.sleep(SETTLE_S)
                    list_id = _eval(page, ASK.format(action="(await sendWithPromise('getState')).lists.find("
                                                           f"(l) => l.url === {json.dumps(list_url(server.port))}).id"))
                    _eval(page, view(list_id))
                    seen = _wait_viewer(page)
                    report("added", added_problems(seen), {k: seen.get(k) for k in ("title", "about", "count")})
                    _eval(page, "document.getElementById('viewer-close').click(); 1")

                _eval(page, f"document.querySelector('[data-id={json.dumps(LIST_OFF)}] input').click(); 1")
                time.sleep(SETTLE_S + 2)  # the engine is built again
                has = _eval(page, f"!!document.querySelector('[data-id={json.dumps(LIST_OFF)}] button.view')")
                report("off", [] if has is False else [f"off: {LIST_OFF} switched off still has View"], has)

                answers = [_eval(page, ASK.format(action=f"sendWithPromise('getListText', {json.dumps(i)})"))
                           for i in ("no-such-list", "../state", LIST_OFF)]
                report("refused", refused_problems(answers), answers)
            finally:
                page.close()
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
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
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work)
    for problem in problems:
        print(problem)
    print("VIEWER CHECK: PASSED" if not problems else f"VIEWER CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
