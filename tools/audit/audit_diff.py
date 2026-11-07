#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Security audit of everything a revision ADDS relative to a base revision.

Run before every upstream merge and before every release:
    py -3 -I tools/audit/audit_diff.py REPO BASE TARGET [--section files|hosts|patterns|security|all]
                                       [--json] [--strict]
--strict exits 1 when non-image binaries or high-risk patterns are added.
"""
import argparse
import json
import re
import subprocess
import sys
from urllib.parse import urlparse

SKIP_RE = re.compile(r"\.xtb$|/translations/|\.png$|\.svg$|\.icon$")
IMAGE_RE = re.compile(r"\.(png|ico|icns|svg|webp|jpe?g|gif|bmp|xcf)$", re.I)

# Hosts that routinely appear in Chromium/Thorium docs and code. Only bare documentation
# domains are benign; subdomains of example.* are still reported.
BENIGN_HOSTS_RE = re.compile(
    r"^example\.(com|org|net)$|(^|\.)(chromium\.org|googlesource\.com|google\.com|googleapis\.com|"
    r"gstatic\.com|github\.com|githubusercontent\.com|thorium\.rocks|w3\.org|mozilla\.org|apache\.org|"
    r"gnu\.org|freedesktop\.org|microsoft\.com|apple\.com|chrome\.com|youtube\.com|wikipedia\.org|"
    r"llvm\.org|creativecommons\.org|opensource\.org|python\.org|kernel\.org|debian\.org|ubuntu\.com|"
    r"fedoraproject\.org|archlinux\.org|android\.com|crbug\.com|chromestatus\.com|webkit\.org|"
    r"whatwg\.org|ietf\.org|unicode\.org)$|^(localhost|127\.0\.0\.1)$")
URL_RE = re.compile(r"(?i)\b(?:https?|ftp|wss?)://([^\s\"'<>()\\`]+)")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
NON_PUBLIC_IP_RE = re.compile(r"^(127\.|0\.|10\.|192\.168\.|255\.|1\.0\.0\.|2\.0\.0\.|8\.8\.|1\.1\.1\.1|9\.9\.9\.9)")
VERSION_CONTEXT_RE = re.compile(r"version|VERSION|\.\d+\.\d+\.\d+\.\d")

PATTERNS = {
    "remote_exec": r"curl[^|\n]*\|\s*(ba)?sh|wget[^|\n]*\|\s*(ba)?sh|\biex\s*\(|Invoke-Expression|"
                   r"\bDownloadString\b|\bDownloadFile\b|Invoke-WebRequest|Start-BitsTransfer|"
                   r"certutil\s+-urlcache|\bbitsadmin\b",
    "encoded_payload": r"powershell[^\n]*-e(nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{20,}|FromBase64String|"
                       r"base64\s+(-d|--decode)\b|\batob\(|[A-Za-z0-9+/]{200,}={0,2}",
    "dynamic_code": r"\beval\s*\(|\bnew Function\(|\bexec\s*\(\s*(compile|base64)|__import__\(|"
                    r"shell\s*=\s*True|\bos\.system\(",
    "persistence": r"CurrentVersion\\+Run\b|\bschtasks\b|Register-ScheduledTask|\bcrontab\b|"
                   r"systemctl\s+enable|LaunchAgents|~/\.bashrc|~/\.profile|/etc/sudoers|sudoers\.d",
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


def _git(repo: str, *args: str) -> str:
    result = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", *args], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout.decode("utf-8", "replace")


def collect_added_lines(repo: str, base: str, target: str) -> dict[str, list[str]]:
    diff = _git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", base, target)
    added: dict[str, list[str]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is not None and SKIP_RE.search(current):
                current = None
        elif line.startswith("+") and current is not None:
            added.setdefault(current, []).append(line[1:])
    return added


def find_binaries(repo: str, base: str, target: str) -> list[tuple[str, str, int]]:
    fields = _git(repo, "diff", "--name-status", "-z", "--no-renames", base, target).split("\0")
    status = {fields[i + 1]: fields[i] for i in range(0, len(fields) - 1, 2) if fields[i]}
    found = []
    for record in _git(repo, "diff", "--numstat", "-z", "--no-renames", base, target).split("\0"):
        if not record.startswith("-\t-\t"):
            continue
        path = record[4:]
        if status.get(path) in ("A", "M") and not IMAGE_RE.search(path):
            size = int(_git(repo, "cat-file", "-s", f"{target}:{path}").strip())
            found.append((path, status[path], size))
    return found


def find_endpoints(added: dict[str, list[str]]) -> dict[str, set[str]]:
    hosts: dict[str, set[str]] = {}
    for path, lines in added.items():
        for text in lines:
            for match in URL_RE.finditer(text):
                try:
                    host = urlparse("http://" + match.group(1)).hostname or ""
                except ValueError:
                    continue
                if "." in host and not BENIGN_HOSTS_RE.search(host):
                    hosts.setdefault(host, set()).add(path)
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


def _print_report(section, binaries, endpoints, patterns, security):
    if section in ("files", "all"):
        print(f"=== ADDED/MODIFIED NON-IMAGE BINARIES ({len(binaries)})")
        for path, st, size in binaries:
            print(f"  [{st}] {path}  ({size:,} bytes)")
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
    parser.add_argument("--strict", action="store_true", help="exit 1 on binaries or high-risk patterns")
    args = parser.parse_args(argv)

    added = collect_added_lines(args.repo, args.base, args.target)
    binaries = find_binaries(args.repo, args.base, args.target)
    endpoints = find_endpoints(added)
    patterns = find_patterns(added)
    security = find_security_changes(added)

    if args.json:
        print(json.dumps({
            "binaries": [{"path": p, "status": s, "size": n} for p, s, n in binaries],
            "endpoints": {h: sorted(f) for h, f in endpoints.items()},
            "patterns": {k: [{"path": p, "line": t} for p, t in v] for k, v in patterns.items()},
            "security": security,
        }, indent=1))
    else:
        _print_report(args.section, binaries, endpoints, patterns, security)

    if args.strict and (binaries or any(patterns[c] for c in STRICT_CATEGORIES)):
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
