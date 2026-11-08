# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Stand-in browser for smoke-test unit tests. Behaviour is chosen with FAKE_MODE:
ok | crash | exit1 | missing | nosandbox. Writes its argv and the profile's initial contents to
FAKE_ARGV_LOG (JSON lines) when set."""
import json
import os
import sys

argv = sys.argv[1:]
profile = next((a.split("=", 1)[1] for a in argv if a.startswith("--user-data-dir=")), None)
if os.environ.get("FAKE_ARGV_LOG"):
    with open(os.environ["FAKE_ARGV_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": argv, "profile": profile,
                            "profile_initial": sorted(os.listdir(profile)) if profile and os.path.isdir(profile) else None}) + "\n")
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "nosandbox" and "--no-sandbox" in argv:
    sys.exit(2)
if mode == "exit1":
    sys.exit(1)
results = {"js": True, "webgl": True, "h264": True, "hevc": True, "av1": True, "jxl": True, "ua": "Fake/1.0"}
if mode == "missing":
    results.pop("jxl")
if mode == "empty":                     # the page script never ran: the DOM keeps its initial {}
    results = {}
if mode == "null":
    results = None
if mode == "list":
    results = []
if mode == "crash" and profile:
    reports = os.path.join(profile, "Crashpad", "reports")
    os.makedirs(reports, exist_ok=True)
    open(os.path.join(reports, "x.dmp"), "wb").close()
print("<html><body><pre id=\"result\">" + json.dumps(results).replace("&", "&amp;").replace("<", "&lt;") + "</pre></body></html>")
