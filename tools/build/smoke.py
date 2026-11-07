#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Smoke-test a freshly built browser: fresh throwaway profile, sandbox always on, local page only.

Fails on a non-zero exit, any crash dump, a missing smoke result, or any required capability
(JS, WebGL, H.264, HEVC, AV1, JPEG XL) reported false.
    py -3 -I tools/build/smoke.py --browser out\\thoron\\chrome.exe --work J:\\thoron-build\\smoke\\win
        --jxl-sample <chromium src>\\third_party\\libjxl\\src\\testdata\\...\\<small>.jxl
"""
import argparse
import base64
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = {"js": True, "webgl": True, "h264": True, "hevc": True, "av1": True, "jxl": True}
PAGE_TEMPLATE = Path(__file__).with_name("smoke_page.html")
RESULT_RE = re.compile(r'<pre id="result">(.*?)</pre>', re.S)
CRASH_DIRS = (("Crashpad", "reports"), ("Crash Reports",))  # Windows, Linux


def _render_page(work_dir: Path, jxl_sample: Path | None) -> Path:
    sample = base64.b64encode(jxl_sample.read_bytes()).decode("ascii") if jxl_sample else ""
    page = work_dir / "smoke_page.html"
    page.write_text(PAGE_TEMPLATE.read_text(encoding="utf-8").replace("__JXL_BASE64__", sample), encoding="utf-8")
    return page


def _crash_dumps(profile: Path) -> list[str]:
    dumps = []
    for parts in CRASH_DIRS:
        folder = profile.joinpath(*parts)
        if folder.is_dir():
            dumps += sorted(p.name for p in folder.rglob("*") if p.is_file())
    return dumps


def run_smoke(browser: Path, work_dir: Path, timeout_s: int = 90, jxl_sample: Path | None = None) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="profile-", dir=work_dir))  # fresh and empty every run
    page = _render_page(work_dir, jxl_sample)
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--dump-dom", page.resolve().as_uri()]
    failures, results = [], {}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout_s)
        exit_code, output = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        exit_code, output = None, ""
        failures.append(f"timed out after {timeout_s} s")
    if exit_code not in (0, None):
        failures.append(f"exit code {exit_code}")
    match = RESULT_RE.search(output)
    if match:
        try:
            results = json.loads(html.unescape(match.group(1)))
        except ValueError:
            failures.append("smoke result is not valid JSON")
    else:
        failures.append("no smoke result in browser output")
    for key, wanted in REQUIRED.items():
        if results and results.get(key) is not wanted:
            failures.append(f"capability {key} is {results.get(key)!r}, expected {wanted}")
    dumps = _crash_dumps(profile)
    if dumps:
        failures.append(f"crash dump(s) written: {', '.join(dumps)}")
    return {"exit_code": exit_code, "results": results, "crash_dumps": dumps,
            "passed": not failures, "failures": failures}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--jxl-sample", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    a = parser.parse_args(argv)
    result = run_smoke(a.browser, a.work, a.timeout, a.jxl_sample)
    print(json.dumps(result, indent=2))
    print("SMOKE: PASSED" if result["passed"] else "SMOKE: FAILED")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
