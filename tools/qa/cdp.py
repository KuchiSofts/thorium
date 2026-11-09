#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Minimal DevTools client for checking WebUI pages in a test build (ROADMAP P2.23).

Starts the browser headless on a throwaway profile with DevTools on 127.0.0.1 (random port), opens a
chrome:// page in a new tab and returns its text (shadow DOM included) and a PNG screenshot. Standard
library only: a small WebSocket client is enough for request/response DevTools calls.
    py -3 -I tools/qa/cdp.py --browser <out>\\thoron.exe --work <scratch> --page chrome://settings/help
        --png about.png [--text about.txt]
"""
import argparse
import base64
import json
import os
import socket
import struct
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa.bench import _launch, _stop  # noqa: E402

# Text of the page, walking open shadow roots (settings pages are web components).
TEXT_JS = """(() => { const out = []; const walk = (n) => {
  if (n.nodeType === 3) { const t = n.textContent.trim(); if (t) out.push(t); return; }
  if (n.shadowRoot) walk(n.shadowRoot);
  for (const c of n.childNodes) walk(c);
}; walk(document.body); return out.join('\\n'); })()"""


class WebSocket:
    def __init__(self, url: str, timeout: float = 30):
        u = urlparse(url)
        if u.hostname != "127.0.0.1":
            raise ValueError("only local DevTools endpoints are allowed")
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(head.split(b"\r\n", 1)[0].decode(errors="replace"))
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self.next_id = 0

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text: str) -> None:
        data, mask = text.encode(), os.urandom(4)
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else
                                bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else
                                bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self) -> str:
        parts = []
        while True:
            b0, b1 = self._recv_exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            payload = self._recv_exact(n)
            if b0 & 0x0F in (0x1, 0x0):
                parts.append(payload)
                if b0 & 0x80:
                    return b"".join(parts).decode("utf-8", "replace")

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        self.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.recv())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def close(self) -> None:
        self.sock.close()


def inspect(browser: Path, work: Path, page: str, settle: float = 4, width: int = 1280, height: int = 1600) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="cdp-", dir=work))
    proc = _launch(browser, profile, ["about:blank", f"--window-size={width},{height}"], devtools=True)
    try:
        port_file = profile / "DevToolsActivePort"
        for _ in range(150):
            if port_file.is_file():
                break
            time.sleep(0.2)
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{page}", method="PUT")
        target = json.loads(urllib.request.urlopen(req, timeout=10).read())
        time.sleep(settle)
        ws = WebSocket(target["webSocketDebuggerUrl"])
        try:
            text = ws.call("Runtime.evaluate", expression=TEXT_JS, returnByValue=True)["result"].get("value", "")
            shot = base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
        finally:
            ws.close()
        return {"text": text, "png": shot}
    finally:
        _stop(proc, profile)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--page", required=True)
    p.add_argument("--png", type=Path, required=True)
    p.add_argument("--text", type=Path)
    a = p.parse_args(argv)
    if not a.page.startswith(("chrome://", "about:")):
        print("cdp: only chrome:// and about: pages are checked", file=sys.stderr)
        return 2
    result = inspect(a.browser, a.work, a.page)
    a.png.write_bytes(result["png"])
    if a.text:
        a.text.write_text(result["text"], encoding="utf-8")
    print(result["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
