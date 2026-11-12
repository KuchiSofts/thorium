#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, strict blocking: a page the lists block is not opened, checked end to end and offline
(ROADMAP P5.37).

As in uBlock Origin, a page is blocked by a rule for whole pages (`$doc`, `$all`) or by a rule that names its
whole host (`||ads.example^`), and a page that says why is shown in its place. A local server answers for every
name used (host-resolver rules; every other name fails, so nothing leaves the PC) and writes down which hosts
were asked. The hosts come from the bundled lists: the first plain host rule of EasyList, the first `$doc` rule
and the first `$all` rule of uBlock Origin's badware list.

    control    native blocking off: every page opens
    native     the three pages are not opened and the blocked page names the site; a plain page opens; a plain
               page that redirects to a blocked host ends on the blocked page; a blocked redirector that names
               a plain address offers it as a link, and the link opens it
    site-off   ads allowed on the host of the plain host rule: its page opens

    py -3 -I tools/qa/adblock_strict_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
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
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import NOT_FOR_REPORTS, WARM_HTML  # noqa: E402
from tools.qa.adblock_earlyhints_check import ad_host  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import _launch  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "site-off")
PLAIN_HOST = "plain-strict.test"
BLOCKED_TITLE = "Thoron blocked this page"
SETTLE_S = 2.5
PAGE_RULE = re.compile(r"\|\|([a-z0-9-]+(?:\.[a-z0-9-]+)+)\^\$(doc|document|all)")


def page_hosts(lists_text: str) -> dict[str, str]:
    """The first `$doc` (or `$document`) and the first `$all` rule of uBlock Origin's badware list that name a
    whole host and nothing more: {"doc": host, "all": host}."""
    found: dict[str, str] = {}
    current = ""
    for line in (line.strip() for line in lists_text.splitlines()):
        if line.startswith("! thoron-list: "):
            current = line.removeprefix("! thoron-list: ").strip()
        elif current == "ublock-badware" and (m := PAGE_RULE.fullmatch(line)) and \
                not any(word in m.group(1) for word in NOT_FOR_REPORTS):
            kind = "all" if m.group(2) == "all" else "doc"
            found.setdefault(kind, m.group(1))
    return found


def cases(hosts: dict[str, str]) -> dict[str, str]:
    """The address of each page the check opens."""
    onward = urllib.parse.quote(f"http://{PLAIN_HOST}/landing", safe="")
    return {
        "host": f"http://{hosts['host']}/page",
        "doc": f"http://{hosts['doc']}/page",
        "all": f"http://{hosts['all']}/page",
        "plain": f"http://{PLAIN_HOST}/page",
        "redirect": f"http://{PLAIN_HOST}/go",
        "onward": f"http://{hosts['host']}/click?url={onward}",
    }


def native_problems(seen: dict, hosts: dict[str, str]) -> list[str]:
    out = []
    asked = {tuple(item) for item in seen.get("asked", [])}
    for kind in ("host", "doc", "all"):
        page = seen.get(kind, {})
        if page.get("title") != BLOCKED_TITLE:
            out.append(f"the {kind} page was opened (title {page.get('title')!r})")
        elif hosts[kind] not in page.get("text", ""):
            out.append(f"the blocked {kind} page does not name its site {hosts[kind]}")
        if any(name == hosts[kind] for name, _ in asked):
            out.append(f"the {kind} host was asked")
    if seen.get("plain", {}).get("title") != "plain":
        out.append("the plain page did not open")
    if seen.get("redirect", {}).get("title") != BLOCKED_TITLE:
        out.append("a redirect to a blocked host was followed")
    onward = seen.get("onward", {})
    if onward.get("title") != BLOCKED_TITLE:
        out.append("the blocked redirector was opened")
    elif f"http://{PLAIN_HOST}/landing" not in onward.get("links", []):
        out.append("the blocked redirector's page does not offer where it sends on to")
    elif (PLAIN_HOST, "/landing") not in asked:
        out.append("the link to where the redirector sends on to did not open it")
    return out


def opened_problems(seen: dict, kinds: tuple[str, ...]) -> list[str]:
    return [f"the {kind} page was not opened (title {seen.get(kind, {}).get('title')!r})"
            for kind in kinds if seen.get(kind, {}).get("title") != "plain"]


class Server:
    def __init__(self, hosts: dict[str, str]):
        self.asked: set[tuple[str, str]] = set()
        server = self
        names = set(hosts.values()) | {PLAIN_HOST}

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, status: int, body: bytes, headers: dict | None = None):
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                name = (self.headers.get("Host") or "").split(":")[0]
                path = self.path.split("?")[0]
                if name == "127.0.0.1" and path == "/warm.html":
                    self._send(200, WARM_HTML.encode())
                    return
                if name in names and path != "/favicon.ico":
                    server.asked.add((name, path))
                if name == PLAIN_HOST and path == "/go":
                    self._send(302, b"", {"Location": f"http://{hosts['host']}/page"})
                else:
                    self._send(200, b"<!doctype html><title>plain</title><p>a page</p>")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


READ = """JSON.stringify({title: document.title, text: document.body ? document.body.innerText : '',
  links: Array.from(document.querySelectorAll('a[href]')).map((a) => a.href)})"""


def _visit(port: int, url: str) -> tuple[WebSocket, dict]:
    target = _open(port, "about:blank")
    ws = WebSocket(target["webSocketDebuggerUrl"])
    ws.call("Page.navigate", url=url)
    time.sleep(SETTLE_S)
    reply = ws.call("Runtime.evaluate", expression=READ, returnByValue=True)
    return ws, json.loads(reply.get("result", {}).get("value") or "{}")


def _allow_ads_on(port: int, host: str) -> None:
    ws = WebSocket(_open(port, "chrome://settings/content/ads")["webSocketDebuggerUrl"])
    try:
        time.sleep(3)
        allow = [host, "", "ads", "allow", False]
        ws.call("Runtime.evaluate", expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
        time.sleep(1)
    finally:
        ws.close()


def run_mode(browser: Path, work: Path, hosts: dict[str, str], mode: str) -> list[str]:
    profile = Path(tempfile.mkdtemp(prefix=f"strict-{mode}-", dir=work))
    seen: dict = {}
    found: list[str] = []
    urls = cases(hosts)
    with Server(hosts) as server:
        proc = _launch(browser, profile, server.port, sorted(set(hosts.values()) | {PLAIN_HOST}),
                       native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                _allow_ads_on(port, hosts["host"])
            if mode != "control":
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            kinds = ("host",) if mode == "site-off" else ("host", "doc", "all", "plain", "redirect", "onward")
            for kind in kinds:
                ws, seen[kind] = _visit(port, urls[kind])
                try:
                    if kind == "onward" and mode == "native" and seen[kind].get("links"):
                        ws.call("Runtime.evaluate", expression="document.querySelector('a[href]').click(); 1",
                                userGesture=True)
                        time.sleep(SETTLE_S)
                finally:
                    ws.close()
            seen["asked"] = sorted(server.asked)
            if mode == "native":
                found = native_problems(seen, hosts)
            else:
                found = opened_problems(seen, ("host",) if mode == "site-off" else ("host", "doc", "all", "plain"))
        except (OSError, RuntimeError, ValueError, KeyError) as e:
            found = [f"the run failed: {e}"]
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    brief = {k: v.get("title") if isinstance(v, dict) else v for k, v in seen.items() if k != "asked"}
    print(f"{'PASS' if not found else 'FAIL'}  {mode}: {json.dumps(brief)}" + (f"; {'; '.join(found)}" if found else ""))
    return [f"{mode}: {p}" for p in found]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    text = (a.lists or a.browser.parent / "thoron_adblock_lists.txt").read_text(encoding="utf-8")
    hosts = page_hosts(text)
    host = ad_host(text)
    if host is None or set(hosts) != {"doc", "all"}:
        print("STRICT CHECK: FAILED (the lists hold no plain host rule, or no $doc and $all rule for a host)")
        return 1
    hosts["host"] = host
    print(f"    hosts: {hosts}")
    a.work.mkdir(parents=True, exist_ok=True)
    found = [p for mode in MODES for p in run_mode(a.browser.resolve(), a.work, hosts, mode)]
    for problem in found:
        print(problem)
    print("STRICT CHECK: PASSED" if not found else f"STRICT CHECK: FAILED ({len(found)} problem(s))")
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
