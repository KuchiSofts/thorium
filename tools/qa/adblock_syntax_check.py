#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Native ad blocking, the rest of the filter syntax, checked end to end and offline (ROADMAP P5.22):
procedural hide rules (`:shadow()` among them), `$removeparam`, `$csp`, `$permissions` and `method=`.

The check uses the browser's own bundled lists. For each kind of rule it takes the first real rule that is
simple enough to build a page for, serves that page under the rule's site name from a local server
(host-resolver rules send the names to 127.0.0.1 and make every other name fail), and loads it on throwaway
profiles:

    has-text       an element with the rule's text is hidden, one without it is not
    upward         the ancestor the rule climbs to is hidden, the one above it is not
    remove         the element is taken out of the page
    remove-class   the class is taken off the element
    remove-attr    the attribute is taken off the element
    style          the element gets the rule's style
    removeparam    the parameter is gone from a page's address (the server and the page both see the clean
                   address), from a frame's and from a fetch; an image request keeps it
    csp            the page is under the rule's policy: what it forbids is refused and reported
    permissions    every browser feature the lists switch off for all sites is off for the page, also
                   when the site's own header keeps it
    permissions-kept   on a site with an exception for one of them, that one stays and the others are off
    method         a rule for requests sent with POST stops such a request and lets one with GET through
    shadow         a widget whose shadow tree holds what the rule looks for is marked by the procedural runner,
                   whether the tree is open or closed; one without it is not (judged by the runner's mark, as
                   other rules of the lists hide such widgets by their class anyway)

in four modes:

    control    native blocking off: nothing is touched
    native     native blocking on: every rule has acted
    frame      the pages inside frames of a page on 127.0.0.1: the rules apply in a frame too (not the
               permissions rules: they leave pages on the PC itself alone, and what is in them)
    site-off   ads allowed on each site (the per-site switch): nothing is touched

Besides the list rules, the page-side runner for procedural rules (procedural.js) is run on a fixture page
with a battery of hand-written rules, one per operator, and looked at again after the page changes.

    py -3 -I tools/qa/adblock_syntax_check.py --browser <out>\\thoron.exe --work <scratch dir>
Exit status 0 only when every mode and the runner battery pass.
"""
import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.qa import bench  # noqa: E402
from tools.qa.adblock_cosmetic_check import NO_HTTPS_FIRST, NOT_FOR_REPORTS, WARM_HTML  # noqa: E402
from tools.qa.adblock_site_switch_check import _close_browser, _devtools_port, _open  # noqa: E402
from tools.qa.cdp import WebSocket  # noqa: E402

MODES = ("control", "native", "frame", "site-off")
# The removeparam rules that are used are for every site, so the page gets a name of its own.
PARAM_HOST = "param-check.test"
RESULT_TIMEOUT_S = 60
REPORT_AFTER_MS = 2500     # a page reports this long after it has loaded
TAGS = ("div", "span", "a", "p", "section", "article", "aside", "li", "button")
_SIMPLE = r"(?:[a-z][a-z0-9]*)?(?:[.#][A-Za-z][A-Za-z0-9_-]*)+"
_HOST = r"([a-z0-9.-]+)"
RULES = {
    "has-text": re.compile(_HOST + rf"##({_SIMPLE}):has-text\(([A-Za-z][A-Za-z ]{{2,30}})\)"),
    "upward": re.compile(_HOST + rf"##({_SIMPLE}):upward\(([1-4])\)"),
    "remove": re.compile(_HOST + rf"##({_SIMPLE}):remove\(\)"),
    "remove-class": re.compile(_HOST + rf"##({_SIMPLE}):remove-class\(([A-Za-z][A-Za-z0-9_-]*)\)"),
    "remove-attr": re.compile(_HOST + rf"##({_SIMPLE}):remove-attr\(([a-z][a-z0-9-]*)\)"),
    "style": re.compile(_HOST + rf"##({_SIMPLE}):style\((display|overflow|opacity|visibility|position): ?"
                        r"([a-z0-9.]+) !important;?\)"),
}
PARAM_RE = re.compile(r"\$removeparam=([A-Za-z_][A-Za-z0-9_]*)")
CSP_ADDRESS_RE = re.compile(r"\|\|([a-z0-9.-]+)\^\$csp=([^,]+)")
CSP_DOMAIN_RE = re.compile(r"\*?\$(?:doc,|document,)?csp=([^,]+),domain=(\S+)")
# What the csp page tries is a worker; a policy that also limits scripts would stop the page's own script.
CSP_NEEDS = "worker-src 'none'"
# The permissions rules that are used are for every site but those on the PC itself, so the page gets a name
# of its own.
PERMISSIONS_HOST = "perm-check.test"
PERMISSIONS_RE = re.compile(r"\*\$permissions=([a-z][a-z0-9-]*)=\(\),from=~[^,|]+(?:\|~[^,|]+)*")
METHOD_RE = re.compile(r"\|\|([a-z0-9.-]+)((?:/[a-z0-9._-]+)+)\$method=(?:post|POST)")
PERMISSIONS_KEPT_RE = re.compile(r"@@\|\|([a-z0-9.-]+)\^\$permissions=([a-z][a-z0-9-]*)=\(\)")
CSP_NOT = ("script-src", "default-src", "sandbox")
# A value the style page starts from, other than the rule's.
STYLE_START = {"display": ("inline", "block"), "overflow": ("hidden", "scroll"), "opacity": ("0.5", "0.25"),
               "visibility": ("hidden", "collapse"), "position": ("absolute", "relative")}
IN_FRAMES = ("has-text", "upward", "remove", "remove-class", "remove-attr", "style", "shadow")
# host##outer:has(:shadow(inner)), with both parts made of compound selectors the page can be built from
SHADOW_RE = re.compile(r"([a-z0-9.-]+)##(.+?):has\(:shadow\((.+)\)\)")
_COMPOUND = re.compile(r"([a-z][a-z0-9]*)?((?:#[A-Za-z_][\w-]*|\.[A-Za-z_][\w-]*|"
                       r"\[[a-z][a-z0-9-]*(?:[\^*]?=\"[^\"]*\")?\])*)")
_PART = re.compile(r"#([A-Za-z_][\w-]*)|\.([A-Za-z_][\w-]*)|\[([a-z][a-z0-9-]*)(?:([\^*]?)=\"([^\"]*)\")?\]")
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def parse_simple(selector: str) -> dict | None:
    """A selector made of an optional tag name, classes and at most one id, as the element it describes."""
    m = re.fullmatch(r"([a-z][a-z0-9]*)?((?:[.#][A-Za-z][A-Za-z0-9_-]*)+)", selector)
    if not m or (m.group(1) and m.group(1) not in TAGS):
        return None
    parts = re.findall(r"([.#])([A-Za-z][A-Za-z0-9_-]*)", m.group(2))
    ids = [name for kind, name in parts if kind == "#"]
    if len(ids) > 1:
        return None
    return {"tag": m.group(1) or "div", "id": ids[0] if ids else None,
            "classes": [name for kind, name in parts if kind == "."]}


def element_html(selector: str, check: str, text: str = "", attrs: dict | None = None, style: str | None = None,
                 close: bool = True) -> str:
    """The element a simple selector describes, marked with data-check so the page can find it again."""
    e = parse_simple(selector)
    if e is None:
        raise ValueError(selector)
    out = f"<{e['tag']}"
    if e["id"]:
        out += f' id="{e["id"]}"'
    if e["classes"]:
        out += f' class="{" ".join(e["classes"])}"'
    out += f' data-check="{check}"'
    for name, value in (attrs or {}).items():
        out += f' {name}="{value}"'
    if style:
        out += f' style="{style}"'
    return out + f">{text}" + (f"</{e['tag']}>" if close else "")


def compound_html(compound: str, extra: str = "") -> str | None:
    """The opening tag of an element that a compound selector (a tag, #id, .class, [name], [name="v"],
    [name^="v"], [name*="v"]) describes, or None for any other selector."""
    m = _COMPOUND.fullmatch(compound)
    if not m or not compound or (m.group(1) and m.group(1) not in TAGS + ("ins", "iframe", "img")):
        return None
    element_id, classes, attrs = None, [], []
    for part in _PART.finditer(m.group(2)):
        if part.group(1):
            element_id = part.group(1)
        elif part.group(2):
            classes.append(part.group(2))
        else:
            name, how, value = part.group(3), part.group(4), part.group(5)
            value = "1" if value is None else value + ("1" if how == "^" else "")
            if name == "id":
                element_id = value
            else:
                attrs.append(f'{name}="{value}"')
    out = [m.group(1) or "div"]
    if element_id:
        out.append(f'id="{element_id}"')
    if classes:
        out.append(f'class="{" ".join(classes)}"')
    out += attrs
    if extra:
        out.append(extra)
    return "<" + " ".join(out) + ">"


def chain_html(chain: str) -> str | None:
    """Elements nested as a chain of compound selectors joined by " > " describes them."""
    parts = chain.split(" > ")
    opened = [compound_html(part) for part in parts]
    if any(tag is None for tag in opened):
        return None
    closing = "".join(f"</{tag[1:].split(' ')[0].rstrip('>')}>" for tag in reversed(opened))
    return "".join(opened) + closing


def _fit(host: str) -> bool:
    return not any(word in host for word in NOT_FOR_REPORTS)


def _csp_case(lines: list[str]) -> dict | None:
    by_domain = None
    for line in lines:
        if CSP_NEEDS not in line or line.startswith(("!", "@@")) or any(word in line for word in CSP_NOT):
            continue
        if (m := CSP_ADDRESS_RE.fullmatch(line)) and _fit(m.group(1)):
            return {"host": m.group(1), "policy": m.group(2).strip(), "by_address": True}
        if by_domain is None and (m := CSP_DOMAIN_RE.fullmatch(line)):
            hosts = [h for h in m.group(2).split("|") if re.fullmatch(r"[a-z0-9.-]+", h) and _fit(h)]
            if hosts:
                by_domain = {"host": hosts[0], "policy": m.group(1).strip(), "by_address": False}
    return by_domain


def cases(lists_text: str) -> dict:
    """The first usable rule of each kind in the lists. A kind without one is left out."""
    lines = [line.strip() for line in lists_text.splitlines()]
    out = {}
    for line in lines:
        for kind, rule in RULES.items():
            m = rule.fullmatch(line) if kind not in out else None
            if not m or not _fit(m.group(1)) or parse_simple(m.group(2)) is None:
                continue
            case = {"host": m.group(1), "selector": m.group(2)}
            if kind == "has-text":
                case["text"] = m.group(3)
            elif kind == "upward":
                case["levels"] = int(m.group(3))
            elif kind in ("remove-class", "remove-attr"):
                case["name"] = m.group(3)
            elif kind == "style":
                first, second = STYLE_START[m.group(3)]
                case.update(property=m.group(3), value=m.group(4), initial=second if m.group(4) == first else first)
            out[kind] = case
        if "removeparam" not in out and (m := PARAM_RE.fullmatch(line)):
            out["removeparam"] = {"host": PARAM_HOST, "name": m.group(1)}
        if "method" not in out and (m := METHOD_RE.fullmatch(line)) and _fit(m.group(1)):
            out["method"] = {"host": m.group(1), "path": m.group(2), "method": "POST"}
    if csp := _csp_case(lines):
        out["csp"] = csp
    for line in lines:
        if (m := SHADOW_RE.fullmatch(line)) and _fit(m.group(1)) and compound_html(m.group(2)) \
                and chain_html(m.group(3)):
            out["shadow"] = {"host": m.group(1), "outer": m.group(2), "inner": m.group(3)}
            break
    features = [m.group(1) for line in lines if (m := PERMISSIONS_RE.fullmatch(line))]
    if features:
        out["permissions"] = {"host": PERMISSIONS_HOST, "features": features}
        for line in lines:
            if (m := PERMISSIONS_KEPT_RE.fullmatch(line)) and m.group(2) in features and _fit(m.group(1)):
                out["permissions-kept"] = {"host": m.group(1), "kept": m.group(2), "features": features}
                break
    return out


def hosts(found: dict) -> list[str]:
    return sorted({case["host"] for case in found.values()})


def _dirty(case: dict) -> str:
    return f"{case['name']}=abc&keep=1"


def page_path(kind: str, case: dict) -> str:
    return f"/clean.html?{_dirty(case)}" if kind == "removeparam" else f"/{kind}.html"


def page_html(kind: str, case: dict) -> str:
    """The page for one case. It reports to /result/<kind> a while after it has loaded."""
    script = ""
    if kind == "has-text":
        body = element_html(case["selector"], "yes", case["text"]) + element_html(case["selector"], "no", "plain words")
        report = "{yes: hidden(q('yes')), no: hidden(q('no'))}"
    elif kind == "upward":
        n = case["levels"]
        body = ("".join(f'<div data-level="{level}">' for level in range(n + 1, 0, -1))
                + element_html(case["selector"], "start", "ad") + "</div>" * (n + 1))
        report = f"{{target: hidden(level({n})), above: hidden(level({n + 1}))}}"
    elif kind == "remove":
        body = element_html(case["selector"], "gone", "ad")
        report = "{present: !!q('gone')}"
    elif kind == "remove-class":
        selector = case["selector"]
        if case["name"] not in parse_simple(selector)["classes"]:
            selector += "." + case["name"]
        body = element_html(selector, "el", "link")
        report = f"{{has: q('el').classList.contains({json.dumps(case['name'])})}}"
    elif kind == "remove-attr":
        body = element_html(case["selector"], "el", "link", attrs={case["name"]: "x"})
        report = f"{{has: q('el').hasAttribute({json.dumps(case['name'])})}}"
    elif kind == "style":
        body = element_html(case["selector"], "el", "text", style=f"{case['property']}: {case['initial']}")
        report = f"{{value: getComputedStyle(q('el')).getPropertyValue({json.dumps(case['property'])})}}"
    elif kind == "removeparam":
        dirty = _dirty(case)
        body = (f'<img src="/shape.gif?{dirty}" width="1" height="1" alt="">'
                f'<iframe src="/inner.html?{dirty}" width="100" height="50"></iframe>')
        script = f"fetch('/data.json?{dirty}').catch(() => {{}});"
        report = "{search: location.search}"
    elif kind == "csp":
        body = "<p>policy check</p>"
        script = ("const violations = [];"
                  "document.addEventListener('securitypolicyviolation', (e) => "
                  "violations.push({directive: e.effectiveDirective, policy: e.originalPolicy}));"
                  "let worker = 'started';"
                  "try { new Worker('/worker.js'); } catch (e) { worker = 'refused'; }")
        report = "{worker, violations}"
    elif kind == "shadow":
        body = "<p>shadow check</p>"
        inner = chain_html(case["inner"])
        plain = chain_html(case["inner"].rsplit(" > ", 1)[0]) if " > " in case["inner"] else "<p>plain</p>"
        script = ("const make = (check, options, content) => {"
                  "const t = document.createElement('template');"
                  f"t.innerHTML = {json.dumps(compound_html(case['outer'], 'data-check=CHECK'))}"
                  ".replace('CHECK', JSON.stringify(check)) + '</div>';"
                  "const host = t.content.firstElementChild; document.body.appendChild(host);"
                  "host.attachShadow(options).innerHTML = content; };"
                  f"make('open', {{mode: 'open'}}, {json.dumps(inner)});"
                  f"make('closed', {{mode: 'closed'}}, {json.dumps(inner)});"
                  f"make('plain', {{mode: 'open'}}, {json.dumps(plain)});")
        # the runner marks what a rule finds with an attribute of 12 small letters
        script += "const marked = (e) => !!e && e.getAttributeNames().some((n) => /^[a-z]{12}$/.test(n));"
        report = "{open: marked(q('open')), closed: marked(q('closed')), plain: marked(q('plain'))}"
    elif kind == "method":
        body = "<p>method check</p>"
        path = case["path"]
        script = ("const sent = {};"
                  f"fetch('{path}', {{method: 'POST', body: 'x'}})"
                  ".then(() => { sent.post = 'loaded'; }, () => { sent.post = 'blocked'; });"
                  f"fetch('{path}').then(() => {{ sent.get = 'loaded'; }}, () => {{ sent.get = 'blocked'; }});")
        report = "sent"
    elif kind in ("permissions", "permissions-kept"):
        body = "<p>features check</p>"
        # only a feature this browser has can be on or off
        script = (f"const names = {json.dumps(case['features'])};"
                  "const policy = document.featurePolicy;"
                  "const known = policy ? names.filter((n) => policy.features().includes(n)) : [];"
                  "const allowed = known.filter((n) => policy.allowsFeature(n));")
        report = "{known, allowed}"
    else:
        raise ValueError(kind)
    return ("<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>Thoron syntax check, {kind}</title></head><body>{body}"
            "<script>const hidden = (e) => !!e && getComputedStyle(e).display === 'none';"
            "const q = (name) => document.querySelector('[data-check=' + JSON.stringify(name) + ']');"
            "const level = (n) => document.querySelector('[data-level=' + JSON.stringify(String(n)) + ']');"
            f"{script}"
            "addEventListener('load', () => setTimeout(() => "
            f"fetch('/result/{kind}', {{method: 'POST', body: JSON.stringify({report})}}), {REPORT_AFTER_MS}));"
            "</script></body></html>")


def page_headers(kind: str, case: dict) -> dict:
    """Headers the site itself sends with a case's page. The permissions page comes with a policy of the
    site's own that keeps every feature for the site: the rules must win over it."""
    if kind == "permissions":
        return {"Permissions-Policy": ", ".join(f"{feature}=(self)" for feature in case["features"])}
    return {}


def framed(found: dict) -> list[str]:
    """The kinds that are checked inside a frame of another site's page. A csp rule that goes by the site of
    the page (`domain=`) does not apply there; removeparam brings a frame of its own."""
    kinds = [kind for kind in IN_FRAMES if kind in found]
    if found.get("csp", {}).get("by_address"):
        kinds.append("csp")
    return kinds


def parent_html(found: dict) -> str:
    frames = "".join(f'<iframe src="http://{found[kind]["host"]}{page_path(kind, found[kind])}" width="300" '
                     'height="120"></iframe>' for kind in framed(found))
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Thoron syntax check, frames</title></head>'
            f"<body>{frames}</body></html>")


def judgeable(kind: str, case: dict, control: dict | None) -> bool:
    """False for a case that the run with blocking off shows cannot be judged in this browser: its page did
    not load, or the browser does not have the one feature an exception is about."""
    if not isinstance(control, dict):
        return False
    if kind == "permissions-kept":
        return case["kept"] in (control.get("known") or [])
    return True


def _policy(text: str) -> str:
    return " ".join(str(text).replace(";", " ; ").split()).strip(" ;")


def problems(mode: str, kind: str, case: dict, result: dict | None) -> list[str]:
    if mode not in MODES:
        raise ValueError(mode)
    if not isinstance(result, dict):
        return ["the page gave no result"]
    on = mode in ("native", "frame")
    off = "though blocking is off here"
    out = []
    if kind == "has-text":
        if bool(result.get("yes")) != on:
            out.append(f"the element with the text {case['text']!r} is " + ("not hidden" if on else f"hidden {off}"))
        if result.get("no"):
            out.append("the element without the text is hidden")
    elif kind == "upward":
        if bool(result.get("target")) != on:
            out.append(f"the ancestor {case['levels']} levels up is " + ("not hidden" if on else f"hidden {off}"))
        if result.get("above"):
            out.append("the ancestor one level further up is hidden too")
    elif kind == "remove":
        if bool(result.get("present")) == on:
            out.append("the element is still in the page" if on else f"the element was removed {off}")
    elif kind in ("remove-class", "remove-attr"):
        what = "class" if kind == "remove-class" else "attribute"
        if bool(result.get("has")) == on:
            out.append(f"the {what} {case['name']} is still there" if on else f"the {what} {case['name']} was removed {off}")
    elif kind == "style":
        want = case["value"] if on else case["initial"]
        if result.get("value") != want:
            out.append(f"{case['property']} is {result.get('value')!r}, not {want!r}")
    elif kind == "removeparam":
        dirty = _dirty(case)
        clean = "keep=1" if on else dirty
        seen = result.get("seen") or {}
        for path, want in (("/clean.html", clean), ("/data.json", clean), ("/inner.html", clean), ("/shape.gif", dirty)):
            if seen.get(path) != want:
                out.append(f"the server was asked for {path}?{seen.get(path)}, not {path}?{want}")
        if result.get("search") != "?" + clean:
            out.append(f"the page sees the address ending {result.get('search')!r}, not {'?' + clean!r}")
    elif kind == "csp":
        mine = [v for v in result.get("violations") or []
                if str(v.get("directive", "")).startswith("worker-src") and _policy(v.get("policy")) == _policy(case["policy"])]
        if on and not mine:
            out.append(f"nothing was refused under the rule's policy {case['policy']!r}: {result}")
        if not on and (result.get("violations") or result.get("worker") != "started"):
            out.append(f"the page is under a policy {off}: {result}")
    elif kind == "shadow":
        for which in ("open", "closed"):
            if bool(result.get(which)) != on:
                out.append(f"the widget whose shadow tree is {which} is " + ("not marked" if on else f"marked {off}"))
        if result.get("plain"):
            out.append("the widget without the sponsored link is marked")
    elif kind == "method":
        want = "blocked" if on else "loaded"
        if result.get("post") != want:
            out.append("a request with POST was let through" if on else f"a request with POST was stopped {off}")
        if result.get("get") != "loaded":
            out.append("a request with GET was stopped")
    elif kind in ("permissions", "permissions-kept"):
        known = [feature for feature in case["features"] if feature in (result.get("known") or [])]
        allowed = result.get("allowed") or []
        if not known:
            out.append("the browser knows none of the features the rules name")
        for feature in known:
            kept = on and feature == case.get("kept")
            if on and not kept and feature in allowed:
                out.append(f"{feature} is still allowed")
            elif (kept or not on) and feature not in allowed:
                out.append(f"{feature} is switched off " + ("though the exception keeps it" if kept else off))
    else:
        raise ValueError(kind)
    return out


# --- The runner battery: procedural.js on a fixture page, one hand-written rule per operator. ---

RUNNER_HTML = (
    '<!doctype html><html><head><meta charset="utf-8"><title>Thoron procedural runner check</title>'
    '<style>#before1::before{content:"Ad ";}#bg{background-color:rgb(1, 2, 3);}</style></head><body>'
    '<div id="list"><div class="card" id="c1"><span class="label" id="lab1">Sponsored</span><p id="p1">buy</p></div>'
    '<div class="card" id="c2"><span class="label" id="lab2">News</span><p id="p2">read this long text here</p></div>'
    '<div class="card keep" id="c3"><span class="label" id="lab3">Sponsored</span></div></div>'
    '<div id="deep"><section id="s1"><div id="d1"><a id="a1" href="/out" data-ad="yes">Ad link</a></div></section></div>'
    '<p id="before1">text</p><p id="before2">text</p><div id="bg"></div>'
    '<div id="o-wrap"><div id="o-keep"><b id="o-inner">x</b></div><div id="o-other">y</div></div>'
    '<ul id="ul1"><li id="l1" class="locked" disabled-x="1">one</li><li id="l2">two</li></ul>'
    '<div id="rm">remove me</div>'
    '<h2 id="h2a">Sponsored</h2><div id="sib1">after heading</div><h2 id="h2b">Other</h2><div id="sib2">after other</div>'
    '<div id="sh-host"></div><script>document.getElementById("sh-host").attachShadow({mode: "open"}).innerHTML = '
    "'<p id=\"sh-target\">in a shadow tree</p>';</script>"
    "</body></html>")


def _rule(mark: str, selector: str, *tasks) -> dict:
    return {"s": selector, "t": [list(t) for t in tasks], "a": ["mark", mark]}


def _inner(selector: str, *tasks) -> dict:
    return {"s": selector, "t": [list(t) for t in tasks]}


RUNNER_FILTERS = [
    _rule("m01", ".card", ("has-text", "Sponsored")),
    _rule("m02", ".card", ("has-text", "/^news/i")),
    _rule("m03", ".card", ("has", _inner(".label", ("has-text", "Sponsored"))), ("spath", ":not(.keep)")),
    _rule("m04", ".card", ("not", _inner("p", ("min-text-length", "1")))),
    _rule("m05", "#a1", ("upward", "2")),
    _rule("m06", "#a1", ("upward", "#deep")),
    _rule("m07", "a", ("matches-attr", "data-ad=yes")),
    _rule("m08", "a", ("matches-attr", "/^data-/=/^y/")),
    _rule("m09", "p", ("matches-css-before", "content: /Ad/")),
    _rule("m10", "div", ("matches-css", "background-color: rgb(1, 2, 3)")),
    _rule("m11", "#a1", ("xpath", "..")),
    _rule("m12", "", ("xpath", "//b[@id='o-inner']")),
    _rule("m13", "#o-keep", ("others", "")),
    _rule("m14", "h2", ("has-text", "Sponsored"), ("spath", " + div")),
    _rule("m15", "", ("matches-path", "/runner"), ("spath", " #l2")),
    _rule("m16", "", ("matches-path", "/nowhere"), ("spath", " #l2")),
    _rule("m17", "li", ("min-text-length", "3")),
    _rule("m18", "div", ("matches-media", "(min-width: 1px)"), ("spath", "#bg")),
    _rule("m19", "div", ("matches-media", "(max-width: 1px)")),
    _rule("m20", "#l2", ("watch-attr", "class"), ("spath", ".late")),
    _rule("m21", ".card", ("has", _inner("> .label", ("has-text", "News")))),
    _rule("m22", "#lab1", ("spath", " ~ p")),
    # an element in a shadow tree: the document's style sheets do not reach it, the runner styles it
    {"s": "#sh-host", "t": [["shadow", "p"]], "a": ["mark", "m23", "display:none!important"]},
    {"s": "#rm", "t": [], "a": ["remove"]},
    {"s": "#l1", "t": [], "a": ["remove-class", "locked"]},
    {"s": "#l1", "t": [], "a": ["remove-attr", "disabled-x"]},
]
# mark -> the ids of the elements that must carry it, and no other
RUNNER_EXPECT = {
    "m01": ["c1", "c3"], "m02": ["c2"], "m03": ["c1"], "m04": ["c3"], "m05": ["s1"], "m06": ["deep"],
    "m07": ["a1"], "m08": ["a1"], "m09": ["before1"], "m10": ["bg"], "m11": ["d1"], "m12": ["o-inner"],
    "m14": ["sib1"], "m15": ["l2"], "m16": [], "m17": ["l1", "l2"], "m18": ["bg"], "m19": [], "m20": [],
    "m21": ["c2"], "m22": ["p1"], "m23": [],
}
# "others" marks most of the page: what must and what must not carry the mark
RUNNER_EXPECT_NOT_ONLY = {"m13": {"has": ["o-other", "list", "deep"], "not": ["o-keep", "o-inner", "o-wrap"]}}
RUNNER_STATE = {"removed": True, "class": "", "attribute": False, "shadow": "none"}
# Then the page changes: an attribute that is watched, a new element, and text that no longer matches.
RUNNER_CHANGE = ("document.getElementById('l2').className = 'late';"
                 "const c4 = document.createElement('div'); c4.className = 'card'; c4.id = 'c4';"
                 "c4.innerHTML = '<span class=\"label\">Sponsored</span>';"
                 "document.getElementById('list').appendChild(c4);"
                 "document.getElementById('lab1').textContent = 'News'; 'changed'")
RUNNER_EXPECT_LATER = {"m01": ["c3", "c4"], "m02": ["c1", "c2"], "m03": ["c4"], "m04": ["c3", "c4"], "m20": ["l2"],
                       "m21": ["c1", "c2"]}


def runner_code(source: str) -> str:
    """procedural.js as the engine sends it: without its comment lines."""
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//")).strip()


def runner_problems(expect: dict, got: dict) -> list[str]:
    out = []
    for mark, ids in sorted(expect.items()):
        found = got.get(mark) or []
        if set(found) != set(ids):
            out.append(f"{mark}: marked {sorted(found)}, expected {sorted(ids)}")
    return out


def _collect_expression() -> str:
    marks = [f["a"][1] for f in RUNNER_FILTERS if f["a"][0] == "mark"]
    return ("JSON.stringify({marks: Object.fromEntries(" + json.dumps(marks) + ".map((m) => [m, "
            "Array.from(document.querySelectorAll('[' + m + ']')).map((e) => e.id || e.localName)])), "
            "state: {removed: !document.getElementById('rm'), class: document.getElementById('l1').className, "
            "attribute: document.getElementById('l1').hasAttribute('disabled-x'), "
            "shadow: getComputedStyle(document.getElementById('sh-host').shadowRoot"
            ".getElementById('sh-target')).display}})")


def _evaluate(ws: WebSocket, expression: str):
    reply = ws.call("Runtime.evaluate", expression=expression, returnByValue=True)
    if "exceptionDetails" in reply:
        details = reply["exceptionDetails"]
        raise RuntimeError(f"the page threw: {details.get('text')} {details.get('exception', {}).get('description', '')}")
    return reply.get("result", {}).get("value")


class PageServer:
    def __init__(self, found: dict):
        self.results: dict = {}
        self.seen: dict = {}
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, ctype: str, body: bytes, more: dict | None = None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for name, value in (more or {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _is_method_target(self) -> bool:
                case = found.get("method")
                host = (self.headers.get("Host") or "").split(":")[0]
                return bool(case) and host == case["host"] and self.path == case["path"]

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if self._is_method_target() and length <= 65536:
                    self.rfile.read(length)
                    self._send(200, "text/plain", b"ok")
                    return
                kind = self.path.removeprefix("/result/")
                if not self.path.startswith("/result/") or kind not in found or length > 65536:
                    self._send(404, "text/plain", b"refused")
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeError):
                    data = None
                if isinstance(data, dict):
                    server.results[kind] = data
                self._send(200, "text/plain", b"ok")

            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                host = (self.headers.get("Host") or "").split(":")[0]
                html = "text/html; charset=utf-8"
                if host == PARAM_HOST and "removeparam" in found:
                    server.seen[url.path] = url.query
                    if url.path == "/clean.html":
                        self._send(200, html, page_html("removeparam", found["removeparam"]).encode())
                    elif url.path == "/inner.html":
                        self._send(200, html, b"<!doctype html><title>inner</title><p>inner</p>")
                    elif url.path == "/data.json":
                        self._send(200, "application/json", b"{}")
                    elif url.path == "/shape.gif":
                        self._send(200, "image/gif", GIF)
                    else:
                        self._send(404, "text/plain", b"not found")
                    return
                kind = url.path.removeprefix("/").removesuffix(".html")
                if url.path.endswith(".html") and kind in found and kind != "removeparam" and host == found[kind]["host"]:
                    self._send(200, html, page_html(kind, found[kind]).encode(), page_headers(kind, found[kind]))
                elif self._is_method_target():
                    self._send(200, "text/plain", b"ok")
                elif url.path == "/worker.js":
                    self._send(200, "text/javascript", b"// a worker that does nothing\n")
                elif url.path == "/parent.html" and host == "127.0.0.1":
                    self._send(200, html, parent_html(found).encode())
                elif url.path == "/warm.html" and host == "127.0.0.1":
                    self._send(200, html, WARM_HTML.encode())
                elif url.path == "/runner.html" and host == "127.0.0.1":
                    self._send(200, html, RUNNER_HTML.encode())
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


def _launch(browser: Path, profile: Path, port: int, names: list[str], native: bool,
            enable: tuple[str, ...] = ()) -> subprocess.Popen:
    # The test pages are plain http, and the browser would first try https for a top-level visit: both
    # features that do that are switched off.
    mapping = ", ".join(f"MAP {name} 127.0.0.1:{port}" for name in names)
    args = [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-default-apps", "--disable-background-networking",
            "--disable-component-update", f"--disable-features={NO_HTTPS_FIRST}",
            f"--host-resolver-rules={mapping}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
    features = [*enable, *(["ThoronNativeAdblock"] if native else [])]
    if features:
        # one switch: of several, the browser reads only the last
        args.append(f"--enable-features={','.join(features)}")
    return subprocess.Popen(args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=os.name != "nt")


def _navigate(port: int, url: str) -> None:
    """Opens `url` exactly as written (its query included) in a new tab."""
    target = _open(port, "about:blank")
    ws = WebSocket(target["webSocketDebuggerUrl"])
    try:
        ws.call("Page.navigate", url=url)
    finally:
        ws.close()


def run_mode(browser: Path, work: Path, found: dict, mode: str) -> dict:
    profile = Path(tempfile.mkdtemp(prefix=f"syntax-{mode}-", dir=work))
    kinds = framed(found) if mode == "frame" else list(found)
    results: dict = {}
    with PageServer(found) as server:
        proc = _launch(browser, profile, server.port, hosts(found), native=mode != "control")
        port = None
        try:
            port = _devtools_port(profile)
            if mode == "site-off":
                target = _open(port, "chrome://settings/content/ads")
                time.sleep(3)
                ws = WebSocket(target["webSocketDebuggerUrl"])
                try:
                    for name in hosts(found):
                        allow = [name, "", "ads", "allow", False]
                        ws.call("Runtime.evaluate",
                                expression=f"chrome.send('setCategoryPermissionForPattern', {json.dumps(allow)})")
                finally:
                    ws.close()
                time.sleep(1)
            if mode != "control":
                # the engine loads when the first page asks for it: let one page go by first
                _open(port, f"http://127.0.0.1:{server.port}/warm.html")
                time.sleep(4)
            if mode == "frame":
                _open(port, f"http://127.0.0.1:{server.port}/parent.html")
            else:
                for kind in kinds:
                    _navigate(port, f"http://{found[kind]['host']}{page_path(kind, found[kind])}")
            deadline = time.monotonic() + RESULT_TIMEOUT_S
            while len(server.results) < len(kinds) and time.monotonic() < deadline:
                time.sleep(0.2)
            results = dict(server.results)
            if "removeparam" in results:
                results["removeparam"]["seen"] = dict(server.seen)
        except (OSError, RuntimeError, ValueError) as e:
            print(f"{mode}: {e}", file=sys.stderr)
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    found_problems = {kind: p for kind in kinds if (p := problems(mode, kind, found[kind], results.get(kind)))}
    return {"mode": mode, "passed": not found_problems, "problems": found_problems, "results": results}


def run_runner(browser: Path, work: Path, runner: Path) -> dict:
    """The battery: the runner on the fixture page, then again after the page has changed."""
    code = runner_code(runner.read_text(encoding="utf-8"))
    profile = Path(tempfile.mkdtemp(prefix="syntax-runner-", dir=work))
    found_problems: list[str] = []
    with PageServer({}) as server:
        proc = _launch(browser, profile, server.port, [], native=False)
        port = None
        try:
            port = _devtools_port(profile)
            target = _open(port, f"http://127.0.0.1:{server.port}/runner.html")
            time.sleep(2)
            ws = WebSocket(target["webSocketDebuggerUrl"])
            try:
                _evaluate(ws, f"{code}({json.dumps(RUNNER_FILTERS)}); 'started'")
                time.sleep(1)
                first = json.loads(_evaluate(ws, _collect_expression()))
                found_problems += runner_problems(RUNNER_EXPECT, first["marks"])
                for mark, want in RUNNER_EXPECT_NOT_ONLY.items():
                    got = set(first["marks"].get(mark) or [])
                    if not set(want["has"]) <= got or got & set(want["not"]):
                        found_problems.append(f"{mark}: marked {sorted(got)}, expected {want}")
                if first["state"] != RUNNER_STATE:
                    found_problems.append(f"actions: {first['state']}, expected {RUNNER_STATE}")
                _evaluate(ws, RUNNER_CHANGE)
                time.sleep(1.5)
                later = json.loads(_evaluate(ws, _collect_expression()))
                found_problems += ["after the page changed, " + p
                                   for p in runner_problems(RUNNER_EXPECT_LATER, later["marks"])]
            finally:
                ws.close()
        except (OSError, RuntimeError, ValueError, KeyError) as e:
            found_problems.append(f"the battery did not run: {e}")
        finally:
            if port is not None:
                _close_browser(port, proc)
            else:
                bench._stop(proc, profile)
            shutil.rmtree(profile, ignore_errors=True)
    return {"mode": "runner", "passed": not found_problems, "problems": found_problems,
            "rules": len(RUNNER_FILTERS)}


def run_all(browser: Path, work: Path, lists_file: Path, runner: Path | None) -> dict:
    found = cases(lists_file.read_text(encoding="utf-8"))
    if not found:
        raise SystemExit(f"{lists_file} has no rule this check can build a page for")
    work.mkdir(parents=True, exist_ok=True)
    out = {"cases": found, "results": []}
    if runner is not None and runner.is_file():
        out["results"].append(run_runner(browser, work, runner))
    else:
        out["runner_skipped"] = f"procedural.js not found ({runner})"
    control = run_mode(browser, work, found, "control")
    # A name the browser will not load over plain http (it forces https for it) cannot be judged, nor an
    # exception for a feature this browser does not have: such cases are left out, by the run with blocking
    # off, and named in the output.
    unusable = [kind for kind in found if not judgeable(kind, found[kind], control["results"].get(kind))]
    if unusable:
        out["left_out"] = {kind: found[kind] for kind in unusable}
        found = {kind: case for kind, case in found.items() if kind not in unusable}
        out["cases"] = found
        control = run_mode(browser, work, found, "control")
    if not found:
        raise SystemExit("no case could be loaded at all, even with blocking off")
    out["results"].append(control)
    out["results"] += [run_mode(browser, work, found, mode) for mode in MODES if mode != "control"]
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="scratch folder for the throwaway profiles")
    parser.add_argument("--lists", type=Path, help="bundled lists (default: thoron_adblock_lists.txt next to it)")
    parser.add_argument("--runner", type=Path,
                        help="procedural.js (default: components/thoron_adblock/ of the tree the browser was built in)")
    a = parser.parse_args(argv)
    browser = a.browser.resolve()
    runner = a.runner or browser.parents[2] / "components" / "thoron_adblock" / "procedural.js"
    out = run_all(browser, a.work, a.lists or browser.parent / "thoron_adblock_lists.txt", runner)
    print(json.dumps(out, indent=2))
    ok = all(r["passed"] for r in out["results"]) and "runner_skipped" not in out
    print("SYNTAX CHECK:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
