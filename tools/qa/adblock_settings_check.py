#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""The settings page of native ad blocking, chrome://adblock, checked end to end and offline (ROADMAP P5.30).

It starts the browser headless on a throwaway profile (sandbox on, DevTools on 127.0.0.1 only) with the
ThoronNativeAdblock feature, opens chrome://adblock and works it the way a person does: it types into the
boxes and clicks the buttons of the page. After every step it loads a local test page that asks three
test hosts for a script, and looks which ones were blocked. Host-resolver rules send the test hosts to a
local server and make every other host fail; the built-in lists come from that server too.

    default                the first update is in: the built-in easylist blocks its test host, 8 lists shown
    my filters             a rule of one's own is saved: its host is blocked
    refused rule           a rule that allows every request is refused; nothing changes; the box keeps the text
    add a list             a list is added by its address: its host is blocked, its title is shown, and its
                           rule that asks for trust (a trusted scriptlet) is not carried out
    refused list           a web page instead of a list is refused
    not https              an address that is not secure is refused
    list off               easylist is switched off: its host is no longer blocked, the others still are
    after a restart        the browser is closed and started again: every choice is still there and in force
    list on                easylist is switched on again: its host is blocked again, by the updated copy
    after an update        the state on disk is from another browser version, as after an update of the
                           browser: the added list and the own rules are in force from the start, and the
                           built-in lists are fetched again
    remove the list        the added list is removed: its host is no longer blocked
    after an interruption  the state says the browser stopped while it read these settings: at the next start
                           they are not read again, the engine saved before is used, and the page says so
    change after it        the next change is read and used, and the notice is gone
    no filters             the own rules are emptied: their host is no longer blocked

    py -3 -I tools/qa/adblock_settings_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import copy
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port  # noqa: E402
from tools.qa.adblock_update_check import split_lists  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

HOSTS = {"easy": "easy-host.test", "list": "list-host.test", "mine": "mine-host.test"}
PAGE_HOST = "page.test"
STORE_DIR = "Thoron Adblock"
MINE = f"||{HOSTS['mine']}^\n"
# A list a person adds: a title, a rule, and a rule that only a trusted list may use.
EXTRA_LIST = (f"! Title: Extra test list\n||{HOSTS['list']}^\n"
              f"{PAGE_HOST}##+js(trusted-set-cookie, thoron_trusted, yes)\n")
BAD_LIST = "<!doctype html>\n<html><body><h1>Sign in</h1></body></html>\n"
PAGE = """<!doctype html>
<meta charset="utf-8"><title>Thoron settings check</title>
<script>
window.results = {};
for (const host of %(hosts)s) {
  const s = document.createElement("script");
  s.onload = () => { window.results[host] = "loaded"; };
  s.onerror = () => { window.results[host] = "blocked"; };
  s.src = "http://" + host + ":%(port)d/probe.js?t=" + Date.now();
  document.head.appendChild(s);
}
</script>
"""
READ_PAGE = """JSON.stringify((() => {
  const rows = [...document.querySelectorAll('#lists .list')];
  const checked = {};
  for (const r of rows) { const box = r.querySelector('input'); if (box) checked[r.dataset.id] = box.checked; }
  const message = document.getElementById('message');
  return {rows: rows.length, custom: rows.filter(r => r.querySelector('button:not(.view)')).length, checked,
          titles: rows.map(r => r.querySelector('.title').textContent),
          message: message.textContent, bad: message.classList.contains('bad'),
          busy: document.body.classList.contains('busy'),
          filters: document.getElementById('my-filters').value,
          not_applied: !document.getElementById('not-applied').hidden};
})())"""
ALL = {"easy": True, "list": True, "mine": True}

# What is done, and what must be true afterwards. Blocked hosts are named by their key in HOSTS.
STEPS = [
    {"name": "default", "act": ("none",),
     "want": {"blocked": {"easy": True, "list": False, "mine": False}, "rows": 8, "custom": 0,
              "checked": {"easylist": True}, "not_applied": False}},
    {"name": "my filters", "act": ("filters", MINE),
     "want": {"blocked": {"easy": True, "list": False, "mine": True}, "message": "saved", "bad": False}},
    {"name": "refused rule", "act": ("filters", MINE + "@@*\n"),
     "want": {"blocked": {"easy": True, "list": False, "mine": True}, "message": "allows every request",
              "bad": True, "filters": MINE + "@@*\n"}},
    {"name": "add a list", "act": ("add", "/extra.txt"),
     "want": {"blocked": ALL, "message": "added", "bad": False, "rows": 9, "custom": 1,
              "title": "Extra test list", "no_cookie": "thoron_trusted"}},
    {"name": "refused list", "act": ("add", "/bad.txt"),
     "want": {"blocked": ALL, "message": "not a usable filter list", "bad": True, "rows": 9}},
    {"name": "not https", "act": ("add_url", "http://lists.example/filters.txt"),
     "want": {"blocked": ALL, "message": "https://", "bad": True, "rows": 9}},
    {"name": "list off", "act": ("toggle", "easylist"),
     "want": {"blocked": {"easy": False, "list": True, "mine": True}, "message": "switched off", "bad": False,
              "checked": {"easylist": False}}},
    {"name": "after a restart", "act": ("restart",),
     "want": {"blocked": {"easy": False, "list": True, "mine": True}, "rows": 9, "custom": 1,
              "checked": {"easylist": False}, "filters": MINE, "not_applied": False}},
    {"name": "list on", "act": ("toggle", "easylist"),
     "want": {"blocked": ALL, "message": "in use", "bad": False, "checked": {"easylist": True}}},
    {"name": "after an update", "act": ("version",),
     "want": {"blocked": ALL, "rows": 9, "custom": 1, "filters": MINE, "not_applied": False,
              "first": {"list": True, "mine": True}}},
    {"name": "remove the list", "act": ("remove",),
     "want": {"blocked": {"easy": True, "list": False, "mine": True}, "message": "removed", "bad": False,
              "rows": 8, "custom": 0}},
    {"name": "after an interruption", "act": ("interrupt",),
     "want": {"blocked": {"easy": True, "list": False, "mine": True}, "not_applied": True, "still_marked": True,
              "filters": MINE}},
    {"name": "change after it", "act": ("toggle", "easyprivacy"),
     "want": {"blocked": {"easy": True, "list": False, "mine": True}, "message": "switched off", "bad": False,
              "not_applied": False, "still_marked": False}},
    {"name": "no filters", "act": ("filters", ""),
     "want": {"blocked": {"easy": True, "list": False, "mine": False}, "message": "saved", "bad": False}},
]


def served_lists(bundled: dict[str, str]) -> dict[str, str]:
    """The browser's own lists, with one more rule in easylist: the update brings it."""
    served = dict(bundled)
    served["easylist"] = bundled.get("easylist", "") + f"||{HOSTS['easy']}^\n"
    return served


def page_html(port: int) -> str:
    return PAGE % {"hosts": json.dumps(sorted(HOSTS.values())), "port": port}


def blocked(results: dict) -> dict:
    """Per probe host: True blocked, False loaded, None when the page has no answer for it."""
    return {key: {"blocked": True, "loaded": False}.get(results.get(host)) for key, host in HOSTS.items()}


def interrupted(state: dict) -> dict:
    """The state file as it is while the lists for the present settings are being read."""
    faked = copy.deepcopy(state)
    faked["building"] = state.get("settings", "")
    faked["settings"] = "the settings before"
    return faked


def other_version(state: dict) -> dict:
    """The state file as another version of the browser would have left it."""
    changed = copy.deepcopy(state)
    changed["version"] = "0.0.0.1"
    return changed


def step_problems(name: str, want: dict, got: dict) -> list[str]:
    found = []
    for key, expected in want.get("first", {}).items():
        if got.get("first", {}).get(key) != expected:
            found.append(f"right after the start {HOSTS[key]} is not blocked")
    for key, expected in want.get("blocked", {}).items():
        actual = got.get("blocked", {}).get(key)
        if actual is None:
            found.append(f"the test page has no answer for {HOSTS[key]}")
        elif actual != expected:
            found.append(f"{HOSTS[key]} is {'blocked' if actual else 'not blocked'}, expected "
                         f"{'blocked' if expected else 'not blocked'}")
    if "message" in want and want["message"] not in got.get("message", ""):
        found.append(f"message is {got.get('message', '')!r}, expected one with {want['message']!r}")
    if "bad" in want and got.get("bad") != want["bad"]:
        found.append("the page shows " + ("no error where one is due" if want["bad"] else "an error"))
    if "rows" in want and got.get("rows") != want["rows"]:
        found.append(f"rows: {got.get('rows')} lists are shown, expected {want['rows']}")
    if "custom" in want and got.get("custom") != want["custom"]:
        found.append(f"added lists shown: {got.get('custom')}, expected {want['custom']}")
    if "title" in want and want["title"] not in got.get("titles", []):
        found.append(f"no list is shown as {want['title']!r}")
    if "no_cookie" in want and want["no_cookie"] in got.get("cookie", ""):
        found.append(f"a cookie was set by a rule that needs trust: {got.get('cookie')!r}")
    for list_id, expected in want.get("checked", {}).items():
        actual = got.get("checked", {}).get(list_id)
        if actual != expected:
            shown = "not shown" if actual is None else ("shown on" if actual else "shown off")
            found.append(f"{list_id} is {shown}, expected {'on' if expected else 'off'}")
    if "not_applied" in want and got.get("not_applied") != want["not_applied"]:
        found.append("the notice that the settings are not in use is "
                     + ("missing" if want["not_applied"] else "shown"))
    if "filters" in want and got.get("filters") != want["filters"]:
        found.append(f"the box of own rules holds {got.get('filters')!r}, expected {want['filters']!r}")
    if "still_marked" in want and got.get("still_marked") != want["still_marked"]:
        found.append("the state file " + ("no longer says" if want["still_marked"] else "still says")
                     + " that these settings were being read")
    return [f"{name}: {p}" for p in found]


class Server:
    """The test page, the probe script, the built-in lists and the lists a person could add."""

    def __init__(self, lists: dict[str, str]):
        self.lists = lists
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                if path == "/page.html":
                    self._send(200, "text/html; charset=utf-8", page_html(server.port).encode())
                elif path == "/probe.js":
                    self._send(200, "text/javascript", b"window.__probe = 1;")
                elif path == "/extra.txt":
                    self._send(200, "text/plain; charset=utf-8", EXTRA_LIST.encode())
                elif path == "/bad.txt":
                    self._send(200, "text/html; charset=utf-8", BAD_LIST.encode())
                elif path.startswith("/lists/") and path.endswith(".txt"):
                    text = server.lists.get(path[len("/lists/"):-len(".txt")])
                    if text is None:
                        self._send(404, "text/plain", b"not found")
                    else:
                        self._send(200, "text/plain; charset=utf-8", text.encode("utf-8"))
                else:
                    self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


class Browser:
    """One run of the browser on the profile, with the settings page and the test page open."""

    def __init__(self, browser: Path, profile: Path, port: int):
        self.profile, self.port = profile, port
        port_file = profile / "DevToolsActivePort"
        if port_file.exists():
            port_file.unlink()
        args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
                "--disable-component-update", "--enable-features=ThoronNativeAdblock",
                f"--thoron-adblock-lists-url-for-testing=http://127.0.0.1:{port}/lists/",
                "--host-resolver-rules=MAP *.test 127.0.0.1, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.devtools = _devtools_port(profile)
        self.settings = self._open("chrome://adblock/")
        self.page = self._open("about:blank")
        self._wait(lambda: self._eval(self.settings, "!!document.getElementById('lists')"), 30)
        self.wait_idle()

    def _open(self, url: str) -> WebSocket:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.devtools}/json/new?{urllib.parse.quote(url, safe=':/')}", method="PUT")
        return WebSocket(json.loads(urllib.request.urlopen(req, timeout=20).read())["webSocketDebuggerUrl"])

    @staticmethod
    def _eval(tab: WebSocket, expression: str):
        return tab.call("Runtime.evaluate", expression=expression, returnByValue=True)["result"].get("value")

    @staticmethod
    def _wait(done, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if done():
                    return True
            except (RuntimeError, OSError, ValueError, KeyError):
                pass
            time.sleep(0.25)
        return False

    def read(self) -> dict:
        return json.loads(self._eval(self.settings, READ_PAGE))

    def wait_idle(self) -> None:
        """Until the page has the answer to what was asked last."""
        time.sleep(0.4)
        self._wait(lambda: not (lambda s: s["busy"] or s["message"] == "Working...")(self.read()), 90)

    def act(self, script: str) -> None:
        self._eval(self.settings, f"(() => {{ {script} }})()")
        self.wait_idle()

    def set_filters(self, text: str) -> None:
        self.act(f"const b = document.getElementById('my-filters'); b.value = {json.dumps(text)}; "
                 "b.dispatchEvent(new Event('input')); document.getElementById('save-filters').click();")

    def undo_filters(self) -> None:
        self.act("document.getElementById('revert-filters').click();")

    def add(self, url: str) -> None:
        self.act(f"document.getElementById('add-url').value = {json.dumps(url)}; "
                 "document.getElementById('add-form').requestSubmit();")

    def toggle(self, list_id: str) -> None:
        self.act(f"document.querySelector('#lists .list[data-id={json.dumps(list_id)}] input').click();")

    def remove(self) -> None:
        # the list's "Remove" (every list in use also has "View", P5.55)
        self.act("document.querySelector('#lists .list button:not(.view)').click();")

    def probe(self) -> tuple[dict, str]:
        """Loads the test page anew and says what it saw: per host loaded or blocked, and its cookies."""
        url = f"http://{PAGE_HOST}:{self.port}/page.html?t={time.monotonic_ns()}"
        self.page.call("Page.navigate", url=url)
        self._wait(lambda: len(json.loads(self._eval(self.page, "JSON.stringify(window.results || {})"))) == len(HOSTS),
                   10)
        results = json.loads(self._eval(self.page, "JSON.stringify(window.results || {})"))
        return results, self._eval(self.page, "document.cookie") or ""

    def state(self) -> dict:
        try:
            return json.loads((self.profile / STORE_DIR / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def saved_filters(self) -> str:
        """The own rules as the browser saved them."""
        try:
            return (self.profile / STORE_DIR / "my-filters.txt").read_bytes().decode("utf-8")
        except OSError:
            return ""

    def close(self) -> None:
        for tab in (self.settings, self.page):
            try:
                tab.close()
            except OSError:
                pass
        _close_browser(self.devtools, self.proc)


def run(browser: Path, work: Path, lists_file: Path) -> list[str]:
    bundled = split_lists(lists_file.read_text(encoding="utf-8"))
    if "easylist" not in bundled:
        return [f"{lists_file} holds no easylist"]
    work.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="settings-", dir=work))
    problems: list[str] = []
    with Server(served_lists(bundled)) as server:
        b = Browser(browser, profile, server.port)
        try:
            for step in STEPS:
                kind, *args = step["act"]
                if kind == "none":
                    # the first update, a second after the engine started
                    Browser._wait(lambda: "easylist: updated" in b.state().get("result", ""), 120)
                elif kind == "filters":
                    b.set_filters(args[0])
                elif kind == "add":
                    b.add(f"http://127.0.0.1:{server.port}{args[0]}")
                elif kind == "add_url":
                    b.add(args[0])
                elif kind == "toggle":
                    b.toggle(args[0])
                elif kind == "remove":
                    b.remove()
                first = {}
                if kind in ("restart", "interrupt", "version"):
                    b.close()
                    if kind != "restart":
                        path = profile / STORE_DIR / "state.json"
                        state = json.loads(path.read_text(encoding="utf-8"))
                        changed = interrupted(state) if kind == "interrupt" else other_version(state)
                        path.write_text(json.dumps(changed), encoding="utf-8")
                    b = Browser(browser, profile, server.port)
                    if kind == "version":
                        # what holds before the lists are fetched again, then what holds after
                        first = blocked(b.probe()[0])
                        Browser._wait(lambda: "easylist: updated" in b.state().get("result", ""), 120)
                got = b.read()
                results, cookie = b.probe()
                got.update(blocked=blocked(results), cookie=cookie, still_marked="building" in b.state(),
                           first=first)
                found = step_problems(step["name"], step["want"], got)
                print(f"{'PASS' if not found else 'FAIL'}  {step['name']}: "
                      f"{', '.join(f'{k} {v}' for k, v in sorted(results.items()))}; {got['message']!r}")
                problems += found
                if got["filters"] != b.saved_filters():
                    b.undo_filters()        # a refused rule stays in the box; start the next step clean
        finally:
            b.close()
    shutil.rmtree(profile, ignore_errors=True)
    return problems


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path)
    p.add_argument("--lists", type=Path, help="the bundled lists file (default: next to the browser)")
    a = p.parse_args(argv)
    lists_file = a.lists or a.browser.parent / "thoron_adblock_lists.txt"
    problems = run(a.browser, a.work, lists_file)
    for problem in problems:
        print(problem)
    print("SETTINGS CHECK: PASSED" if not problems else f"SETTINGS CHECK: FAILED ({len(problems)} problem(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
