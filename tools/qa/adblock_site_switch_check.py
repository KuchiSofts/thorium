#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, per-site switch, checked offline (ROADMAP P5.16).

Thoron's native ad blocking uses Chromium's per-site "Ads" setting as its switch: page info and
Settings > Site settings show it, "Allow" turns blocking off on that site, and an "Allow" default turns
it off everywhere. The setting lives in the profile with the person's other site settings.

Each mode starts the browser headless on a throwaway profile (sandbox on, DevTools on 127.0.0.1 only)
with the ThoronNativeAdblock feature, makes the choice the way the Settings page does (its own
`chrome.send` handlers on chrome://settings), then opens the local ad test page of
`tools/build/mv2_check.py` (offline: only the ad host and 127.0.0.1 resolve):

    none        no choice made: every ad request is blocked
    site        ads allowed on 127.0.0.1: none is blocked
    everywhere  ads allowed by default: none is blocked
    restart     the "site" profile after a normal browser exit, with no new choice: the browser kept it,
                and still blocks nothing there

    py -3 -I tools/qa/adblock_site_switch_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode passes.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.build import mv2_check  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

SITE_PATTERN = "127.0.0.1"   # the test host on any port: the restart run gets a new server port
MODES = ("none", "site", "everywhere")
PAGE_TIMEOUT_S = 90


def settings_call(mode: str) -> str | None:
    """The Settings page's own handler call for a mode's choice (None: make no choice)."""
    if mode == "site":
        args = [SITE_PATTERN, "", "ads", "allow", False]
        return f"chrome.send('setCategoryPermissionForPattern', {json.dumps(args)})"
    if mode == "everywhere":
        return f"chrome.send('setDefaultValueForContentType', {json.dumps(['ads', 'allow'])})"
    if mode in ("none", "restart"):
        return None
    raise ValueError(mode)


def problems(mode: str, run: dict) -> list[str]:
    page = run.get("page") if isinstance(run, dict) else None
    if not run.get("ok") or not isinstance(page, dict):
        return [f"the run failed: {run.get('error', 'no page result')}"]
    attempts, loaded, errors = page.get("attempts", 0), page.get("loaded", 0), page.get("errors", 0)
    if mode == "none":
        return [f"{loaded} of {attempts} ad requests loaded with no choice made"] if loaded else []
    if mode in ("site", "everywhere", "restart"):
        if errors or loaded != attempts:
            return [f"ads were blocked though allowed: {errors} of {attempts} failed"]
        return []
    raise ValueError(mode)


def _launch(browser: Path, profile: Path, port: int) -> subprocess.Popen:
    # a port file left by the previous start of this profile would point at a closed port
    (profile / "DevToolsActivePort").unlink(missing_ok=True)
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", "--enable-features=ThoronNativeAdblock",
            f"--host-resolver-rules=MAP {mv2_check.AD_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _devtools_port(profile: Path) -> int:
    port_file = profile / "DevToolsActivePort"
    for _ in range(150):
        try:
            # the browser may still be writing it (Windows refuses the read then)
            lines = port_file.read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip().isdigit():
                return int(lines[0])
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("DevTools did not start")


def _open(port: int, url: str) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{urllib.parse.quote(url, safe=':/')}",
                                 method="PUT")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def _close_browser(port: int, proc: subprocess.Popen) -> None:
    """A normal exit, so the profile is saved as it is when a person closes the browser."""
    try:
        version = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=10).read())
        ws = WebSocket(version["webSocketDebuggerUrl"])
        try:
            ws.call("Browser.close")
        except (ConnectionError, OSError):
            pass
        finally:
            ws.close()
        proc.wait(timeout=30)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        proc.wait(timeout=20)
    time.sleep(2)


def run_mode(browser: Path, profile: Path, work: Path, mode: str) -> dict:
    with mv2_check.TestServer(work) as server:
        proc = _launch(browser, profile, server.port)
        port = None
        try:
            port = _devtools_port(profile)
            call = settings_call(mode)
            if call:
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    ws.call("Runtime.evaluate", expression=call)
                finally:
                    ws.close()
                time.sleep(1)
            _open(port, f"http://127.0.0.1:{server.port}/test.html")
            deadline = time.monotonic() + PAGE_TIMEOUT_S
            while time.monotonic() < deadline:
                r = server.posted
                if r and r.get("attempts") == mv2_check.ATTEMPTS and r.get("frame"):
                    time.sleep(2)
                    break
                time.sleep(0.5)
            page = server.posted
            ok = bool(page and page.get("attempts") == mv2_check.ATTEMPTS)
            return {"ok": ok, "page": page, "ad_requests": server.ad_requests,
                    **({} if ok else {"error": f"no final page result in {PAGE_TIMEOUT_S} s"})}
        except (OSError, RuntimeError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                proc.kill()
                proc.wait(timeout=20)


def run_all(browser: Path, work: Path) -> list[dict]:
    work.mkdir(parents=True, exist_ok=True)
    results = []
    for mode in MODES:
        profile = Path(tempfile.mkdtemp(prefix=f"switch-{mode}-", dir=work))
        try:
            run = run_mode(browser, profile, work, mode)
            results.append({"mode": mode, "problems": problems(mode, run), "page": run.get("page")})
            if mode == "site":
                run = run_mode(browser, profile, work, "restart")
                results.append({"mode": "restart", "problems": problems("restart", run), "page": run.get("page")})
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    for r in results:
        r["passed"] = not r["problems"]
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    a = parser.parse_args(argv)
    results = run_all(a.browser, a.work)
    print(json.dumps(results, indent=2))
    ok = all(r["passed"] for r in results)
    print("SITE SWITCH CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
