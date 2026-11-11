#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Profile compatibility check: did a new browser version keep a profile 1:1? (ROADMAP Q.7)

`snapshot` summarises a `User Data` folder: per profile the open windows, tabs, pinned tabs and tab
groups (name, colour, tab count) from the newest session file; the number of bookmarks, saved
passwords and cookies (and how cookies are encrypted); and the enabled extensions. It also records
whether `Local State` holds a DPAPI key and an app-bound key.

It never decrypts anything and never writes a secret, a URL or a cookie value: only counts,
extension IDs, tab-group names and key *presence*. It opens databases read-only and refuses to run
while the browser is running (`lockfile` present) or on a folder that is not a `User Data` folder.
Anything it cannot read is recorded as unreadable, never as zero, and `compare` reports it, so an
unreadable "before" can never hide a loss. If a profile that was open at exit kept the same session
file, `compare` reports that the new version did not write one.

It also records whether a profile continues where it left off. One that does not opens a new tab page
at a start, so its earlier tabs are not expected back: `compare` leaves them out and says so.

`compare` lists everything the second snapshot lost: fewer passwords, bookmarks or tabs, missing or
changed tab groups, extensions no longer enabled, a cookie loss beyond normal expiry, or a new
app-bound encryption key (which the older version could not read after a rollback).
    py -3 -I tools/qa/profile_check.py snapshot "<User Data>" --out before.json
    py -3 -I tools/qa/profile_check.py compare before.json after.json
Exit status 1 when compare finds a problem.
"""
import argparse
import json
from collections import Counter
import re
import sqlite3
import struct
import sys
from pathlib import Path

CMD_SET_TAB_WINDOW, CMD_PINNED, CMD_TAB_CLOSED, CMD_WINDOW_CLOSED = 0, 12, 16, 17
CMD_SET_TAB_GROUP, CMD_TAB_GROUP_METADATA2 = 25, 27
COOKIE_LOSS_TOLERANCE = 0.02      # expired cookies are deleted at start-up
NO_NEW_SESSION = "the new version did not write a session"   # a browser without a window never writes one
RESTORES_LAST_SESSION = (1, 6)    # session.restore_on_startup: the last tabs (6: and some pages); else a new tab page or pages


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
    """Rows of a read-only query: [] when the database does not exist, None when it exists but cannot be read."""
    if not path.is_file():
        return []
    con = None
    try:
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
        return con.execute(query).fetchall()
    except sqlite3.Error:
        return None
    finally:
        if con is not None:
            con.close()


def _count_bookmarks(node) -> int:
    if isinstance(node, dict):
        return (1 if node.get("type") == "url" else 0) + sum(_count_bookmarks(c) for c in node.get("children", []))
    return 0


def _json(path: Path) -> dict | None:
    """Parsed JSON: {} when the file does not exist, None when it exists but cannot be read."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


class SnapshotError(RuntimeError):
    pass


def profile_summary(profile: Path) -> dict:
    """Counts for one profile. A value that could not be read is None (or {"unreadable": True}), never 0."""
    out: dict = {}
    bookmarks = _json(profile / "Bookmarks")
    out["bookmarks"] = None if bookmarks is None else sum(_count_bookmarks(r) for r in bookmarks.get("roots", {}).values())
    passwords = 0
    for name in ("Login Data", "Login Data For Account"):
        rows = _sqlite_rows(profile / name, "SELECT COUNT(*) FROM logins")
        if rows is None:
            passwords = None
            break
        passwords += rows[0][0] if rows else 0
    out["passwords"] = passwords
    cookies_db = next((p for p in (profile / "Network" / "Cookies", profile / "Cookies") if p.is_file()), None)
    rows = _sqlite_rows(cookies_db, "SELECT substr(encrypted_value, 1, 3) FROM cookies") if cookies_db else []
    cookies = {"total": 0} if rows is not None else {"unreadable": True}
    for (prefix,) in rows or []:
        if isinstance(prefix, str):              # some rows store the value as TEXT, not BLOB
            prefix = prefix.encode("utf-8", "replace")
        key = prefix.decode("ascii", "replace") if prefix and re.match(rb"v\d\d", prefix) else ("empty" if not prefix else "other")
        cookies[key] = cookies.get(key, 0) + 1
        cookies["total"] += 1
    out["cookies"] = cookies
    settings, readable, startup = {}, True, None
    for name in ("Preferences", "Secure Preferences"):          # the second is the protected one, and wins
        prefs = _json(profile / name)
        if prefs is None:
            readable = False
            break
        settings.update(prefs.get("extensions", {}).get("settings", {}))
        session = prefs.get("session")
        if isinstance(session, dict) and "restore_on_startup" in session:
            startup = session["restore_on_startup"]
    out["extensions_enabled"] = sorted(k for k, v in settings.items() if isinstance(v, dict)
                                       and not v.get("disable_reasons") and v.get("state", 1) != 0) if readable else None
    # Does a start bring the last tabs back? Without the setting a browser opens a new tab page.
    out["restores_session"] = (startup in RESTORES_LAST_SESSION) if readable else None
    sessions = sorted((profile / "Sessions").glob("Session_*"),
                      key=lambda p: int(p.name.split("_")[-1]) if p.name.split("_")[-1].isdigit() else 0)
    out["session"] = session_summary(sessions[-1].read_bytes()) if sessions else {"missing": True}
    out["session_file"] = {"name": sessions[-1].name, "mtime": sessions[-1].stat().st_mtime} if sessions else None
    return out


def snapshot(user_data: Path) -> dict:
    """Summarise a closed browser's `User Data` folder. Refuses a running browser or a wrong folder."""
    user_data = Path(user_data)
    if (user_data / "lockfile").exists():
        raise SnapshotError(f"{user_data}: the browser is running (lockfile present); close it completely first")
    state = _json(user_data / "Local State")
    if not (user_data / "Local State").is_file() or state is None:
        raise SnapshotError(f"{user_data}: no readable 'Local State'; pass the browser's 'User Data' folder")
    os_crypt = state.get("os_crypt", {})
    names = [n for n in state.get("profile", {}).get("info_cache", {}) if (user_data / n).is_dir()]
    if not names:
        raise SnapshotError(f"{user_data}: no profile folders listed in 'Local State'")
    return {"os_crypt": {"dpapi_key": bool(os_crypt.get("encrypted_key")),
                         "app_bound_key": bool(os_crypt.get("app_bound_encrypted_key"))},
            "last_active_profiles": list(state.get("profile", {}).get("last_active_profiles", [])),
            "profiles": {n: profile_summary(user_data / n) for n in names}}


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
        for key in ("passwords", "bookmarks", "extensions_enabled"):
            for side, snap in (("before", b), ("after", a)):
                if snap.get(key) is None:
                    problems.append(f"{name}: {key} unreadable {side}, so nothing can be verified")
        for key in ("passwords", "bookmarks"):
            if b.get(key) is not None and a.get(key) is not None and a[key] < b[key]:
                problems.append(f"{name}: {key} {b[key]} -> {a[key]}")
        if b.get("extensions_enabled") is not None and a.get("extensions_enabled") is not None:
            lost = sorted(set(b["extensions_enabled"]) - set(a["extensions_enabled"]))
            if lost:
                problems.append(f"{name}: extensions no longer enabled: {', '.join(lost)}")
        bc, ac = b["cookies"], a["cookies"]
        if "unreadable" in bc or "unreadable" in ac:
            problems.append(f"{name}: cookies unreadable {'before' if 'unreadable' in bc else 'after'}")
        else:
            if ac["total"] < bc["total"] * (1 - COOKIE_LOSS_TOLERANCE):
                problems.append(f"{name}: cookies {bc['total']} -> {ac['total']} (more than normal expiry)")
            if ac.get("v20", 0) > bc.get("v20", 0):
                problems.append(f"{name}: cookies re-encrypted with the app-bound scheme (v20)")
        problems += _compare_sessions(name, b, a, name in before.get("last_active_profiles", []))
    return problems


def notes(before: dict) -> list[str]:
    """What `compare` leaves out for a good reason, said aloud so that nobody takes it for checked."""
    return [f"{name}: tabs and tab groups not compared: this profile does not continue where it left off, "
            f"so a start opens a new tab page and the earlier tabs are not expected back"
            for name, p in before["profiles"].items()
            if p.get("restores_session") is False and p.get("session", {}).get("tabs")]


def _compare_sessions(name: str, b: dict, a: dict, was_open: bool) -> list[str]:
    if b.get("restores_session") is False:
        return []                                  # a start opens a new tab page: see notes()
    bs, as_ = b["session"], a["session"]
    if "missing" in bs:
        return []                                  # no session before: no tabs that could be lost
    if "encrypted" in bs or "unreadable" in bs:
        return [f"{name}: session unreadable before, so tabs and tab groups cannot be verified"]
    if any(k in as_ for k in ("encrypted", "unreadable", "missing")):
        return [f"{name}: session not readable after the change"]
    problems = []
    bf, af = b.get("session_file"), a.get("session_file")
    if was_open and bf and af and af["name"] == bf["name"] and af["mtime"] <= bf["mtime"]:
        problems.append(f"{name}: {NO_NEW_SESSION} (same file {af['name']}), "
                        f"so this compares the old session with itself")
    for key in ("windows", "tabs", "pinned"):
        if as_[key] < bs[key]:
            problems.append(f"{name}: open {key} {bs[key]} -> {as_[key]}")
    key = lambda g: (g["title"], g["color"], g["tabs"])
    after_groups = Counter(key(g) for g in as_["groups"])
    for (title, color, tabs), count in Counter(key(g) for g in bs["groups"]).items():
        if after_groups[(title, color, tabs)] < count:
            problems.append(f"{name}: tab group '{title}' (colour {color}, {tabs} tabs) missing or changed "
                            f"({count} before, {after_groups[(title, color, tabs)]} after)")
    return problems


def summary_line(name: str, p: dict) -> str:
    """One profile of a snapshot in a line: counts only."""
    sess = p["session"]
    tabs = f"{sess.get('windows')} windows, {sess.get('tabs')} tabs, {len(sess.get('groups', []))} groups" \
        if "tabs" in sess else ", ".join(sess)
    ext = p["extensions_enabled"]
    return (f"{name}: {tabs}; {p['bookmarks']} bookmarks, {p['passwords']} passwords, "
            f"{p['cookies'].get('total', 'unreadable')} cookies, "
            f"{'unreadable' if ext is None else len(ext)} extensions enabled")


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
        try:
            snap = snapshot(a.user_data)
        except SnapshotError as exc:
            print(f"profile check: {exc}")
            return 1
        a.out.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        for name, p in snap["profiles"].items():
            print(summary_line(name, p))
        return 0
    before = json.loads(a.before.read_text(encoding="utf-8"))
    problems = compare(before, json.loads(a.after.read_text(encoding="utf-8")))
    for p in problems + notes(before):
        print(p)
    print("profile check: 1:1 on every checked item" if not problems else f"profile check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
