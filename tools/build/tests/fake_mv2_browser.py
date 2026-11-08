# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Stand-in browser for mv2_check tests.

It reads the same switches a real browser gets and the attempt count from the test page. Without
--load-extension it behaves like a browser with no blocker: every ad request reaches the server and
the ad element stays visible. With --load-extension it behaves like a working blocker. A file named
BROKEN in the extension folder makes it behave as if the extension never ran; a file named SLOW
lets the first half of the attempts through, like a blocker that is still starting.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

args = sys.argv[1:]
if "--no-sandbox" in args:
    sys.exit(3)
rules = next(a for a in args if a.startswith("--host-resolver-rules="))
port = int(re.search(r"127\.0\.0\.1:(\d+)", rules).group(1))
page = urllib.request.urlopen(args[-1]).read().decode()
attempts = int(re.search(r"const ATTEMPTS = (\d+);", page).group(1))
ext = next((Path(a.split("=", 1)[1]) for a in args if a.startswith("--load-extension=")), None)
blocking = ext is not None and not (ext / "BROKEN").exists()
slow = blocking and (ext / "SLOW").exists()
loaded = 0
for n in range(attempts):
    if not blocking or (slow and n < attempts // 2):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/pagead/js/adsbygoogle.js?n={n}").read()
        loaded += 1
result = {"attempts": attempts, "loaded": loaded, "stand_ins": 0, "errors": attempts - loaded,
          "frame": True, "ad_element_hidden": blocking}
print(f'<html><body><pre id="thoron-mv2-result">{json.dumps(result)}</pre></body></html>')
