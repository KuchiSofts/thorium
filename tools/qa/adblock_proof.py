#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, proof measurements (ROADMAP P5.17; design section 9), the offline part.

Loads three ad-heavy local test pages (news, recipe and blog page structures) in four configurations,
each on fresh throwaway profiles with the sandbox on:

    control     no blocker
    ubo         uBlock Origin alone (an unpacked copy, --extension), its bundled lists
    native      Thoron's native engine alone (the ThoronNativeAdblock feature)
    native+ubo  both, as Thoron would ship them

The pages ask for scripts, images, frames and beacons on real ad and tracker host names, and for a few
third-party resources a page needs to work (libraries, fonts, thumbnails). Fully offline: Chrome's
host-resolver rules send those host names to a local server on 127.0.0.1 and make every other name
fail. Some ad scripts ask for more ads once they run, as real ones do. Every answer for a mapped host
is held back --remote-delay ms to stand in for a network round trip (local answers are instant), so
the load times show the shape of the gain, not what a person sees on a real connection.

Measured per configuration: ad and tracker requests that reached the server, needed resources that
did not, blocked scripts that were answered with a harmless stand-in (the page sees them load, the
server never sees them), page load time (navigation start to the load event; median of --runs loads per page, taken
page after page in turn after --warm unmeasured rounds, and summed over the pages), CPU time of the
whole browser per page load, and private memory with 1 and 20 tabs.
`native` and `native+ubo` are then compared with `ubo` against the design's targets. The breakage
target on real sites is not covered here.
    py -3 -I tools/qa/adblock_proof.py --browser <out>\\thoron.exe --extension <unpacked uBO>
        --work J:\\thoron-build\\proof --out docs/perf/<name>.json --md docs/perf/<name>.md
Exit status 0 when every configuration ran and gave valid numbers (whether or not the targets are met).
"""
import argparse
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
from tools.build.mv2_check import GIF  # noqa: E402
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _devtools_port, _open  # noqa: E402

MODES = ("control", "ubo", "native", "native+ubo")
READY_TIMEOUT_S = 120
LOAD_TIMEOUT_S = 60
LOAD_TARGET = 0.90   # at least 10 % faster than uBlock Origin alone


def _r(rid, group, kind, host, path, **more):
    return {"id": rid, "group": group, "kind": kind, "host": host, "path": path, **more}


# Host names on Chromium's HSTS preload list cannot be used: the browser turns their http:// requests into
# https://, which the plain local server cannot answer. The control run proves every request arrives.
RESOURCES = [
    # ads
    _r("adsbygoogle", "ad", "script", "pagead2.googlesyndication.com", "/pagead/js/adsbygoogle.js",
       children=["gads-frame", "simgad"]),
    _r("gpt", "ad", "script", "securepubads.g.doubleclick.net", "/tag/js/gpt.js", children=["dc-pixel", "dc-frame"]),
    _r("apstag", "ad", "script", "c.amazon-adsystem.com", "/aax2/apstag.js"),
    _r("criteo", "ad", "script", "static.criteo.net", "/js/ld/publishertag.js", children=["criteo-bid"]),
    _r("taboola", "ad", "script", "cdn.taboola.com", "/libtrc/site/loader.js", sync=True),
    _r("outbrain", "ad", "script", "widgets.outbrain.com", "/outbrain.js"),
    _r("adnxs", "ad", "iframe", "ib.adnxs.com", "/ttj?id=1"),
    _r("gads-frame", "ad", "iframe", "googleads.g.doubleclick.net", "/pagead/ads?client=ca-pub-1"),
    _r("dc-frame", "ad", "iframe", "ad.doubleclick.net", "/ddm/adi/x"),
    _r("dc-pixel", "ad", "img", "ad.doubleclick.net", "/ddm/ad/x.gif"),
    _r("simgad", "ad", "img", "tpc.googlesyndication.com", "/simgad/123"),
    _r("criteo-bid", "ad", "xhr", "bidder.criteo.com", "/cdb?ptv=1"),
    # trackers
    _r("gtm", "tracker", "script", "www.googletagmanager.com", "/gtm.js?id=GTM-X", children=["quant", "quant-pixel"]),
    _r("quant", "tracker", "script", "secure.quantserve.com", "/quant.js"),
    _r("quant-pixel", "tracker", "img", "pixel.quantserve.com", "/pixel"),
    _r("linkedin", "tracker", "script", "snap.licdn.com", "/li.lms-analytics/insight.min.js",
       children=["li-collect"]),
    _r("li-collect", "tracker", "img", "px.ads.linkedin.com", "/collect?pid=1"),
    _r("scorecard", "tracker", "script", "sb.scorecardresearch.com", "/beacon.js", sync=True),
    _r("chartbeat", "tracker", "script", "static.chartbeat.com", "/js/chartbeat.js"),
    _r("hotjar", "tracker", "script", "static.hotjar.com", "/c/hotjar-1.js"),
    _r("clarity", "tracker", "script", "www.clarity.ms", "/tag/abc"),
    _r("tiktok", "tracker", "script", "analytics.tiktok.com", "/i18n/pixel/events.js"),
    _r("segment", "tracker", "script", "cdn.segment.com", "/analytics.js/v1/x/analytics.min.js"),
    _r("yahoo", "tracker", "xhr", "sp.analytics.yahoo.com", "/spp.pl?a=1"),
    # third-party resources the page needs: blocking one is breakage
    _r("jsdelivr", "needed", "script", "cdn.jsdelivr.net", "/npm/lib@1/lib.min.js", sync=True),
    _r("jqueryui", "needed", "script", "code.jquery.com", "/ui/1.13.2/jquery-ui.min.js"),
    _r("jquery", "needed", "script", "ajax.googleapis.com", "/ajax/libs/jquery/3.7.1/jquery.min.js", sync=True),
    _r("fonts", "needed", "css", "fonts.googleapis.com", "/css?family=Roboto"),
    _r("ytimg", "needed", "img", "i.ytimg.com", "/vi/abc/hqdefault.jpg"),
    _r("bootstrap", "needed", "script", "stackpath.bootstrapcdn.com", "/bootstrap/4.5.2/js/bootstrap.min.js"),
]
BY_ID = {r["id"]: r for r in RESOURCES}
BY_REQUEST = {(r["host"], r["path"].split("?")[0]): r for r in RESOURCES}
PAGES = {
    "news": ["jquery", "fonts", "jsdelivr", "ytimg", "taboola", "scorecard", "gpt", "adsbygoogle", "apstag",
             "criteo", "outbrain", "adnxs", "gtm", "linkedin", "chartbeat", "clarity", "yahoo"],
    "recipe": ["jquery", "fonts", "jqueryui", "ytimg", "adsbygoogle", "gpt", "criteo", "taboola", "gtm", "linkedin",
               "hotjar", "tiktok", "segment"],
    "blog": ["fonts", "bootstrap", "jsdelivr", "adsbygoogle", "gtm", "linkedin", "segment", "hotjar"],
}
FIRST_PARTY_IMAGES = 6


def expected(page: str) -> list[str]:
    """Every resource a page can ask for with no blocker: its own and the ones its scripts add."""
    out, todo = [], list(PAGES[page])
    while todo:
        rid = todo.pop(0)
        if rid not in out:
            out.append(rid)
            todo += BY_ID[rid].get("children", [])
    return out


def url(rid: str, run: str) -> str:
    r = BY_ID[rid]
    return f"http://{r['host']}{r['path']}{'&' if '?' in r['path'] else '?'}r={run}"


def _tag(rid: str, run: str) -> str:
    r, u = BY_ID[rid], url(rid, run)
    if r["kind"] == "script":   # the page notes whether it loaded or failed (stand_ins())
        return (f'<script src="{u}"{"" if r.get("sync") else " async"} onload="__ok(\'{rid}\')" '
                f'onerror="__er(\'{rid}\')"></script>')
    if r["kind"] == "css":
        return f'<link rel="stylesheet" href="{u}">'
    if r["kind"] == "img":
        return f'<img src="{u}" alt="" width="1" height="1">'
    if r["kind"] == "iframe":
        return f'<iframe src="{u}" width="300" height="250"></iframe>'
    return f"<script>fetch({json.dumps(u)}, {{mode: 'no-cors'}}).catch(() => {{}});</script>"


def page_html(page: str, run: str, port: int) -> str:
    own = PAGES[page]
    head = "".join(_tag(i, run) for i in own if BY_ID[i]["kind"] == "css" or BY_ID[i].get("sync"))
    body = "".join(_tag(i, run) for i in own if BY_ID[i]["kind"] != "css" and not BY_ID[i].get("sync"))
    text = "".join(f"<p>Paragraph {n} of the {page} page, with enough words to lay out as text.</p>"
                   f'<img src="/static/photo{n}.gif?r={run}" alt="" width="320" height="180">'
                   for n in range(FIRST_PARTY_IMAGES))
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{page}</title>'
            "<script>window.__okl = []; window.__erl = []; window.__real = [];"
            "window.__ok = (i) => __okl.push(i); window.__er = (i) => __erl.push(i);</script>"
            f'<link rel="stylesheet" href="/static/site.css?r={run}">{head}'
            f'<script src="/static/app.js?r={run}"></script></head><body><h1>{page}</h1>{text}{body}'
            "<script>addEventListener('load', () => setTimeout(() => {"
            "const n = performance.getEntriesByType('navigation')[0];"
            f"fetch('/result', {{method: 'POST', keepalive: true, body: JSON.stringify({{run: {json.dumps(run)}, "
            "load: n.loadEventStart, dcl: n.domContentLoadedEventStart, "
            "ok: window.__okl, er: window.__erl, real: window.__real})});}, 0));</script></body></html>")


# The readiness page: asks for one ad script again and again until it stays blocked.
PROBE = """<!doctype html><meta charset="utf-8"><title>probe</title><script>
let n = 0, blocked = 0;
const timer = setInterval(() => {
  window.__ad = 0;
  const s = document.createElement('script');
  s.src = 'http://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?r=probe&n=' + n++;
  const done = (ad) => {
    blocked = ad ? 0 : blocked + 1;
    if (blocked === 3) { clearInterval(timer); fetch('/ready', {method: 'POST', body: String(n)}); }
  };
  s.onload = () => done(window.__ad === 1);
  s.onerror = () => done(false);
  document.head.appendChild(s);
}, 700);
</script>"""
# The same for uBlock Origin. With the native engine also on, a blocked script proves nothing about the
# extension, so this asks for a WebSocket on an ad host: the native engine does not check those, uBlock Origin
# does. The page cannot tell a blocked socket from a refused one; the server knows which ones arrived.
PROBE_WS = """<!doctype html><meta charset="utf-8"><title>probe</title><script>
let n = 0;
setInterval(() => {
  const k = n++;
  try { new WebSocket('ws://pagead2.googlesyndication.com/ws?n=' + k).onerror = () => {}; } catch (e) {}
  setTimeout(() => fetch('/tick?n=' + k, {method: 'POST'}), 500);
}, 700);
</script>"""


def resolver_rules(port: int) -> str:
    hosts = sorted({r["host"] for r in RESOURCES})
    return ", ".join([f"MAP {h} 127.0.0.1:{port}" for h in hosts] + ["MAP * ~NOTFOUND", "EXCLUDE 127.0.0.1"])


class ProofServer:
    """The local web: the test pages on 127.0.0.1 and every mapped ad, tracker and library host."""

    def __init__(self, remote_delay_ms: int = 40):
        self.hits: dict[str, set[str]] = {}
        self.results: dict[str, dict] = {}
        self.ready = threading.Event()
        self._ws_seen: set[str] = set()
        self._ws_blocked = 0
        lock, server, delay = threading.Lock(), self, remote_delay_ms / 1000

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

            def _local(self) -> bool:
                return (self.headers.get("Host") or "").split(":")[0] == "127.0.0.1"

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                path = self.path.split("?")[0]
                if not self._local() or length > 65536 or path not in ("/result", "/ready", "/tick"):
                    self._send(404, "text/plain", b"refused")
                    return
                body = self.rfile.read(length)
                if path == "/ready":
                    server.ready.set()
                elif path == "/tick":   # one WebSocket attempt of the uBlock Origin probe is over
                    with lock:
                        arrived = self.path.split("n=")[-1] in server._ws_seen
                        server._ws_blocked = 0 if arrived else server._ws_blocked + 1
                        if server._ws_blocked >= 3:
                            server.ready.set()
                else:
                    try:
                        data = json.loads(body.decode("utf-8"))
                        with lock:
                            server.results[str(data["run"])] = data
                    except (ValueError, UnicodeError, KeyError, TypeError):
                        self._send(400, "text/plain", b"bad result")
                        return
                self._send(200, "text/plain", b"ok")

            def do_GET(self):
                u = urllib.parse.urlsplit(self.path)
                run = (urllib.parse.parse_qs(u.query).get("r") or [""])[0]
                if self._local():
                    if u.path.startswith("/page/") and u.path[6:] in PAGES:
                        self._send(200, "text/html; charset=utf-8", page_html(u.path[6:], run, server.port).encode())
                    elif u.path == "/probe.html":
                        self._send(200, "text/html; charset=utf-8", PROBE.encode())
                    elif u.path == "/probe-ws.html":
                        self._send(200, "text/html; charset=utf-8", PROBE_WS.encode())
                    elif u.path == "/static/site.css":
                        self._send(200, "text/css", b"body{font:16px sans-serif;max-width:60em}img{display:block}")
                    elif u.path == "/static/app.js":
                        self._send(200, "text/javascript", b"window.__app = 1;")
                    elif u.path.startswith("/static/photo"):
                        self._send(200, "image/gif", GIF)
                    else:
                        self._send(404, "text/plain", b"not found")
                    return
                if u.path == "/ws":   # the uBlock Origin probe's socket got through
                    with lock:
                        server._ws_seen.add((urllib.parse.parse_qs(u.query).get("n") or [""])[0])
                    self._send(404, "text/plain", b"no socket here")
                    return
                r = BY_REQUEST.get(((self.headers.get("Host") or "").split(":")[0], u.path))
                if r is None:
                    self._send(404, "text/plain", b"not found")
                    return
                if run != "probe":
                    with lock:
                        server.hits.setdefault(run, set()).add(r["id"])
                if delay:
                    time.sleep(delay)
                if r["kind"] == "script":
                    js = f"(window.__real = window.__real || []).push({json.dumps(r['id'])});window.__ad = 1;"
                    for child in r.get("children", []):
                        c, cu = BY_ID[child], json.dumps(url(child, run))
                        if c["kind"] == "img":
                            js += f"new Image().src = {cu};"
                        elif c["kind"] == "xhr":
                            js += f"fetch({cu}, {{mode: 'no-cors'}}).catch(() => {{}});"
                        else:
                            tag = "iframe" if c["kind"] == "iframe" else "script"
                            js += (f"(() => {{ const e = document.createElement('{tag}'); e.src = {cu}; "
                                   "(document.body || document.head).appendChild(e); })();")
                    self._send(200, "text/javascript", js.encode())
                elif r["kind"] == "css":
                    self._send(200, "text/css", b"h1{font-weight:500}")
                elif r["kind"] == "img":
                    self._send(200, "image/gif", GIF)
                elif r["kind"] == "iframe":
                    self._send(200, "text/html; charset=utf-8", b"<!doctype html><title>ad</title><p>ad</p>")
                else:
                    self._send(200, "text/plain", b"ok")

        class Quiet(http.server.ThreadingHTTPServer):
            def handle_error(self, request, client_address):   # a tab closed mid-request
                pass

        self._httpd = Quiet(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def count(page: str, hits: set[str]) -> dict:
    want = expected(page)
    ads = [i for i in want if BY_ID[i]["group"] != "needed"]
    return {"possible": len(ads), "reached": sum(1 for i in ads if i in hits),
            "reached_ids": sorted(i for i in ads if i in hits),
            "needed_missing": sorted(i for i in want if BY_ID[i]["group"] == "needed" and i not in hits)}


def stand_ins(result: dict, hits: set[str]) -> list[str]:
    """The scripts of one page load that a blocker answered with a harmless stand-in: the page saw them
    load, but they never reached the server and did not run the real script."""
    real = set(result.get("real") or [])
    return sorted(i for i in set(result.get("ok") or [])
                  if i not in real and i not in hits and BY_ID.get(i, {}).get("kind") == "script")


def _launch(browser: Path, profile: Path, port: int, mode: str, extension: Path | None) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--host-resolver-rules={resolver_rules(port)}",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
    if "ubo" in mode:
        args += [f"--load-extension={extension}", "--disable-features=DisableLoadExtensionCommandLineSwitch"]
    if "native" in mode:
        args.append("--enable-features=ThoronNativeAdblock")
    return subprocess.Popen(args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _close_tab(port: int, target: dict) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/close/{target['id']}", timeout=10).read()
    except OSError:
        pass


def quiet(samples: list[float], window: int = 3, limit_s: float = 0.15) -> bool:
    """True when the last `window` steps of total CPU time each grew by less than `limit_s`."""
    steps = [b - a for a, b in zip(samples, samples[1:])]
    return len(steps) >= window and all(d < limit_s for d in steps[-window:])


def _settle(proc: subprocess.Popen, timeout_s: float = 90) -> None:
    """Wait until the browser has finished its start-up work (a new profile, an extension building its
    filters), so that work is not counted as page load."""
    samples, deadline = [], time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        samples.append(bench.total(bench._processes(), proc.pid, "cpu"))
        if quiet(samples):
            return
        time.sleep(2)
    raise bench.BenchError(f"the browser was still busy {timeout_s} s after its start")


def _start(browser: Path, work: Path, server: ProofServer, mode: str, extension: Path | None):
    """A browser in `mode` on a new profile, with its blocker (if any) proven to block."""
    profile = Path(tempfile.mkdtemp(prefix="proof-", dir=work))
    proc = _launch(browser, profile, server.port, mode, extension)
    try:
        port = _devtools_port(profile)
        if mode != "control":
            server.ready.clear()
            server._ws_blocked = 0
            probe = _open(port, f"http://127.0.0.1:{server.port}/probe{'-ws' if 'ubo' in mode else ''}.html")
            if not server.ready.wait(READY_TIMEOUT_S):
                raise bench.BenchError(f"{mode}: the blocker did not start blocking within {READY_TIMEOUT_S} s")
            _close_tab(port, probe)
        _settle(proc)
        return proc, profile, port
    except Exception:
        bench._stop(proc, profile)
        raise


def _load(server: ProofServer, port: int, page: str, run: str, keep: bool = False) -> float:
    target = _open(port, f"http://127.0.0.1:{server.port}/page/{page}?r={run}")
    deadline = time.monotonic() + LOAD_TIMEOUT_S
    while run not in server.results:
        if time.monotonic() > deadline:
            raise bench.BenchError(f"{run}: the page did not finish loading in {LOAD_TIMEOUT_S} s")
        time.sleep(0.05)
    time.sleep(0.6)   # beacons sent after the load event
    if not keep:
        _close_tab(port, target)
    return float(server.results[run]["load"])


def measure_mode(browser: Path, work: Path, mode: str, extension: Path | None, runs: int, memory_runs: int,
                 remote_delay_ms: int, warm: int = 3) -> dict:
    out = {"valid": False, "pages": {}}
    name, mode = mode, mode.replace("+", "-")   # run ids go into URLs, where a plus means a space
    with ProofServer(remote_delay_ms) as server:
        proc, profile, port = _start(browser, work, server, name, extension)
        try:
            for w in range(warm):   # unmeasured rounds first: caches and the blocker's own warm-up
                for page in PAGES:
                    _load(server, port, page, f"{mode}-{page}-warm{w}")
            _settle(proc)
            before = bench.total(bench._processes(), proc.pid, "cpu")
            loads = {page: [] for page in PAGES}
            for i in range(runs):   # page after page in turn, so a slow moment does not fall on one page only
                for page in PAGES:
                    loads[page].append(_load(server, port, page, f"{mode}-{page}-{i}"))
            after = bench.total(bench._processes(), proc.pid, "cpu")
        finally:
            bench._stop(proc, profile)
        for page in PAGES:
            per_run = [server.hits.get(f"{mode}-{page}-{i}", set()) for i in range(runs)]
            hits = set().union(*per_run)
            stood_in = set().union(*(stand_ins(server.results.get(f"{mode}-{page}-{i}", {}), per_run[i])
                                     for i in range(runs)))
            out["pages"][page] = {**count(page, hits), "stand_ins": sorted(stood_in),
                                  "load_ms": bench.summarise(loads[page])}
        memory = {1: [], 20: []}
        for n in range(memory_runs):
            proc, profile, port = _start(browser, work, server, name, extension)
            try:
                names = list(PAGES)
                _load(server, port, names[0], f"{mode}-mem{n}-0", keep=True)
                time.sleep(15)
                memory[1].append(bench.total(bench._processes(), proc.pid, "ws") / 2**20)
                for t in range(1, 20):
                    _load(server, port, names[t % len(names)], f"{mode}-mem{n}-{t}", keep=True)
                time.sleep(20)
                memory[20].append(bench.total(bench._processes(), proc.pid, "ws") / 2**20)
            finally:
                bench._stop(proc, profile)
    pages = out["pages"].values()
    out.update({
        "possible": sum(p["possible"] for p in pages), "reached": sum(p["reached"] for p in pages),
        "needed_missing": sum(len(p["needed_missing"]) for p in pages),
        "stand_ins": sum(len(p["stand_ins"]) for p in pages),
        "load_ms": round(sum(p["load_ms"]["median"] for p in pages), 1),
        "load_spread_pct": max(p["load_ms"]["spread_pct"] for p in pages),
        "cpu_s_per_load": round((after - before) / (runs * len(PAGES)), 3),
        "memory_mb_1": bench.summarise(memory[1])["median"], "memory_mb_20": bench.summarise(memory[20])["median"],
        "memory_values": {str(k): [round(v, 1) for v in vals] for k, vals in memory.items()},
    })
    out["valid"] = True
    if name == "control" and (out["reached"] != out["possible"] or out["needed_missing"]):
        missing = sorted(i for p in PAGES for i in expected(p) if i not in server.hits.get(f"{mode}-{p}-0", set()))
        out.update(valid=False, error=f"without a blocker these requests did not arrive: {', '.join(missing)}")
    return out


def verdict(candidate: dict, ubo: dict) -> list[dict]:
    """The design's targets (section 9) for one configuration, compared with uBlock Origin alone."""
    ok = bool(candidate.get("valid") and ubo.get("valid"))

    def row(target, rule, a, b, met):
        return {"target": target, "rule": rule, "value": a, "ubo": b, "met": bool(ok and met)}
    c, u = candidate, ubo
    return [
        row("blocking", "no more ad and tracker requests get through", c["reached"], u["reached"],
            c["reached"] <= u["reached"]),
        row("load time", "at least 10 % faster", c["load_ms"], u["load_ms"], c["load_ms"] <= u["load_ms"] * LOAD_TARGET),
        row("cpu", "lower", c["cpu_s_per_load"], u["cpu_s_per_load"], c["cpu_s_per_load"] < u["cpu_s_per_load"]),
        row("memory, 1 tab", "not more", c["memory_mb_1"], u["memory_mb_1"], c["memory_mb_1"] <= u["memory_mb_1"]),
        row("memory, 20 tabs", "not more", c["memory_mb_20"], u["memory_mb_20"],
            c["memory_mb_20"] <= u["memory_mb_20"]),
        row("breakage (test pages)", "no needed resource newly blocked", c["needed_missing"], u["needed_missing"],
            c["needed_missing"] <= u["needed_missing"]),
        row("stand-ins", "no fewer blocked scripts answered with a harmless stand-in", c.get("stand_ins", 0),
            u.get("stand_ins", 0), c.get("stand_ins", 0) >= u.get("stand_ins", 0)),
    ]


def to_markdown(results: dict) -> str:
    lines = [f"# Native ad blocking: proof measurements ({results.get('browser_version', 'unknown version')})", "",
             "Generated by `tools/qa/adblock_proof.py`: three ad-heavy local test pages, fully offline, throwaway",
             f"profiles. Load time is the median of {results['runs']} loads per page, summed over the pages; every",
             f"answer from a mapped host is held back {results['remote_delay_ms']} ms to stand in for the network.", "",
             "| Configuration | Ads and trackers through | Needed resources blocked | Stand-ins served |"
             " Load, ms (worst spread) | CPU, s per load | Memory 1 tab, MB | Memory 20 tabs, MB |",
             "|---|---|---|---|---|---|---|---|"]
    for name, m in results["modes"].items():
        if not m.get("valid"):
            lines.append(f"| {name} | invalid: {m.get('error', 'no result')} | | | | | | |")
            continue
        lines.append(f"| {name} | {m['reached']} of {m['possible']} | {m['needed_missing']} | "
                     f"{m.get('stand_ins', 0)} | {m['load_ms']} "
                     f"({m['load_spread_pct']} %) | {m['cpu_s_per_load']} | {m['memory_mb_1']} | {m['memory_mb_20']} |")
    for name, rows in results["verdicts"].items():
        lines += ["", f"## {name} against uBlock Origin alone", "", "| Target | Rule | Value | uBlock Origin | Met |",
                  "|---|---|---|---|---|"]
        lines += [f"| {t['target']} | {t['rule']} | {t['value']} | {t['ubo']} | {'yes' if t['met'] else 'no'} |"
                  for t in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--extension", required=True, type=Path, help="unpacked uBlock Origin")
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    parser.add_argument("--runs", type=int, default=15)
    parser.add_argument("--warm", type=int, default=3, help="unmeasured rounds of all pages before the measured ones")
    parser.add_argument("--memory-runs", type=int, default=3)
    parser.add_argument("--remote-delay", type=int, default=40, help="ms added to every mapped host's answer")
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--md", type=Path)
    a = parser.parse_args(argv)
    a.work.mkdir(parents=True, exist_ok=True)
    modes = {}
    for mode in [m for m in MODES if m in a.modes.split(",")]:
        try:
            modes[mode] = measure_mode(a.browser, a.work, mode, a.extension, a.runs, a.memory_runs, a.remote_delay,
                                       a.warm)
        except (bench.BenchError, OSError, RuntimeError, ValueError) as e:
            modes[mode] = {"valid": False, "error": str(e)}
        print(mode, json.dumps({k: v for k, v in modes[mode].items() if k != "pages"}), flush=True)
    version = ""
    try:
        version = subprocess.run([str(a.browser), "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if "control" in modes and not modes["control"].get("valid"):   # the test pages themselves are not trustworthy
        for m in modes.values():
            m.setdefault("error", "the control run is invalid")
            m["valid"] = False
    ubo = modes.get("ubo", {"valid": False})
    results = {"browser_version": version, "runs": a.runs, "warm_rounds": a.warm,
               "remote_delay_ms": a.remote_delay, "modes": modes,
               "verdicts": {k: verdict(modes[k], ubo) for k in ("native", "native+ubo")
                            if modes.get(k, {}).get("valid") and ubo.get("valid")}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    if a.md:
        a.md.write_text(to_markdown(results), encoding="utf-8", newline="\n")
    ok = all(m.get("valid") for m in modes.values())
    print("ADBLOCK PROOF:", "MEASURED" if ok else "INVALID")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
