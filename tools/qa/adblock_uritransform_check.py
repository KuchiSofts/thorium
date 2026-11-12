#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, `$uritransform`, checked end to end and offline (ROADMAP P5.26).

A `$uritransform` rule makes another address of a request's own, with a regular expression and a
replacement. The check takes two real rules from the browser's bundled lists, the first of each kind
whose address pattern ends with the plain text it replaces:

    page     a page's own address: the browser goes to the changed address, by a redirect it sees
    script   a script of a page: it is fetched from the changed address of the same site, and runs

The rules' site names and the page's are sent to a local server by host-resolver rules; every other
name fails, so nothing leaves the PC. The server writes down every address it is asked for. With native
blocking on, only the changed address may be asked for; with blocking off (control), and with ads allowed
on the page's site (site-off), only the address as it was.

    py -3 -I tools/qa/adblock_uritransform_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every case passes in every mode.
"""
import argparse
import http.server
import json
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch, _navigate  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
PAGE_HOST = "uri-check.test"
SETTLE_S = 3.0
_PLAIN = r"([A-Za-z0-9%=._-]+)"
# ||host/*TEXT$doc,uritransform=/TEXT/NEW/   and   ||host/path$script,uritransform=/TEXT/NEW/
PAGE_RE = re.compile(r"\|\|([a-z0-9.-]+)/\*" + _PLAIN + r"\$doc,uritransform=/" + _PLAIN + "/" + _PLAIN + "/")
SCRIPT_RE = re.compile(r"\|\|([a-z0-9.-]+)((?:/[A-Za-z0-9_.-]+)+)\$script,uritransform=/" + _PLAIN + "/" + _PLAIN + "/")


def cases(lists_text: str) -> dict:
    out: dict = {}
    for line in (line.strip() for line in lists_text.splitlines()):
        if "page" not in out and (m := PAGE_RE.fullmatch(line)) and m.group(2) == m.group(3):
            out["page"] = {"host": m.group(1), "path": "/check", "from": m.group(3), "to": m.group(4)}
        elif "script" not in out and (m := SCRIPT_RE.fullmatch(line)):
            out["script"] = {"host": m.group(1), "path": m.group(2), "from": m.group(3), "to": m.group(4)}
    return out


def address(case: dict, which: str) -> str:
    query = f"q={case[which]}" if case["path"] == "/check" else case[which]
    return f"http://{case['host']}{case['path']}?{query}"


def hosts(found: dict) -> list[str]:
    return sorted({case["host"] for case in found.values()} | {PAGE_HOST})


def page_html(found: dict) -> str:
    src = json.dumps(address(found["script"], "from"))
    return ('<!doctype html><meta charset="utf-8"><title>Thoron uritransform check</title><script>'
            f"const s = document.createElement('script'); s.src = {src};"
            "s.onload = () => fetch('/result', {method: 'POST', body: 'loaded'});"
            "s.onerror = () => fetch('/result', {method: 'POST', body: 'blocked'});"
            "document.head.appendChild(s);</script>")


def problems(kind: str, case: dict, native: bool, seen: list, outcome: str | None) -> list[str]:
    """`seen`: (host, path with query) the server was asked for; `outcome`: for a page the address it
    shows at the end, for a script "loaded" or "blocked"."""
    want, other = ("to", "from") if native else ("from", "to")
    asked = [path for host, path in seen if host == case["host"]]
    out = []
    if any(case[other] in path for path in asked):
        out.append("the address was asked for as it was" if native else
                   "the address was changed though blocking is off here")
    if not any(case[want] in path for path in asked):
        out.append(f"the server was never asked for the address with {case[want]!r}")
    if kind == "page" and (outcome is None or case[want] not in outcome):
        out.append(f"the page shows {outcome!r}, not the address with {case[want]!r}")
    if kind == "script" and outcome != "loaded":
        out.append("the script did not run")
    return out


class Server:
    def __init__(self, found: dict):
        self.seen: list[tuple[str, str]] = []
        self.outcome: str | None = None
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
                host = (self.headers.get("Host") or "").split(":")[0]
                server.seen.append((host, self.path))
                path = urllib.parse.urlsplit(self.path).path
                if host == "127.0.0.1" and path == "/warm.html":
                    self._send("text/html; charset=utf-8", WARM_HTML.encode())
                elif host == PAGE_HOST and path == "/page.html":
                    self._send("text/html; charset=utf-8", page_html(found).encode())
                elif "script" in found and host == found["script"]["host"] and path == found["script"]["path"]:
                    self._send("text/javascript", b"// the player\n")
                else:
                    self._send("text/html; charset=utf-8", b"<!doctype html><title>page</title><p>page</p>")

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(min(length, 64)).decode("utf-8", "replace")
                if self.path == "/result":
                    server.outcome = body
                self._send("text/plain", b"ok")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _location(port: int) -> str | None:
    """The address of the tab that was opened last."""
    for target in json.loads(_get(f"http://127.0.0.1:{port}/json/list")):
        if target.get("type") == "page":
            return target.get("url")
    return None


def _get(url: str) -> str:
    return urllib.request.urlopen(url, timeout=20).read().decode("utf-8")


def run_mode(browser: Path, work: Path, found: dict, mode: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix=f"uritransform-{mode}-", dir=work))
    out: list[str] = []
    with Server(found) as server:
        proc = _launch(browser, profile, server.port, hosts(found), native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    for name in hosts(found):
                        allow = [name, "", "ads", "allow", False]
                        ws.call("Runtime.evaluate",
                                expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            native = mode == "native"
            for kind, case in found.items():
                server.seen.clear()
                server.outcome = None
                if kind == "page":
                    _navigate(port, address(case, "from"))
                    time.sleep(SETTLE_S)
                    outcome = _location(port)
                else:
                    _navigate(port, f"http://{PAGE_HOST}/page.html")
                    deadline = time.monotonic() + 20
                    while server.outcome is None and time.monotonic() < deadline:
                        time.sleep(0.2)
                    outcome = server.outcome
                found_here = problems(kind, case, native, list(server.seen), outcome)
                print(f"{'PASS' if not found_here else 'FAIL'}  {mode} {kind}: "
                      + ("the address " + ("changed" if native else "as it was") if not found_here else "; ".join(found_here)))
                out += [f"{mode} {kind}: {p}" for p in found_here]
        except (OSError, RuntimeError, ValueError) as e:
            out.append(f"{mode}: {e}")
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    found = cases(lists_file.read_text(encoding="utf-8"))
    missing = [kind for kind in ("page", "script") if kind not in found]
    if missing:
        print(f"URITRANSFORM CHECK: FAILED (the lists hold no plain rule of the kind: {', '.join(missing)})")
        return 1
    a.work.mkdir(parents=True, exist_ok=True)
    found_problems = [p for mode in MODES for p in run_mode(a.browser.resolve(), a.work, found, mode)]
    for problem in found_problems:
        print(problem)
    print("URITRANSFORM CHECK: PASSED" if not found_problems
          else f"URITRANSFORM CHECK: FAILED ({len(found_problems)} problem(s))")
    return 0 if not found_problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
