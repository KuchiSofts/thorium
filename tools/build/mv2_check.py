#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Manifest V2 ad-blocking check (ROADMAP P1.8, later the built-in uBlock Origin release gate).

Runs the browser twice, each time with a fresh throwaway profile and the sandbox on: once without
the extension (control) and once with it (`--load-extension`). Both runs open a local test page,
fully offline: Chrome's host-resolver rules send the real ad host to a local server and make every
other host fail, and background networking and component updates are off. A request the extension
blocks never reaches the server. The page also holds an `.ad_banner` element for the generic
cosmetic filter in EasyList.

Verdict: works (network and cosmetic blocking), partial (one of them), fails (neither), or invalid
when a run cannot be trusted: it failed, the page did not make and finish all its attempts or never
checked the ad frame, the control saw no ads, or the control's last requests were blocked without
the extension (for example by an extension installed by default apps).
    py -3 -I tools/build/mv2_check.py --browser out\\m158\\chrome.exe --extension <unpacked uBO> --work <dir>
Exit status 0 only for "works".
"""
import argparse
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

AD_HOST = "pagead2.googlesyndication.com"   # EasyList: ||pagead2.googlesyndication.com^
ATTEMPTS = 10
INTERVAL_MS = 2000
LATE_ATTEMPTS = 3                            # the last attempts must all be blocked (the blocker may still be starting before)
FRAME_FALLBACK_MS = 14000
HOLD_MS = 26000                              # keeps the page loading while the blocker starts on a new profile
RESULT_RE = re.compile(r'<pre id="thoron-mv2-result">(.*?)</pre>', re.S)
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")

# The ad script our server returns sets window.__thoronAd; a blocker's stand-in script does not.
# The ad element lives in a frame that is added only once blocking is seen (or after a fallback
# delay), so the blocker is running when the frame's content scripts are injected.
PAGE = """<!doctype html>
<meta charset="utf-8"><title>Thoron MV2 check</title>
<pre id="thoron-mv2-result"></pre>
<script>
const ATTEMPTS = %(attempts)d;
const r = {attempts: 0, loaded: 0, stand_ins: 0, errors: 0, frame: false, ad_element_hidden: false};
let frame = null;
function publish() {
  const doc = frame && frame.contentDocument;
  const el = doc && doc.getElementById('thoron-ad');
  if (el) {
    r.frame = true;
    r.ad_element_hidden = el.offsetHeight === 0 || frame.contentWindow.getComputedStyle(el).display === 'none';
  }
  document.getElementById('thoron-mv2-result').textContent = JSON.stringify(r);
}
function addFrame() {
  if (frame) return;
  frame = document.createElement('iframe');
  frame.src = '/frame.html';
  frame.onload = () => setTimeout(publish, 1000);
  document.body.appendChild(frame);
}
let n = 0;
const timer = setInterval(() => {
  window.__thoronAd = 0;
  const s = document.createElement('script');
  s.src = 'http://%(host)s/pagead/js/adsbygoogle.js?n=' + n++;
  s.onload = () => {
    if (window.__thoronAd === 1) { r.loaded++; } else { r.stand_ins++; setTimeout(addFrame, 1000); }
    publish();
  };
  s.onerror = () => { r.errors++; setTimeout(addFrame, 1000); publish(); };
  r.attempts++;
  document.head.appendChild(s);
  if (n >= ATTEMPTS) clearInterval(timer);
}, %(interval)d);
setTimeout(addFrame, %(fallback)d);
addEventListener('load', publish);
publish();
</script>
<img src="/hold?ms=%(hold)d" alt="">
"""
FRAME = """<!doctype html>
<meta charset="utf-8"><div class="ad_banner" id="thoron-ad" style="height:40px">ad</div>
"""


class TestServer:
    """Local HTTP server for the test page; records which ad requests actually arrive."""

    def __init__(self, work_dir: Path):
        self.ad_hits: list[int] = []
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
                url = urllib.parse.urlsplit(self.path)
                query = urllib.parse.parse_qs(url.query)
                if url.path == "/test.html":
                    page = PAGE % {"host": AD_HOST, "attempts": ATTEMPTS, "interval": INTERVAL_MS,
                                   "fallback": FRAME_FALLBACK_MS, "hold": HOLD_MS}
                    self._send(200, "text/html; charset=utf-8", page.encode())
                elif url.path == "/frame.html":
                    self._send(200, "text/html; charset=utf-8", FRAME.encode())
                elif url.path == "/pagead/js/adsbygoogle.js":
                    server.ad_hits.append(int(query.get("n", ["-1"])[0]))
                    self._send(200, "text/javascript", b"window.__thoronAd = 1;")
                elif url.path == "/hold":
                    time.sleep(min(int(query.get("ms", ["0"])[0]), 60000) / 1000)
                    self._send(200, "image/gif", GIF)
                else:
                    self._send(404, "text/plain", b"not found")

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    @property
    def ad_requests(self) -> int:
        return len(self.ad_hits)

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def browser_args(browser: Path, profile: Path, port: int, extension: Path | None, url: str) -> list[str]:
    # --disable-default-apps: Thorium's default apps install uBlock Origin from the Web Store into
    # every new profile, which would put a blocker into the control run.
    # Fully offline: only the ad host (mapped to the local server) and 127.0.0.1 resolve.
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update",
            f"--host-resolver-rules=MAP {AD_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]
    if extension is not None:
        args += [f"--load-extension={extension}", "--disable-features=DisableLoadExtensionCommandLineSwitch"]
    return args + ["--dump-dom", url]


def parse_result(dom: str) -> dict | None:
    m = RESULT_RE.search(dom or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def run_once(browser: Path, work_dir: Path, extension: Path | None, timeout_s: int = 120) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="profile-", dir=work_dir))
    try:
        with TestServer(work_dir) as server:
            args = browser_args(browser, profile, server.port, extension, f"http://127.0.0.1:{server.port}/test.html")
            try:
                proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=timeout_s)
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"timed out after {timeout_s} s", "ad_requests": server.ad_requests}
            page = parse_result(proc.stdout)
            hits = sorted(server.ad_hits)
            late = [n for n in hits if n >= ATTEMPTS - LATE_ATTEMPTS]
            result = {"ok": proc.returncode == 0 and page is not None, "exit_code": proc.returncode,
                      "ad_requests": len(hits), "ad_hits": hits, "late_ad_requests": len(late), "page": page}
            if not result["ok"]:
                result["error"] = "no result in the page" if page is None else f"exit code {proc.returncode}"
            return result
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _run_problems(name: str, run: dict) -> list[str]:
    """Why a run cannot be trusted (empty list: it measured what it should)."""
    if not run.get("ok"):
        return [f"{name} run failed: {run.get('error', 'unknown error')}"]
    page = run["page"]
    problems = []
    if page.get("attempts") != ATTEMPTS:
        problems.append(f"{name} run made {page.get('attempts')} of {ATTEMPTS} attempts")
    finished = sum(page.get(k, 0) for k in ("loaded", "stand_ins", "errors"))
    if finished != page.get("attempts"):
        problems.append(f"{name} run: only {finished} of {page.get('attempts')} attempts finished")
    if not page.get("frame"):
        problems.append(f"{name} run never checked the ad frame")
    return problems


def verdict(control: dict, with_extension: dict) -> tuple[str, list[str]]:
    problems = _run_problems("control", control) + _run_problems("extension", with_extension)
    if problems:
        return "invalid", problems
    if control["ad_requests"] == 0 or control["page"].get("ad_element_hidden"):
        return "invalid", ["the control run saw no ads, so the page tested nothing"]
    if control.get("late_ad_requests") != LATE_ATTEMPTS:
        return "invalid", [f"the control run's last {LATE_ATTEMPTS} ad requests did not all reach the server "
                           f"({control.get('late_ad_requests')}): something blocked them without the extension"]
    network = with_extension.get("late_ad_requests", with_extension["ad_requests"]) == 0
    cosmetic = bool(with_extension["page"].get("ad_element_hidden"))
    reasons = [f"network blocking: {'yes' if network else 'no'} (ad requests reaching the server: "
               f"{with_extension['ad_requests']} with the extension, {control['ad_requests']} without)",
               f"cosmetic filtering: {'yes' if cosmetic else 'no'}"]
    return ("works" if network and cosmetic else "partial" if network or cosmetic else "fails"), reasons


def run_both(browser: Path, extension: Path, work_dir: Path, timeout_s: int = 120) -> dict:
    control = run_once(browser, work_dir, None, timeout_s)
    with_ext = run_once(browser, work_dir, extension, timeout_s)
    result, reasons = verdict(control, with_ext)
    return {"verdict": result, "reasons": reasons, "control": control, "with_extension": with_ext}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--extension", required=True, type=Path, help="unpacked extension folder")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    a = parser.parse_args(argv)
    report = run_both(a.browser, a.extension.resolve(), a.work, a.timeout)
    print(json.dumps(report, indent=2))
    print(f"MV2 CHECK: {report['verdict'].upper()}")
    return 0 if report["verdict"] == "works" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
