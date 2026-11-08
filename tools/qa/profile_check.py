#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Profile compatibility check: did a new browser version keep a profile 1:1? (ROADMAP Q.7)

`snapshot` summarises a `User Data` folder: per profile the open windows, tabs, pinned tabs and tab
groups (name, colour, tab count) from the newest session file; the number of bookmarks, saved
passwords and cookies (and how cookies are encrypted); and the enabled extensions. It also records
whether `Local State` holds a DPAPI key and an app-bound key.

It never decrypts anything and never writes a secret, a URL or a cookie value: only counts,
extension IDs, tab-group names and key *presence*. Run it on copies, with the browser closed.

`compare` lists everything the second snapshot lost: fewer passwords, bookmarks or tabs, missing or
changed tab groups, extensions no longer enabled, a cookie loss beyond normal expiry, or a new
app-bound encryption key (which the older version could not read after a rollback).
    py -3 -I tools/qa/profile_check.py snapshot "<User Data>" --out before.json
    py -3 -I tools/qa/profile_check.py compare before.json after.json
Exit status 1 when compare finds a problem.
"""
import argparse
import json
import re
import sqlite3
import struct
import sys
from pathlib import Path

CMD_SET_TAB_WINDOW, CMD_PINNED, CMD_TAB_CLOSED, CMD_WINDOW_CLOSED = 0, 12, 16, 17
CMD_SET_TAB_GROUP, CMD_TAB_GROUP_METADATA2 = 25, 27
COOKIE_LOSS_TOLERANCE = 0.02      # expired cookies are deleted at start-up


def _records(data: bytes):
    pos = 8
    while pos + 2 <= len(data):
        (size,) = struct.unpack_from("<H", data, pos)
        pos += 2
        if size == 0 or pos + size > len(data):
            break
        yield data[pos], data[pos + 1:pos + size]
        pos += size


def _pickle_string16(buf: bytes, pos: int) -> tuple[str, int]:
    (length,) = struct.unpack_from("<i", buf, pos)
    pos += 4
    raw = buf[pos:pos + 2 * length]
    pos += 2 * length
    return raw.decode("utf-16-le", "replace"), pos + (-pos % 4)


def session_summary(data: bytes) -> dict:
    """Replay a Chromium session file (SNSS version 3) into live windows, tabs and tab groups."""
    if len(data) < 8 or data[:4] != b"SNSS":
        return {"unreadable": True}
    (version,) = struct.unpack_from("<i", data, 4)
    if version != 3:
        return {"encrypted": True} if version == 5 else {"unreadable": True}
    tabs: dict[int, dict] = {}
    groups: dict[tuple, dict] = {}
    for cmd, p in _records(data):
        try:
            if cmd == CMD_SET_TAB_WINDOW and len(p) >= 8:
                window, tab = struct.unpack_from("<ii", p)
                tabs.setdefault(tab, {"pinned": False, "group": None})["window"] = window
            elif cmd == CMD_TAB_CLOSED and len(p) >= 4:
                tabs.pop(struct.unpack_from("<i", p)[0], None)
            elif cmd == CMD_WINDOW_CLOSED and len(p) >= 4:
                (window,) = struct.unpack_from("<i", p)
                tabs = {t: v for t, v in tabs.items() if v.get("window") != window}
            elif cmd == CMD_PINNED and len(p) >= 5:
                tab, state = struct.unpack_from("<i?", p)
                tabs.setdefault(tab, {"pinned": False, "group": None})["pinned"] = state
            elif cmd == CMD_SET_TAB_GROUP and len(p) >= 25:
                tab, hi, lo, has = struct.unpack_from("<i4xQQ?", p)
                tabs.setdefault(tab, {"pinned": False, "group": None})["group"] = (hi, lo) if has else None
            elif cmd == CMD_TAB_GROUP_METADATA2 and len(p) >= 4 + 16 + 4:
                hi, lo = struct.unpack_from("<QQ", p, 4)
                title, pos = _pickle_string16(p, 20)
                (color,) = struct.unpack_from("<I", p, pos)
                groups[(hi, lo)] = {"title": title, "color": color}
        except struct.error:
            continue
    live = {t: v for t, v in tabs.items() if "window" in v}
    counts: dict[tuple, int] = {}
    for v in live.values():
        if v["group"] is not None:
            counts[v["group"]] = counts.get(v["group"], 0) + 1
    group_list = sorted(({**groups.get(g, {"title": "", "color": -1}), "tabs": n} for g, n in counts.items()),
                        key=lambda g: (g["title"], g["color"], g["tabs"]))
    return {"windows": len({v["window"] for v in live.values()}), "tabs": len(live),
            "pinned": sum(1 for v in live.values() if v["pinned"]), "groups": group_list}


def _sqlite_rows(path: Path, query: str) -> list | None:
    if not path.is_file():
        return None
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        return con.execute(query).fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _count_bookmarks(node) -> int:
    if isinstance(node, dict):
        return (1 if node.get("type") == "url" else 0) + sum(_count_bookmarks(c) for c in node.get("children", []))
    return 0


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def profile_summary(profile: Path) -> dict:
    out: dict = {}
    roots = _json(profile / "Bookmarks").get("roots", {})
    out["bookmarks"] = sum(_count_bookmarks(r) for r in roots.values())
    passwords = 0
    for name in ("Login Data", "Login Data For Account"):
        rows = _sqlite_rows(profile / name, "SELECT COUNT(*) FROM logins")
        passwords += rows[0][0] if rows else 0
    out["passwords"] = passwords
    cookies_db = next((p for p in (profile / "Network" / "Cookies", profile / "Cookies") if p.is_file()), None)
    rows = _sqlite_rows(cookies_db, "SELECT substr(encrypted_value, 1, 3) FROM cookies") if cookies_db else None
    cookies = {"total": 0}
    for (prefix,) in rows or []:
        if isinstance(prefix, str):              # some rows store the value as TEXT, not BLOB
            prefix = prefix.encode("utf-8", "replace")
        key = prefix.decode("ascii", "replace") if prefix and re.match(rb"v\d\d", prefix) else ("empty" if not prefix else "other")
        cookies[key] = cookies.get(key, 0) + 1
        cookies["total"] += 1
    out["cookies"] = cookies
    settings = {}
    for name in ("Preferences", "Secure Preferences"):
        settings.update(_json(profile / name).get("extensions", {}).get("settings", {}))
    out["extensions_enabled"] = sorted(k for k, v in settings.items()
                                       if isinstance(v, dict) and not v.get("disable_reasons") and v.get("state", 1) != 0)
    sessions = sorted((profile / "Sessions").glob("Session_*"),
                      key=lambda p: int(p.name.split("_")[-1]) if p.name.split("_")[-1].isdigit() else 0)
    out["session"] = session_summary(sessions[-1].read_bytes()) if sessions else {"missing": True}
    return out


def snapshot(user_data: Path) -> dict:
    user_data = Path(user_data)
    state = _json(user_data / "Local State")
    os_crypt = state.get("os_crypt", {})
    names = list(state.get("profile", {}).get("info_cache", {}).keys())
    return {"os_crypt": {"dpapi_key": bool(os_crypt.get("encrypted_key")),
                         "app_bound_key": bool(os_crypt.get("app_bound_encrypted_key"))},
            "profiles": {n: profile_summary(user_data / n) for n in names if (user_data / n).is_dir()}}


def compare(before: dict, after: dict) -> list[str]:
    problems = []
    if after["os_crypt"].get("app_bound_key") and not before["os_crypt"].get("app_bound_key"):
        problems.append("Local State gained an app-bound key: cookies re-encrypted this way cannot be read "
                        "by the older version after a rollback")
    if before["os_crypt"].get("dpapi_key") and not after["os_crypt"].get("dpapi_key"):
        problems.append("Local State lost its DPAPI key")
    for name, b in before["profiles"].items():
        a = after["profiles"].get(name)
        if a is None:
            problems.append(f"{name}: profile missing")
            continue
        for key in ("passwords", "bookmarks"):
            if a[key] < b[key]:
                problems.append(f"{name}: {key} {b[key]} -> {a[key]}")
        lost = sorted(set(b["extensions_enabled"]) - set(a["extensions_enabled"]))
        if lost:
            problems.append(f"{name}: extensions no longer enabled: {', '.join(lost)}")
        bc, ac = b["cookies"], a["cookies"]
        if ac["total"] < bc["total"] * (1 - COOKIE_LOSS_TOLERANCE):
            problems.append(f"{name}: cookies {bc['total']} -> {ac['total']} (more than normal expiry)")
        if ac.get("v20", 0) > bc.get("v20", 0):
            problems.append(f"{name}: cookies re-encrypted with the app-bound scheme (v20)")
        bs, as_ = b["session"], a["session"]
        if any(k in bs for k in ("encrypted", "unreadable", "missing")):
            continue
        if any(k in as_ for k in ("encrypted", "unreadable", "missing")):
            problems.append(f"{name}: session not readable after the change")
            continue
        for key in ("windows", "tabs", "pinned"):
            if as_[key] < bs[key]:
                problems.append(f"{name}: open {key} {bs[key]} -> {as_[key]}")
        for g in bs["groups"]:
            if g not in as_["groups"]:
                problems.append(f"{name}: tab group '{g['title']}' (colour {g['color']}, {g['tabs']} tabs) "
                                f"missing or changed")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("user_data", type=Path)
    s.add_argument("--out", required=True, type=Path)
    c = sub.add_parser("compare")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    a = parser.parse_args(argv)
    if a.cmd == "snapshot":
        snap = snapshot(a.user_data)
        a.out.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        for name, p in snap["profiles"].items():
            sess = p["session"]
            tabs = f"{sess.get('windows')} windows, {sess.get('tabs')} tabs, {len(sess.get('groups', []))} groups" \
                if "tabs" in sess else ", ".join(sess)
            print(f"{name}: {tabs}; {p['bookmarks']} bookmarks, {p['passwords']} passwords, "
                  f"{p['cookies']['total']} cookies, {len(p['extensions_enabled'])} extensions enabled")
        return 0
    problems = compare(json.loads(a.before.read_text(encoding="utf-8")), json.loads(a.after.read_text(encoding="utf-8")))
    for p in problems:
        print(p)
    print("profile check: 1:1, nothing lost" if not problems else f"profile check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
