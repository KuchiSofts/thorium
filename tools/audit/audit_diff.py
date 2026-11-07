#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Security audit of everything a revision ADDS relative to a base revision.

Run before every upstream merge and before every release:
    py -3 -I tools/audit/audit_diff.py REPO BASE TARGET [--section files|hosts|patterns|security|all]
                                       [--json] [--strict]
--strict exits 1 when non-image binaries, submodule changes, .gitmodules changes or high-risk
patterns are added; every such finding needs a human review.

Robustness (hostile input is expected here): the file list comes from `git diff --raw -z`, file
contents are read by blob id (never by path, never through the user's diff/textconv settings),
added lines of modified files come from a blob-to-blob diff parsed by hunk line counts, and text is
split on "\\n" only.
"""
import argparse
import functools
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# Huge, non-executable translation data; skipped to keep reports readable.
SKIP_TEXT_RE = re.compile(r"\.xtb$|/translations/")
IMAGE_MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",), ".ico": (b"\x00\x00\x01\x00",), ".icns": (b"icns",),
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",), ".webp": (b"RIFF",), ".xcf": (b"gimp xcf",),
}
SUBMODULE_MODE = "160000"
REGULAR_OR_LINK = ("100644", "100755", "120000")

BENIGN_HOSTS_RE = re.compile(
    r"^example\.(com|org|net)$|(^|\.)(chromium\.org|googlesource\.com|google\.com|googleapis\.com|"
    r"gstatic\.com|docs\.github\.com|thorium\.rocks|w3\.org|mozilla\.org|apache\.org|"
    r"gnu\.org|freedesktop\.org|microsoft\.com|apple\.com|chrome\.com|youtube\.com|wikipedia\.org|"
    r"llvm\.org|creativecommons\.org|opensource\.org|python\.org|kernel\.org|debian\.org|ubuntu\.com|"
    r"fedoraproject\.org|archlinux\.org|android\.com|crbug\.com|chromestatus\.com|webkit\.org|"
    r"whatwg\.org|ietf\.org|unicode\.org)$|^(localhost|127\.0\.0\.1)$")
# Hosts where anyone can publish content: reported with the owner/bucket unless the owner is trusted.
GITHUB_CONTENT_HOSTS = {"github.com", "raw.githubusercontent.com", "objects.githubusercontent.com",
                        "gist.github.com", "gist.githubusercontent.com", "codeload.github.com",
                        "user-images.githubusercontent.com"}
TRUSTED_GITHUB_OWNERS = {"alex313031", "gz83", "hocheung-chromium", "kuchisofts", "gorhill", "chromium",
                         "google", "ungoogled-software", "bromite", "uazo", "iridium-browser",
                         "grapheneos", "libjxl"}
GOOGLE_STORAGE_RE = re.compile(r"(^|\.)(storage|commondatastorage)\.googleapis\.com$")
GOOGLE_FILE_HOSTS = {"docs.google.com", "drive.google.com", "sites.google.com"}

URL_RE = re.compile(r"(?i)\b(?:https?|ftp|wss?)://([^\s\"'<>()\\`]+)")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
NON_PUBLIC_IP_RE = re.compile(r"^(127\.|0\.|10\.|192\.168\.|255\.|1\.0\.0\.|2\.0\.0\.|8\.8\.|1\.1\.1\.1|9\.9\.9\.9)")
VERSION_CONTEXT_RE = re.compile(r"version|VERSION|\.\d+\.\d+\.\d+\.\d")

PATTERNS = {
    "remote_exec": r"(?i)\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+(-\S+\s+)*)?(ba|z|da|k)?sh\b|\b(ba|z)?sh\s+<\(\s*(curl|wget)\b|"
                   r"\b(iex|invoke-expression)\b|\b(irm|iwr|invoke-restmethod|invoke-webrequest)\b|"
                   r"\.download(string|file|data)\s*\(|start-bitstransfer|certutil(\.exe)?\s+-urlcache|"
                   r"\bbitsadmin\b|\bmshta(\.exe)?\b|regsvr32[^\n]*/i:https?",
    "encoded_payload": r"(?i)frombase64string|base64\s+(-d|--decode)\b|\batob\(|[A-Za-z0-9+/]{200,}={0,2}",
    "dynamic_code": r"\beval\s*\(|\bnew Function\(|\bexec\s*\(\s*(compile|base64)|__import__\(|"
                    r"shell\s*=\s*True|\bos\.system\(|"
                    r"(?i:powershell(\.exe)?[^\n]*\s-(e|ec|enc|encodedcommand)\s+[A-Za-z0-9+/=]{20,})",
    "persistence": r"(?i)currentversion\\+run(once)?\b|\bschtasks(\.exe)?\b|register-scheduledtask|"
                   r"new-scheduledtask|\bcrontab\b|/etc/cron|systemctl\s+(--user\s+)?enable|launchagents|"
                   r"launchdaemons|(~|\$home|\$\{home\})/\.(bashrc|profile|bash_profile|zshrc)|"
                   r"/etc/profile\.d/|\.config/autostart|/etc/sudoers|sudoers\.d|shell:startup",
    "security_disabled": r"--no-sandbox|disable-web-security|--disable-site-isolation|ignore-certificate-errors|"
                         r"allow-running-insecure-content|disable-features=[^\"']*(SafeBrowsing|SitePerProcess|IsolateOrigins)|"
                         r"--remote-debugging-(port|address)|unsafely-treat-insecure",
    "credentials": r"AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY|client_secret|"
                   r"password\s*=\s*['\"][^'\"]+|token\s*=\s*['\"][A-Za-z0-9]{16,}",
    "mining_telemetry": r"(?i)coinhive|cryptonight|xmrig|stratum\+tcp|\bmonero\b|mixpanel|segment\.io|"
                        r"api\.amplitude|sentry\.io|posthog|telemetry\.[a-z]",
    "self_update": r"(?i)(update|download)(er)?_?(url|server|endpoint)|\bomaha\b|kUpdateURL",
}
PATTERN_RES = {name: re.compile(rx) for name, rx in PATTERNS.items()}
STRICT_CATEGORIES = ("remote_exec", "dynamic_code", "persistence", "security_disabled", "mining_telemetry")

SECURITY_RE = re.compile(
    r"(?i)(SafeBrowsing|SitePerProcess|SiteIsolation|IsolateOrigins|StrictOrigin|HttpsUpgrade|HttpsFirst|"
    r"MixedContent|CertificateTransparency|CertVerifier|kNoSandbox|sandbox_type|SandboxType|V8Sandbox|jitless|"
    r"kWebSecurity|ContentSecurityPolicy|CORS|SameSite|ThirdPartyCookie|PrivateNetworkAccess|Spectre|"
    r"ControlFlowGuard|cfg_guards|is_cfi|enable_cdm_host_verification|DeviceBoundSession|PasswordProtection|"
    r"DownloadProtection|kAllowInsecure|EnableDangerousDownload)")
HUNK_RE = re.compile(rb"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def _git(repo: str, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "-C", repo, *args], input=data, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").rstrip("\r")


def _changes(repo: str, base: str, target: str) -> list[tuple[str, str, str, str, str, str]]:
    """(path, status, old_mode, new_mode, old_sha, new_sha) from `git diff --raw -z`."""
    out = _git(repo, "diff", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-ext-diff", base, target)
    parts, changes, i = out.split(b"\0"), [], 0
    while i + 1 < len(parts):
        meta = parts[i].decode("ascii", "replace")
        if meta.startswith(":"):
            old_mode, new_mode, old_sha, new_sha, status = meta[1:].split()[:5]
            changes.append((parts[i + 1].decode("utf-8", "replace"), status[0], old_mode, new_mode, old_sha, new_sha))
            i += 2
        else:
            i += 1
    return changes


def _read_blobs(repo: str, shas: list[str]) -> dict[str, bytes]:
    if not shas:
        return {}
    out = _git(repo, "cat-file", "--batch", data=("\n".join(shas) + "\n").encode("ascii"))
    blobs, pos = {}, 0
    for sha in shas:
        newline = out.index(b"\n", pos)
        header = out[pos:newline].split()
        if len(header) < 3 or header[1] == b"missing":
            raise RuntimeError(f"blob {sha} missing")
        size = int(header[2])
        blobs[sha] = out[newline + 1:newline + 1 + size]
        pos = newline + 1 + size + 1
    return blobs


def _added_from_patch(patch: bytes) -> list[str]:
    """Added lines of a unified diff, consuming exactly the line counts each hunk header declares."""
    lines, added, i = patch.split(b"\n"), [], 0
    while i < len(lines):
        match = HUNK_RE.match(lines[i])
        i += 1
        if not match:
            continue
        old_left = int(match.group(1)) if match.group(1) is not None else 1
        new_left = int(match.group(2)) if match.group(2) is not None else 1
        while (old_left > 0 or new_left > 0) and i < len(lines):
            line = lines[i]
            i += 1
            if line.startswith(b"\\"):
                continue
            if line.startswith(b"+"):
                new_left -= 1
                added.append(_decode(line[1:]))
            elif line.startswith(b"-"):
                old_left -= 1
            else:
                old_left -= 1
                new_left -= 1
    return added


def _blob_diff(repo: str, old_sha: str, new_sha: str) -> list[str]:
    return _added_from_patch(_git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv",
                                  old_sha, new_sha))


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def _is_genuine_image(path: str, data: bytes) -> bool:
    ext = path[path.rfind("."):].lower() if "." in path else ""
    magics = IMAGE_MAGIC.get(ext)
    if not magics or not any(data.startswith(m) for m in magics):
        return False
    return ext != ".webp" or data[8:12] == b"WEBP"


def _analyze(repo: str, base: str, target: str):
    # Resolve refs first so the cache can never serve results for a ref that has since moved.
    resolved = []
    for ref in (base, target):
        if ref.startswith("-"):
            raise ValueError(f"refusing option-like revision {ref!r}")
        resolved.append(_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode("ascii").strip())
    return _analyze_commits(repo, *resolved)


@functools.lru_cache(maxsize=8)
def _analyze_commits(repo: str, base: str, target: str):
    changes = _changes(repo, base, target)
    submodules = [(p, o, n) for p, s, om, nm, o, n in changes if SUBMODULE_MODE in (om, nm)]
    content = [c for c in changes if c[1] in ("A", "M", "T") and c[3] in REGULAR_OR_LINK]
    blobs = _read_blobs(repo, sorted({c[5] for c in content}))
    added: dict[str, list[str]] = {}
    binaries: list[tuple[str, str, int]] = []
    pending_diffs = []
    for path, status, old_mode, _new_mode, old_sha, new_sha in content:
        data = blobs[new_sha]
        if _is_binary(data):
            if not _is_genuine_image(path, data):
                binaries.append((path, status, len(data)))
            continue
        if SKIP_TEXT_RE.search(path):
            continue
        if status == "M" and old_mode in REGULAR_OR_LINK:
            pending_diffs.append((path, old_sha, new_sha))
        else:  # added, or type change: every line is new
            added[path] = [_decode(line) for line in data.split(b"\n")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for path, lines in zip([d[0] for d in pending_diffs],
                               pool.map(lambda d: _blob_diff(repo, d[1], d[2]), pending_diffs)):
            if lines:
                added[path] = lines
    gitmodules_changed = any(c[0] == ".gitmodules" and c[1] in ("A", "M", "T") for c in changes)
    return added, binaries, submodules, gitmodules_changed


def collect_added_lines(repo: str, base: str, target: str) -> dict[str, list[str]]:
    return _analyze(repo, base, target)[0]


def find_binaries(repo: str, base: str, target: str) -> list[tuple[str, str, int]]:
    return list(_analyze(repo, base, target)[1])


def find_submodules(repo: str, base: str, target: str) -> list[tuple[str, str, str]]:
    return list(_analyze(repo, base, target)[2])


def _endpoint_key(host: str, url_path: str) -> str | None:
    first = url_path.strip("/").split("/", 1)[0]
    if host in GITHUB_CONTENT_HOSTS:
        return None if first.lower() in TRUSTED_GITHUB_OWNERS else (f"{host}/{first}" if first else host)
    if GOOGLE_STORAGE_RE.search(host):
        return f"{host}/{first}" if first else host
    if host in GOOGLE_FILE_HOSTS:
        return host
    if "." not in host or BENIGN_HOSTS_RE.search(host):
        return None
    return host


def find_endpoints(added: dict[str, list[str]]) -> dict[str, set[str]]:
    hosts: dict[str, set[str]] = {}
    for path, lines in added.items():
        for text in lines:
            for match in URL_RE.finditer(text):
                try:
                    parsed = urlparse("http://" + match.group(1))
                    host = (parsed.hostname or "").lower()
                except ValueError:
                    continue
                key = _endpoint_key(host, parsed.path)
                if key:
                    hosts.setdefault(key, set()).add(path)
            if VERSION_CONTEXT_RE.search(text):
                continue
            for match in IP_RE.finditer(text):
                ip = match.group(0)
                if all(int(part) < 256 for part in ip.split(".")) and not NON_PUBLIC_IP_RE.match(ip):
                    hosts.setdefault("IP " + ip, set()).add(path)
    return hosts


def find_patterns(added: dict[str, list[str]]) -> dict[str, list[tuple[str, str]]]:
    hits: dict[str, list[tuple[str, str]]] = {name: [] for name in PATTERNS}
    for path, lines in added.items():
        for text in lines:
            for name, rx in PATTERN_RES.items():
                if rx.search(text):
                    hits[name].append((path, text.strip()))
    return hits


def find_security_changes(added: dict[str, list[str]]) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}
    for path, lines in added.items():
        for text in lines:
            if SECURITY_RE.search(text):
                changes.setdefault(path, []).append(text.strip())
    return changes


def _print_report(section, binaries, submodules, gitmodules_changed, endpoints, patterns, security):
    if section in ("files", "all"):
        print(f"=== ADDED/MODIFIED NON-IMAGE BINARIES ({len(binaries)})")
        for path, st, size in binaries:
            print(f"  [{st}] {path}  ({size:,} bytes)")
        print(f"\n=== SUBMODULE CHANGES ({len(submodules)}){'  + .gitmodules CHANGED' if gitmodules_changed else ''}")
        for path, old, new in submodules:
            print(f"  {path}: {old[:12]} -> {new[:12]}")
    if section in ("hosts", "all"):
        print(f"\n=== NETWORK ENDPOINTS IN ADDED LINES ({len(endpoints)})")
        for host, files in sorted(endpoints.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"  {host:<45} in {len(files)} file(s): {sorted(files)[:3]}")
    if section in ("patterns", "all"):
        print("\n=== SUSPICIOUS PATTERNS IN ADDED LINES")
        for name, hits in patterns.items():
            print(f"  [{name}] {len(hits)} hit(s)")
            for path, text in hits[:12]:
                print(f"    {path}: {text[:160]}")
    if section in ("security", "all"):
        print(f"\n=== SECURITY-FEATURE CHANGES ({len(security)} file(s))")
        for path, lines in sorted(security.items(), key=lambda kv: -len(kv[1])):
            print(f"  {path}  ({len(lines)} lines)")
            for text in lines[:6]:
                print(f"      {text[:150]}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("base")
    parser.add_argument("target")
    parser.add_argument("--section", choices=["files", "hosts", "patterns", "security", "all"], default="all")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on binaries, submodule/.gitmodules changes or high-risk patterns")
    args = parser.parse_args(argv)

    added, binaries, submodules, gitmodules_changed = _analyze(args.repo, args.base, args.target)
    endpoints = find_endpoints(added)
    patterns = find_patterns(added)
    security = find_security_changes(added)

    if args.json:
        print(json.dumps({
            "binaries": [{"path": p, "status": s, "size": n} for p, s, n in binaries],
            "submodules": [{"path": p, "old": o, "new": n} for p, o, n in submodules],
            "gitmodules_changed": gitmodules_changed,
            "endpoints": {h: sorted(f) for h, f in endpoints.items()},
            "patterns": {k: [{"path": p, "line": t} for p, t in v] for k, v in patterns.items()},
            "security": security,
        }, indent=1))
    else:
        _print_report(args.section, binaries, submodules, gitmodules_changed, endpoints, patterns, security)

    if args.strict and (binaries or submodules or gitmodules_changed
                        or any(patterns[c] for c in STRICT_CATEGORIES)):
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
