#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Which outside hosts a fresh profile contacts on its own (ROADMAP S.10).

Starts the browser headless on a throwaway profile with a local page (127.0.0.1) and Chromium's network
log turned on, waits, stops it, and lists every host other than the local machine that appears in the
log with how often. Nothing is typed or clicked, so every host listed is contacted by the browser itself.
The log may be cut off when the browser is stopped; the parser does not need valid JSON.
    py -3 -I tools/qa/netlog_hosts.py --browser <out>\\thoron.exe --work J:\\thoron-build\\netlog --seconds 120
        --label "Thoron 158" --md docs/security/<name>.md
"""
import argparse
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa.bench import PingServer, _launch, _stop  # noqa: E402

_URL = re.compile(r'"(?:url|original_url|location)"\s*:\s*"(?:https?|wss?)://([^/:"?#]+)')
_HOST = re.compile(r'"host"\s*:\s*"([^"]+)"')
_PAIR = re.compile(r'"host_port_pair"\s*:\s*"([^":]+)')
_LOCAL = {"127.0.0.1", "localhost", "::1", "[::1]"}


def hosts(log_text: str) -> dict[str, int]:
    found = Counter()
    for rx in (_URL, _HOST, _PAIR):
        for h in rx.findall(log_text):
            h = re.sub(r"^[a-z][a-z0-9+.-]*://", "", h.lower()).split("/")[0]   # "https://host" -> "host"
            if h.count(":") == 1:
                h = h.split(":")[0]                                           # "host:443" -> "host"
            h = h.strip(".")
            if h and h not in _LOCAL and "." in h:
                found[h] += 1
    return dict(found)


def capture(browser: Path, work: Path, seconds: float) -> dict[str, int]:
    work.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="netlog-", dir=work))
    log = profile.parent / f"{profile.name}.json"
    with PingServer() as server:
        proc = _launch(browser, profile, [f"--log-net-log={log}", "--net-log-capture-mode=Default",
                                          server.url("page")])
        try:
            time.sleep(seconds)
        finally:
            _stop(proc, profile)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    log.unlink(missing_ok=True)
    if not text:
        raise RuntimeError("the browser wrote no network log")
    return hosts(text)


def to_markdown(found: dict[str, int], label: str, seconds: float) -> str:
    out = [f"# Hosts contacted by a fresh {label} profile", "",
           f"Measured with `tools/qa/netlog_hosts.py`: headless, throwaway profile, one local page, {seconds:g} s,"
           " no user action.", "", "| Host | Log entries |", "|---|---|"]
    out += [f"| {h} | {n} |" for h, n in sorted(found.items(), key=lambda kv: (-kv[1], kv[0]))]
    if not found:
        out.append("| (none) | 0 |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=120)
    p.add_argument("--label", default="browser")
    p.add_argument("--md", type=Path)
    a = p.parse_args(argv)
    try:
        found = capture(a.browser, a.work, a.seconds)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"netlog_hosts: {exc}", file=sys.stderr)
        return 1
    md = to_markdown(found, a.label, a.seconds)
    if a.md:
        a.md.parent.mkdir(parents=True, exist_ok=True)
        a.md.write_text(md, encoding="utf-8", newline="\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
