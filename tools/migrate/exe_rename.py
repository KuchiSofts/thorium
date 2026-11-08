#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Move a Thoron install made before the program file rename (thorium.exe -> thoron.exe) over (ROADMAP P2.20).

Run it once, after installing a build that has `thoron.exe`, with Thoron closed. It:
- retargets shortcuts (desktop, Start menu, taskbar pins) from `<Thoron>\\Application\\thorium.exe` to
  `thoron.exe`, keeping their arguments (for example a profile);
- rewrites per-user registry values that still name the old file (ProgIDs, Open-with, uninstall entry);
- gives the `App Paths\\thorium.exe` entry back to Thorium, which an earlier Thoron install took over
  (or removes it when Thorium is not installed);
- moves the leftover Thorium-named files out of Thoron's folder (`thorium.exe`, `thor_ver`, icons).
It never reads or changes `User Data`, Thorium's folder, or any Thorium registry entry other than
restoring `App Paths\\thorium.exe` to Thorium's own path. Every changed value, shortcut and file is
saved first in a new backup folder, and `restore` puts everything back.

    py -3 -I tools/migrate/exe_rename.py plan
    py -3 -I tools/migrate/exe_rename.py apply --backup-dir C:\\Users\\<you>\\ThoriumBackups\\<stamp>_exe-rename
    py -3 -I tools/migrate/exe_rename.py restore --backup-dir <same folder>
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OLD_EXE = "thorium.exe"
NEW_EXE = "thoron.exe"
TOP_LEFTOVERS = (OLD_EXE, "thor_ver")
VERSION_LEFTOVERS = ("thorium.ico", "thorium.svg", "thorium_shell.ico", "thorium_shell.exe")
APP_PATHS = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
LEGACY_APP_PATHS_KEY = APP_PATHS + "\\" + OLD_EXE
SCAN_ROOTS = (r"Software\Classes", r"Software\Clients", r"Software\Microsoft\Windows\CurrentVersion\Uninstall", APP_PATHS)
STRING_KINDS = (1, 2)   # REG_SZ, REG_EXPAND_SZ
CLOUD_NAMES = ("google drive", "my drive", "onedrive", "dropbox", "icloud drive", "iclouddrive")
PLAN_FILE = "plan.json"


class MigrationRefused(RuntimeError):
    pass


def _norm(path) -> str:
    return os.path.normcase(os.path.normpath(str(path).strip().strip('"')))


def _replace_path(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), lambda _: new, text, flags=re.IGNORECASE)


def _inside(path, folder) -> bool:
    p, f = _norm(path), _norm(folder)
    return p == f or p.startswith(f.rstrip("\\/") + os.sep)


def plan(app_dir: Path, thorium_app_dir: Path, backend, shortcut_dirs) -> dict:
    """What would change, without changing anything."""
    app_dir, thorium_app_dir = Path(app_dir), Path(thorium_app_dir)
    if app_dir.name.lower() != "application" or app_dir.parent.name.lower() != "thoron":
        raise MigrationRefused(f"{app_dir} is not a Thoron program folder (...\\Thoron\\Application)")
    if _inside(app_dir, thorium_app_dir.parent) or _inside(thorium_app_dir, app_dir.parent):
        raise MigrationRefused("the Thoron and Thorium folders overlap")
    old, new = app_dir / OLD_EXE, app_dir / NEW_EXE
    if not new.is_file():
        raise MigrationRefused(f"{new} is missing: install the build with {NEW_EXE} first")
    running = [p for p in backend.processes() if p and _inside(p, app_dir)]
    if running:
        raise MigrationRefused("Thoron is running; close it completely first: " + ", ".join(sorted(set(running))))

    shortcuts = []
    for link in backend.shortcuts([str(d) for d in shortcut_dirs]):
        if _norm(link["target"]) != _norm(old):
            continue
        icon = link.get("icon") or ""
        icon_path, _, index = icon.rpartition(",") if "," in icon else (icon, "", "")
        new_icon = (str(new) + ("," + index if index else "")) if icon_path and _norm(icon_path) == _norm(old) else icon
        working_dir = link.get("working_dir") or ""
        shortcuts.append({"path": link["path"],
                          "old": {"target": link["target"], "working_dir": working_dir, "icon": icon},
                          "new": {"target": str(new), "working_dir": working_dir, "icon": new_icon}})

    values = []
    for key, name, value, kind in backend.read_values(SCAN_ROOTS):
        if _inside(key, LEGACY_APP_PATHS_KEY) or kind not in STRING_KINDS or not isinstance(value, str):
            continue
        if str(old).lower() in value.lower():
            values.append({"key": key, "name": name, "kind": kind, "old": value,
                           "new": _replace_path(value, str(old), str(new))})

    current = backend.read_key(LEGACY_APP_PATHS_KEY)
    app_paths = {"action": "keep", "old": current, "new": current}
    if current and _norm(current.get("", ("",))[0]) == _norm(old):
        thorium_exe = thorium_app_dir / OLD_EXE
        if thorium_exe.is_file():
            app_paths = {"action": "restore", "old": current,
                         "new": {"": (str(thorium_exe), 1), "Path": (str(thorium_app_dir), 1)}}
        else:
            app_paths = {"action": "delete", "old": current, "new": None}

    files = [str(app_dir / n) for n in TOP_LEFTOVERS if (app_dir / n).is_file()]
    for version_dir in sorted(p for p in app_dir.iterdir() if p.is_dir()):
        files += [str(version_dir / n) for n in VERSION_LEFTOVERS if (version_dir / n).is_file()]
    return {"app_dir": str(app_dir), "shortcuts": shortcuts, "values": values, "app_paths": app_paths, "files": files}


def _check_backup_dir(backup_dir: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    resolved = Path(os.path.abspath(backup_dir))
    if resolved.exists():
        raise MigrationRefused(f"backup folder {resolved} already exists; use a new one")
    if _inside(resolved, repo):
        raise MigrationRefused("the backup folder must not be inside the repository")
    parts = [p.lower() for p in resolved.parts]
    clouds = [os.environ.get(v) for v in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
    if any(p in CLOUD_NAMES or p.startswith("onedrive") for p in parts) or any(c and _inside(resolved, c) for c in clouds):
        raise MigrationRefused("the backup folder must be on a local drive that is not cloud-synced")


def apply(the_plan: dict, backend, backup_dir: Path) -> None:
    """Save everything the plan changes into a new backup folder, then make the changes."""
    backup_dir = Path(backup_dir)
    _check_backup_dir(backup_dir)
    backup_dir.mkdir(parents=True)
    moved = [{"from": f, "to": str(backup_dir / "files" / f"{i}_{Path(f).name}")} for i, f in enumerate(the_plan["files"])]
    record = dict(the_plan, moved=moved)
    (backup_dir / PLAN_FILE).write_text(json.dumps(record, indent=1), encoding="utf-8")
    if moved:
        (backup_dir / "files").mkdir()
    for m in moved:
        shutil.move(m["from"], m["to"])
    for v in the_plan["values"]:
        backend.set_value(v["key"], v["name"], v["new"], v["kind"])
    ap = the_plan["app_paths"]
    if ap["action"] == "restore":
        backend.write_key(LEGACY_APP_PATHS_KEY, {k: tuple(v) for k, v in ap["new"].items()})
    elif ap["action"] == "delete":
        backend.delete_key(LEGACY_APP_PATHS_KEY)
    for s in the_plan["shortcuts"]:
        backend.set_shortcut(s["path"], s["new"]["target"], s["new"]["working_dir"], s["new"]["icon"])


def restore(backup_dir: Path, backend) -> None:
    """Undo an apply from its backup folder."""
    record = json.loads((Path(backup_dir) / PLAN_FILE).read_text(encoding="utf-8"))
    for s in record["shortcuts"]:
        backend.set_shortcut(s["path"], s["old"]["target"], s["old"]["working_dir"], s["old"]["icon"])
    ap = record["app_paths"]
    if ap["action"] in ("restore", "delete"):
        backend.write_key(LEGACY_APP_PATHS_KEY, {k: tuple(v) for k, v in ap["old"].items()})
    for v in record["values"]:
        backend.set_value(v["key"], v["name"], v["old"], v["kind"])
    for m in record["moved"]:
        if Path(m["to"]).is_file() and not Path(m["from"]).exists():
            shutil.move(m["to"], m["from"])


class WindowsBackend:
    """Per-user registry (winreg) and .lnk files (WScript.Shell through PowerShell)."""

    def __init__(self):
        import winreg
        self.winreg = winreg

    # --- processes
    def processes(self):
        out = self._ps("Get-CimInstance Win32_Process | ForEach-Object { $_.ExecutablePath } | ConvertTo-Json -Compress", {})
        return [p for p in (out if isinstance(out, list) else [out]) if p]

    # --- registry
    def _walk(self, key_path):
        wr = self.winreg
        try:
            key = wr.OpenKey(wr.HKEY_CURRENT_USER, key_path, 0, wr.KEY_READ)
        except OSError:
            return
        with key:
            i = 0
            while True:
                try:
                    name, value, kind = wr.EnumValue(key, i)
                except OSError:
                    break
                yield key_path, name, value, kind
                i += 1
            subs, j = [], 0
            while True:
                try:
                    subs.append(wr.EnumKey(key, j))
                except OSError:
                    break
                j += 1
        for sub in subs:
            yield from self._walk(key_path + "\\" + sub)

    def read_values(self, roots):
        return [row for root in roots for row in self._walk(root)]

    def read_key(self, key_path):
        rows = [(n, v, k) for p, n, v, k in self._walk(key_path) if p == key_path]
        if not rows and not self._exists(key_path):
            return None
        return {n: (v, k) for n, v, k in rows}

    def _exists(self, key_path):
        try:
            self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, key_path).Close()
            return True
        except OSError:
            return False

    def set_value(self, key_path, name, value, kind):
        wr = self.winreg
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, wr.KEY_SET_VALUE) as key:
            wr.SetValueEx(key, name, 0, kind, value)

    def write_key(self, key_path, values):
        wr = self.winreg
        current = self.read_key(key_path) or {}
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, wr.KEY_SET_VALUE) as key:
            for name in set(current) - set(values):
                wr.DeleteValue(key, name)
            for name, (value, kind) in values.items():
                wr.SetValueEx(key, name, 0, kind, value)

    def delete_key(self, key_path):
        self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, key_path)   # fails if it has subkeys: never forced

    # --- shortcuts
    def _ps(self, script, data):
        with tempfile.TemporaryDirectory(prefix="thoron-lnk-") as tmp:
            arg = Path(tmp) / "in.json"
            arg.write_text(json.dumps(data), encoding="utf-8")
            full = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                    "$in = Get-Content -Raw -Encoding UTF8 $env:THORON_LNK_IN | ConvertFrom-Json; " + script)
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", full],
                                  capture_output=True, encoding="utf-8", errors="replace",
                                  env=dict(os.environ, THORON_LNK_IN=str(arg)))
        if proc.returncode != 0:
            raise RuntimeError(f"PowerShell failed: {proc.stderr.strip()[:500]}")
        text = proc.stdout.strip()
        return json.loads(text) if text else []

    def shortcuts(self, dirs):
        script = ("$sh = New-Object -ComObject WScript.Shell; "
                  "$r = @(foreach ($d in $in.dirs) { if (Test-Path -LiteralPath $d) { "
                  "Get-ChildItem -LiteralPath $d -Recurse -Filter *.lnk -File -ErrorAction SilentlyContinue | ForEach-Object { "
                  "$l = $sh.CreateShortcut($_.FullName); [pscustomobject]@{path=$_.FullName; target=$l.TargetPath; "
                  "arguments=$l.Arguments; working_dir=$l.WorkingDirectory; icon=$l.IconLocation} } } }); "
                  "ConvertTo-Json -Compress -InputObject $r")
        out = self._ps(script, {"dirs": list(dirs)})
        return out if isinstance(out, list) else [out]

    def set_shortcut(self, path, target, working_dir, icon):
        script = ("$sh = New-Object -ComObject WScript.Shell; $l = $sh.CreateShortcut($in.path); "
                  "$l.TargetPath = $in.target; $l.WorkingDirectory = $in.working_dir; "
                  "if ($in.icon) { $l.IconLocation = $in.icon }; $l.Save()")
        self._ps(script, {"path": path, "target": target, "working_dir": working_dir, "icon": icon})

    def create_shortcut_for_test(self, path, target, arguments, working_dir):
        script = ("$sh = New-Object -ComObject WScript.Shell; $l = $sh.CreateShortcut($in.path); "
                  "$l.TargetPath = $in.target; $l.Arguments = $in.arguments; $l.WorkingDirectory = $in.working_dir; $l.Save()")
        self._ps(script, {"path": path, "target": target, "arguments": arguments, "working_dir": working_dir})

    def default_shortcut_dirs(self):
        appdata = os.environ["APPDATA"]
        desktop = self._ps("ConvertTo-Json -Compress -InputObject ([Environment]::GetFolderPath('Desktop'))", {})
        return [desktop, os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"),
                os.path.join(appdata, r"Microsoft\Internet Explorer\Quick Launch")]


def _summary(p: dict) -> str:
    lines = [f"Thoron folder: {p['app_dir']}", f"Shortcuts to retarget: {len(p['shortcuts'])}"]
    lines += [f"  {s['path']}" for s in p["shortcuts"]]
    lines.append(f"Registry values to update: {len(p['values'])}")
    lines += [f"  HKCU\\{v['key']} [{v['name'] or '(default)'}]" for v in p["values"]]
    lines.append(f"App Paths\\{OLD_EXE}: {p['app_paths']['action']}")
    lines.append(f"Leftover files to move into the backup: {len(p['files'])}")
    lines += [f"  {f}" for f in p["files"]]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("plan", "apply", "restore"))
    local = os.environ.get("LOCALAPPDATA", "")
    parser.add_argument("--thoron", type=Path, default=Path(local) / "Thoron" / "Application")
    parser.add_argument("--thorium", type=Path, default=Path(local) / "Thorium" / "Application")
    parser.add_argument("--backup-dir", type=Path)
    a = parser.parse_args(argv)
    backend = WindowsBackend()
    try:
        if a.action == "restore":
            if not a.backup_dir:
                parser.error("restore needs --backup-dir")
            restore(a.backup_dir, backend)
            print(f"restored from {a.backup_dir}")
            return 0
        the_plan = plan(a.thoron, a.thorium, backend, backend.default_shortcut_dirs())
        print(_summary(the_plan))
        if a.action == "apply":
            if not a.backup_dir:
                parser.error("apply needs --backup-dir")
            apply(the_plan, backend, a.backup_dir)
            print(f"done; backup and undo record in {a.backup_dir}")
        return 0
    except MigrationRefused as exc:
        print(f"refused, nothing changed: {exc}")
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
