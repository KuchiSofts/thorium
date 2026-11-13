#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, its pages in the browser's language, checked end to end and offline (ROADMAP P5.51).

As uBlock Origin's pages are in the language of the browser, chrome://adblock and the menu of the shield are
in the browser's language: the browser writes it into the page, and i18n.js translates every text the page
shows. A local server serves a test page under a name of its own (host-resolver rules; every other name fails,
so nothing leaves the PC) so that the menu has a site, its counts and its grid. Steps:

    english   with the browser in English (--lang=en-US) the pages are as written: lang "en", left to right;
              every text they show is noted
    <lang>    for each language (es, fr, de, pt, ru): both pages say so (lang, left to right), and no text
              they show is still one of the English texts: names (uBlock Origin, JavaScript, Ctrl...), rules,
              addresses and the titles of lists stay as they are

    py -3 -I tools/qa/adblock_i18n_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every step passes.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.adblock_syntax_check import NO_HTTPS_FIRST  # noqa: E402
from tools.qa.adblock_trust_check import Server  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

PAGE_HOST = "i18n-check.test"
PAGES = {"settings": "chrome://adblock/", "menu": "chrome://adblock-menu.top-chrome/"}
LANGS = ("es", "fr", "de", "pt", "ru")
SETTLE_S = 3.0
# Words in Latin letters any page may show as they are: names of products and keys, units
NAMES = {"ublock", "origin", "thoron", "javascript", "webrtc", "csp", "ip", "ctrl", "alt", "shift", "kb", "mb",
         "https", "example", "com", "easylist"}
# Texts that are the same word in English and in a language of the table
SAME = {"Sites", "Sections", "Images", "Tab"}
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
# hosts, addresses and rules inside a text ("Allow: example.com on this site", "||ads^"): never translated
CODE_LIKE = re.compile(r"\S*[.|^#$@/:=*+]\S*")

# Every text the page shows and every title, label and placeholder, but not code, rules, addresses, request
# types, host names, the titles of lists or what a person typed.
READ = r"""(() => {
  const keep = 'code, pre, textarea, script, style, .url, td.url, td.type, .host, .site, .title, #log-tab,' +
               ' #my-filters, .grid-row.host .name, .grid-row.domain .name, #lists input, #catalog input';
  const out = [];
  const walk = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.nodeValue.trim().replace(/\s+/g, ' ');
      if (text && !(node.parentElement && node.parentElement.closest(keep))) out.push(text);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE || node.matches(keep)) return;
    for (const name of ['title', 'aria-label', 'placeholder']) {
      const value = node.getAttribute(name);
      if (value && value.trim()) out.push(value.trim().replace(/\s+/g, ' '));
    }
    node.childNodes.forEach(walk);
  };
  walk(document.documentElement);
  return JSON.stringify({lang: document.documentElement.lang, dir: document.documentElement.dir, texts: out});
})()"""


def has_words(text: str) -> bool:
    """True when a text holds a word in Latin letters that is not a name, a host, an address or a rule."""
    return any(w.lower() not in NAMES for w in LATIN_WORD.findall(CODE_LIKE.sub(" ", text)))


def english_left(texts: list[str], english: set[str]) -> list[str]:
    """The texts that are still one of the English texts of the page (and are words, not names)."""
    return [t for t in texts if t in english and t not in SAME and has_words(t)]


def lang_problems(lang: str, page: str, seen: dict, english: set[str]) -> list[str]:
    out = []
    if not str(seen.get("lang", "")).lower().startswith(lang) or seen.get("dir") != "ltr":
        out.append(f"{lang}: {page}: the page is lang {seen.get('lang')!r}, dir {seen.get('dir')!r}")
    left = english_left(seen.get("texts", []), english)
    out += [f"{lang}: {page}: not translated: {t!r}" for t in left[:15]]
    if len(left) > 15:
        out.append(f"{lang}: {page}: and {len(left) - 15} more")
    return out


def english_problems(page: str, seen: dict) -> list[str]:
    out = []
    if not str(seen.get("lang", "")).startswith("en") or seen.get("dir") != "ltr":
        out.append(f"english: {page}: the page is lang {seen.get('lang')!r}, dir {seen.get('dir')!r}")
    if len(seen.get("texts", [])) < 20:
        out.append(f"english: {page}: only {len(seen.get('texts', []))} texts were read")
    return out


def _eval(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    return reply.get("result", {}).get("value")


def _launch_lang(browser: Path, profile: Path, port: int, lang: str) -> subprocess.Popen:
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            "--enable-features=ThoronNativeAdblock", f"--lang={lang}",
            f"--host-resolver-rules=MAP {PAGE_HOST} 127.0.0.1:{port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def read_pages(browser: Path, work: Path, lang: str) -> dict:
    """{page: what READ found}, with the browser in `lang`."""
    profile = Path(tempfile.mkdtemp(prefix=f"i18n-{lang}-", dir=work))
    found: dict = {}
    with Server() as server:
        proc = _launch_lang(browser, profile, server.port, lang)
        port = None
        sockets = []
        try:
            port = _devtools_port(profile)
            target = _open(port, f"http://{PAGE_HOST}/page.html")
            sockets.append(WebSocket(target["webSocketDebuggerUrl"]))
            time.sleep(SETTLE_S)
            for name, url in PAGES.items():
                ws = WebSocket(_open(port, url)["webSocketDebuggerUrl"])
                sockets.append(ws)
                if name == "menu":
                    # the menu works on the active tab: the test page
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/json/activate/{target['id']}",
                                           timeout=10).read()
                time.sleep(SETTLE_S)
                if name == "menu":
                    _eval(ws, "document.getElementById('grid-box').open = true; 1")
                    time.sleep(1.5)
                found[name] = json.loads(_eval(ws, READ) or "{}")
        finally:
            for ws in sockets:
                try:
                    ws.close()
                except OSError:
                    pass
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    return found


def run(browser: Path, work: Path) -> list[str]:
    problems: list[str] = []
    try:
        english_pages = read_pages(browser, work, "en-US")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
        return [f"the run failed (en): {e}"]
    english: dict[str, set[str]] = {}
    for page, seen in english_pages.items():
        found = english_problems(page, seen)
        english[page] = set(seen.get("texts", []))
        print(f"{'PASS' if not found else 'FAIL'}  english: {page}: lang {seen.get('lang')!r}, "
              f"{len(english[page])} texts")
        problems += found
    for lang in LANGS:
        try:
            pages = read_pages(browser, work, lang)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as e:
            problems.append(f"the run failed ({lang}): {e}")
            continue
        for page, seen in pages.items():
            found = lang_problems(lang, page, seen, english.get(page, set()))
            print(f"{'PASS' if not found else 'FAIL'}  {lang}: {page}: lang {seen.get('lang')!r}, "
                  f"{len(seen.get('texts', []))} texts")
            problems += found
    return problems


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--browser", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    a = p.parse_args(argv)
    a.work.mkdir(parents=True, exist_ok=True)
    problems = run(a.browser.resolve(), a.work)
    for problem in problems:
        print(problem)
    print("I18N CHECK: PASSED" if not problems else f"I18N CHECK: FAILED ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
