<div align="center">

<img src="branding/thoron/thoron-logo.svg" alt="Thoron logo" width="128" height="128">

# Thoron

**A fast, secure, Thorium-based browser for Windows 11 and Ubuntu.**

[![Status](https://img.shields.io/badge/status-pre--release-F72F8E?style=flat-square)](#roadmap) <!-- progress-badge:start -->[![Roadmap progress](https://img.shields.io/badge/roadmap-16%25-7B2FF7?style=flat-square)](#roadmap)<!-- progress-badge:end --> [![Platforms](https://img.shields.io/badge/platforms-Windows%2011%20%7C%20Ubuntu-24292f?style=flat-square)](#platforms) [![CPU](https://img.shields.io/badge/cpu-x64%20%7C%20ARM64-24292f?style=flat-square)](#platforms) [![License](https://img.shields.io/badge/license-BSD--3--Clause-24292f?style=flat-square)](LICENSE.md)

[Why Thoron](#why-thoron) · [Features](#features) · [Roadmap](#roadmap) · [Platforms](#platforms) · [Verify](#verifying-downloads) · [Security](#security) · [Contributing](#contributing) · [Credits](#credits)

</div>

> Thoron is an independent browser by KuchiSofts, based on Thorium by Alex313031 and Chromium by The
> Chromium Authors. It is not affiliated with or endorsed by the Thorium project or Google.

*Thoron* is the gas that thorium naturally turns into: a browser born from
[Thorium](https://github.com/Alex313031/thorium).

## Why Thoron

Thoron keeps everything that makes Thorium fast and adds a strict set of commitments. They apply
from the first release; the tooling that delivers them is being built now.

- **Traceable builds.** Every release is built from a tagged commit, and the tag points to exactly
  what was built. Build details (Chromium version, toolchain, our commit) ship in `BUILDINFO.json`.
- **Signed updates.** Update manifests and checksum files are signed. The updater refuses anything
  unsigned, altered or older than what you have.
- **Fast security fixes.** Our target is 7 days after a Chrome release that fixes an actively
  exploited bug, and 14 days after each new Chrome major version.
- **Your data stays yours.** Updates and imports never delete, move or modify your profile, and major
  updates snapshot it first so they can be rolled back. No telemetry.
- **Clean and audited.** Every upstream change passes an automatic audit (binaries, network
  endpoints, download-and-run code, content standards) and a human review before it lands.
- **Full credit.** Everyone whose work Thoron builds on is credited in [`CREDITS.md`](CREDITS.md),
  with every licence listed in [`NOTICE`](NOTICE).

## Features

Thoron is in active development. These are the headline features on the roadmap:

| Feature | What it does | Phase |
|---|---|---|
| **Smart updater** | Small delta downloads for installed **and** portable copies, staged in the background, applied on relaunch, with one-step rollback. Full installers stay available. | [P3](ROADMAP.md#p3---updater-v1--import) · [P4](ROADMAP.md#p4---updater-v2) |
| **Import from your browser** | Brings over **open tabs and tab groups** (names, colours, pinned tabs), bookmarks, history, passwords, settings and extensions from Thorium, Chrome, Edge, Brave, Vivaldi, Opera and later Firefox. Your old browser is never modified. | [P3](ROADMAP.md#p3---updater-v1--import) |
| **Built-in ad blocking** | The genuine, unmodified uBlock Origin, pinned and signature-verified, kept up to date. | [P5](ROADMAP.md#p5---quality) |
| **Protected portable mode** | Saved passwords and cookies in the portable version are encrypted with your passphrase, so they work on any PC and stay safe if the folder is lost. | [P4](ROADMAP.md#p4---updater-v2) |
| **Right build, automatically** | The installer picks the fastest build your CPU supports (AVX2, SSE4 or ARM64). | [P4](ROADMAP.md#p4---updater-v2) |
| **Measured performance** | Every release is benchmarked (Speedometer, JetStream, MotionMark, startup, memory, idle CPU). A regression blocks the release. | [Q track](ROADMAP.md#quality--performance-q) |

## Roadmap

Generated from [`ROADMAP.md`](ROADMAP.md) on every change, so it is always current.

<!-- roadmap:start -->
**Overall:** `███░░░░░░░░░░░░░░░░░` 19 of 117 tasks done (16%) · roadmap updated 2026-11-07

| Area | Progress | Done | Status |
|---|---|---|---|
| [P0 - Foundation](ROADMAP.md#p0---foundation) | `████████████████████` | 11/11 | ✅ Done |
| [P1 - Build environment](ROADMAP.md#p1---build-environment) | `██░░░░░░░░░░░░░░░░░░` | 1/10 | 🔄 In progress |
| [P2 - First release](ROADMAP.md#p2---first-release) | `░░░░░░░░░░░░░░░░░░░░` | 0/15 | ⬜ Not started |
| [P2b - ARM64](ROADMAP.md#p2b---arm64) | `░░░░░░░░░░░░░░░░░░░░` | 0/5 | ⬜ Not started |
| [P3 - Updater v1 + Import](ROADMAP.md#p3---updater-v1--import) | `░░░░░░░░░░░░░░░░░░░░` | 0/18 | ⬜ Not started |
| [P4 - Updater v2](ROADMAP.md#p4---updater-v2) | `░░░░░░░░░░░░░░░░░░░░` | 0/11 | ⬜ Not started |
| [P5 - Quality](ROADMAP.md#p5---quality) | `░░░░░░░░░░░░░░░░░░░░` | 0/12 | ⬜ Not started |
| [Security (S)](ROADMAP.md#security-s) | `██████░░░░░░░░░░░░░░` | 4/13 | 🔄 In progress |
| [Quality & performance (Q)](ROADMAP.md#quality--performance-q) | `░░░░░░░░░░░░░░░░░░░░` | 0/6 | ⬜ Not started |
| [Docs (D)](ROADMAP.md#docs-d) | `███░░░░░░░░░░░░░░░░░` | 1/7 | 🔄 In progress |
| [Legal & licensing (L)](ROADMAP.md#legal--licensing-l) | `░░░░░░░░░░░░░░░░░░░░` | 0/5 | 🔄 In progress |
| [Branding (B)](ROADMAP.md#branding-b) | `██████████░░░░░░░░░░` | 2/4 | 🔄 In progress |

**What's next**

- 🔄 **P1.7** Smoke-test harness (`tools/qa/smoke.py`): fresh profile; local pages for JS, WebGL, H.264/HEVC/AV1 video, JPEG XL; no crash dumps
- ⬜ **P1.1** Windows toolchain: Visual Studio 2022 (Desktop C++, ATL/MFC), Windows 11 SDK 10.0.22621.x plus Debugging Tools, pinned depot_tools, NTFS checkout on a fast local drive
- ⬜ **P1.2** Linux toolchain in WSL2 Ubuntu 24.04: ext4 disk of at least 150 GB, `install-build-deps`, x64 and arm64 sysroots
- ⬜ **P1.3** Branch `ks/M156` from gz83 tag `M156.0.8078.28` (`de9a1bc6`); fetch Chromium 156.0.8078.28; apply the upstream patch series
- ⬜ **P1.4** Reproduce the Windows x64 AVX2 build of M156
- ⬜ **P1.5** Reproduce the Linux x64 build of M156 in WSL2

<details>
<summary><b>Full task list</b> (generated from <a href="ROADMAP.md">ROADMAP.md</a>)</summary>

**P0 - Foundation**

- [x] **P0.1** Feature branch, private noreply commit identity, approved design committed
- [x] **P0.2** Audit toolkit (`tools/audit`: `audit_diff`, `crx_id`, `compare_release`)
- [x] **P0.3** Docs and privacy linter (`tools/docs/check_docs.py`)
- [x] **P0.4** Contributor credits generator (`tools/credits/contributors.py`)
- [x] **P0.5** `CREDITS.md` and `NOTICE`
- [x] **P0.6** Thoron README; original Thorium README preserved at `docs/upstream/`
- [x] **P0.7** This roadmap
- [x] **P0.8** `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- [x] **P0.9** Thoron icon concepts and the owner's choice (see B.1)
- [x] **P0.10** Icon asset pipeline and generated icons (see B.2)
- [x] **P0.11** Final verification and owner-approved push

**P1 - Build environment**

- [ ] **P1.1** Windows toolchain: Visual Studio 2022 (Desktop C++, ATL/MFC), Windows 11 SDK 10.0.22621.x plus Debugging Tools, pinned depot_tools, NTFS checkout on a fast local drive
- [ ] **P1.2** Linux toolchain in WSL2 Ubuntu 24.04: ext4 disk of at least 150 GB, `install-build-deps`, x64 and arm64 sysroots
- [ ] **P1.3** Branch `ks/M156` from gz83 tag `M156.0.8078.28` (`de9a1bc6`); fetch Chromium 156.0.8078.28; apply the upstream patch series
- [ ] **P1.4** Reproduce the Windows x64 AVX2 build of M156
- [ ] **P1.5** Reproduce the Linux x64 build of M156 in WSL2
- [x] **P1.6** `BUILDINFO.json` generator: Chromium tag, Thoron commit, depot_tools revision, VS/SDK versions, GN args hash, build time
- [ ] **P1.7** Smoke-test harness (`tools/qa/smoke.py`): fresh profile; local pages for JS, WebGL, H.264/HEVC/AV1 video, JPEG XL; no crash dumps
- [ ] **P1.8** Manifest V2 / uBlock Origin viability on Chromium 158: apply the MV2 patches to 158 and load uBO 1.75
- [ ] **P1.9** Thoron build docs written from scratch and followed end-to-end
- [ ] **P1.10** Release build-matrix time budget (Windows/Linux × AVX2/SSE4, plus ARM64) against the G2 targets

**P2 - First release**

- [ ] **P2.1** Branch `ks/M158`; rebase the upstream patch series from 156 to Chromium 158.0.8127.x
- [ ] **P2.2** Audit all upstream changes since `de9a1bc6` with `tools/audit` (S.1)
- [ ] **P2.3** Identity patch, Windows: product name Thoron, `%LOCALAPPDATA%\Thoron`, `HKCU\Software\Thoron`, new app GUID in `chromium_install_modes.h`, ProgIDs, AppUserModelID
- [ ] **P2.4** Identity patch, Linux: package `thoron-browser`, `.desktop` file, `~/.config/thoron`, keyring entry `Thoron Safe Storage`
- [ ] **P2.5** About page: Thoron version, Chromium version, verbatim disclaimer, links to credits and changelog
- [ ] **P2.6** Widevine not bundled; fetched by Chromium's component updater at runtime
- [ ] **P2.7** Variants AVX2 and SSE4 for Windows x64 and Linux x64
- [ ] **P2.8** Windows packaging: Thoron mini_installer, portable `.zip` with launcher
- [ ] **P2.9** Linux packaging: `.deb` with an AppArmor profile for user namespaces, plus portable `.tar.xz`
- [ ] **P2.10** Signed APT repository on GitHub Pages (fixes the unsigned-repo problem of upstream #1164 and #1049)
- [ ] **P2.11** Key ceremony: Ed25519 release key (minisign) and APT signing key, offline root, encrypted backups
- [ ] **P2.12** Release script `tools/release/release.py`: build matrix → package → `SHA256SUMS` → sign → `BUILDINFO` → **draft** GitHub release
- [ ] **P2.13** `tools/release/changelog.py`: release notes generated from commit prefixes, upstream merges (author-credited), the Chromium version diff and security fixes (CVE and severity), patch changes, and issues
- [ ] **P2.14** Version scheme for Thoron rebuilds of the same Chromium version (4-part numeric, Windows-installer compatible)
- [ ] **P2.15** First draft release, Thoron 158.x (Windows x64 and Linux x64)

**P2b - ARM64**

- [ ] **P2b.1** Windows ARM64 build, cross-compiled on the x64 host; installer and portable
- [ ] **P2b.2** Linux ARM64 build, cross-compiled with the arm64 sysroot; `.deb` and portable
- [ ] **P2b.3** Emulated smoke tests (qemu-user plus headless for Linux ARM64; static checks for Windows ARM64)
- [ ] **P2b.4** Beta programme: ARM issue template and community tester checklist
- [ ] **P2b.5** Real-device validation (Windows-on-ARM laptop, ARM64 Linux device); beta label removed

**P3 - Updater v1 + Import**

- [ ] **P3.1** Update manifest schema v1 and spec `docs/update/MANIFEST.md` (channel, version, Chromium version, `critical`, `min_updater_version`, `expires`, per-variant full and delta entries)
- [ ] **P3.2** Manifest signing in the release script (Ed25519, detached signature)
- [ ] **P3.3** Updater core (C++, in-tree, BoringSSL): fetch over HTTPS, **verify the signature before parsing**, anti-downgrade, expiry handling
- [ ] **P3.4** Download and verify (size plus SHA-256) for full packages
- [ ] **P3.5** Staging and atomic swap: `<new>.staging` → verify every file → rename; keep N-1
- [ ] **P3.6** In-use update: Chromium's `new_thoron.exe` rename on Windows, and the launcher swap on Linux per-user and portable installs; relaunch badge
- [ ] **P3.7** Profile snapshot before major-version updates (critical files of all profiles, verified, last 2 kept, stored next to `User Data`)
- [ ] **P3.8** Rollback: restore N-1 plus the snapshot, with an explicit warning and confirmation
- [ ] **P3.9** About page updater states: checking, downloading %, ready to relaunch, up to date, cannot verify, error
- [ ] **P3.10** Scheduling without admin rights: Windows per-user task (Limited), Linux systemd user timer, portable only while running
- [ ] **P3.11** Update settings (auto / notify-only / off) and CLI `--check --apply --status --rollback`
- [ ] **P3.12** Portable launcher (a Windows `.exe` replacing the `.bat`; Linux shell launcher) with swap-on-start
- [ ] **P3.13** Import UI in the installer and in Settings → Import: detected browsers and profiles, per-type checkboxes, a "please close <browser>" prompt (never force-closes)
- [ ] **P3.14** Chromium-family import engine: copy, never move; verify (hash plus SQLite integrity); bookmarks, history, passwords, cookies, extensions, settings, autofill
- [ ] **P3.15** Tabs and tab-groups import: our own SNSS session parser (windows, tab order, groups with name, colour and collapsed state, pinned and active tab, per-tab history)
- [ ] **P3.16** Linux keyring migration (`Thorium Safe Storage` → `Thoron Safe Storage`)
- [ ] **P3.17** Guided Chrome password import (Chrome's own CSV export → import → secure delete); never bypasses app-bound encryption
- [ ] **P3.18** Import report (counts per type, what was skipped and why; no secrets)

**P4 - Updater v2**

- [ ] **P4.1** Delta packages: per-file Zucchini patches from each of the previous 3 releases, per variant
- [ ] **P4.2** Delta-chain selection (smallest total download) with automatic fallback to the full package on any base-hash mismatch
- [ ] **P4.3** Resumable downloads (HTTP range; Windows BITS optional), pause on metered connections, proxy support
- [ ] **P4.4** CPU variant auto-selection (AVX2 / SSE4 / ARM64), plus the portable "moved to another PC" check
- [ ] **P4.5** Freeze and expiry protection with clock-skew tolerance
- [ ] **P4.6** Updater self-update via `min_updater_version`
- [ ] **P4.7** Signing-key rotation (the old key signs the new key's statement)
- [ ] **P4.8** Firefox import: bookmarks, history and passwords via Chromium's importer; tabs and groups from `sessionstore.jsonlz4`
- [ ] **P4.9** Portable passphrase encryption: Argon2id-wrapped profile key, remember-this-PC (DPAPI/libsecret), recovery key, read support for old formats
- [ ] **P4.10** Upstream portable adoption: copy → verify → encrypt the copy → verify decryption → use; original untouched
- [ ] **P4.11** Optional APT delta support (`debdelta`)

**P5 - Quality**

- [ ] **P5.1** uBlock Origin migration for existing profiles (frozen Web Store copy `cjpalh…` → updatable GitHub copy `fkgk…`), keeping settings and custom filters; never forced
- [ ] **P5.2** Ad-blocking phase 2 decision: keep Manifest V2 alive, or build a native engine (as Brave does with `adblock-rust`, MPL-2.0)
- [ ] **P5.3** Investigate the M156 Windows CPU spike and "Unknown Hard Error" (#1313) on Thoron builds
- [ ] **P5.4** Intermittent breakpoint crash in `sqlite3_dbdata_init` (#1230)
- [ ] **P5.5** Suspended-tab crash on the AVX-512 build (#1278)
- [ ] **P5.6** `STATUS_ACCESS_VIOLATION` on Discord (#1288)
- [ ] **P5.7** HEVC/AV1 playback regression (#1271) and NVIDIA frame drops (#1285)
- [ ] **P5.8** Passwords not saved (#137, #684, #1199)
- [ ] **P5.9** Random logouts and lost sessions (#1005, #458)
- [ ] **P5.10** Slow start-up with multiple profiles (#803)
- [ ] **P5.11** Evaluate an AVX-512 variant (performance gain versus stability)
- [ ] **P5.12** Linux hardware video acceleration (VA-API) on current Ubuntu (#1231)

**Security (S)**

- [x] **S.1** Audit every upstream merge and release with `tools/audit` (`--strict`, with every finding reviewed by a human)
- [ ] **S.2** Threat model for the updater, import and portable encryption (`docs/security/THREAT_MODEL.md`)
- [ ] **S.3** Remove `'unsafe-inline'` from the Thorium authors WebUI page CSP
- [ ] **S.4** Review every flag that weakens security (for example `allow-insecure-downloads`, `disable-web-security`, `disable-encryption`); each must stay opt-in and carry a warning
- [ ] **S.5** Sandbox verification every release (Windows sandbox; Linux AppArmor and user namespaces)
- [x] **S.6** Enable GitHub Issues and private vulnerability reporting for the repository, before the docs that link to them go public (part of P0.11)
- [ ] **S.7** Every patch carries `Origin:`, `Author:` and `License:` headers (with L.1)
- [ ] **S.8** Authenticode code signing once a certificate exists
- [ ] **S.9** Security-release process: watch Chrome Releases, triage, fast-track build within the G2 targets
- [ ] **S.10** Publish the list of every network endpoint Thoron contacts and why (upstream #126)
- [ ] **S.11** Remove Thorium's hidden Easter-egg WebUI pages (`chrome://eggs`, `chrome://robot`) from Thoron: a professional product with a smaller WebUI attack surface (pairs with S.3)
- [x] **S.12** Content standards: written policy in `CONTRIBUTING.md`, plus an automatic `adult_content` check in `tools/audit` (added text and file names, `--strict`)
- [x] **S.13** Inherited history cleaned: three inappropriate image files that upstream added in 2023 and later deleted were purged from every commit; the current tree is unchanged; they were verified absent from the M150 browser build

**Quality & performance (Q)**

- [ ] **Q.1** Benchmark suite `tools/qa/bench`: Speedometer 3, JetStream 2, MotionMark, start-up with 1 and 4 profiles, idle and 20-tab memory, idle CPU
- [ ] **Q.2** Baselines: Thorium M156 and Chrome of the same major version
- [ ] **Q.3** Regression gate in the release script (a release is blocked until any regression is explained)
- [ ] **Q.4** Memory-leak soak test (8 h of tab churn; memory-growth threshold)
- [ ] **Q.5** Crash triage process (local Crashpad dumps; symbol publication decision)
- [ ] **Q.6** Test VMs: Windows 11 x64, Ubuntu 24.04 and 26.04 x64, clean snapshots

**Docs (D)**

- [ ] **D.1** Keep README, ROADMAP, CHANGELOG, CREDITS, NOTICE and docs current on every change (definition of done)
- [ ] **D.2** User guides: install, import, updates and rollback, portable passphrase (`docs/user/`)
- [ ] **D.3** Repair broken links in upstream docs (`docs/BUILDING_MAC.md`, `docs/PATCHES.md`, `docs/TH24.md`)
- [ ] **D.4** Release notes for every release (generated by `changelog.py`, highlights written by a person)
- [ ] **D.5** Rebrand the GitHub issue and PR templates for Thoron (bug, feature, ARM beta report, security redirect)
- [ ] **D.6** Repository identity: renamed to `KuchiSofts/thoron` with Thoron description and topics; the owner asks GitHub Support to detach it from the Thorium fork network and to remove cached views and old pull-request references to purged history
- [x] **D.7** README shows the live roadmap: overall progress, per-phase bars, what's next and the full task list, generated from this file by `tools/docs/roadmap_progress.py`; `check_docs` fails if it is stale, and validates every heading anchor

**Legal & licensing (L)**

- [ ] **L.1** Licence inventory of every patch (origin, author, licence); resolve pending sources (Debian, chromium-ubuntu-build, Vanadium, Supermium); rewrite or drop anything incompatible
- [ ] **L.2** GPL compliance per release: source tag and Chromium tag in `BUILDINFO`, GPL text in the licence bundle, notes in the release
- [ ] **L.3** Regenerate contributors and update `NOTICE` and `CREDITS` every release
- [ ] **L.4** Courtesy note to Alex313031 and gz83 introducing Thoron and its credits
- [ ] **L.5** Name and logo check: "Thoron" in trademark registries and existing software in target markets; logo similarity to other browser marks (for example Chrome's three-segment logo)

**Branding (B)**

- [x] **B.1** Icon concepts (3 original concepts, previews at 16-256 px on light and dark backgrounds) and the owner's choice
- [x] **B.2** Final asset set: colour and mono SVG, PNG 16-512, multi-size `.ico`
- [ ] **B.3** Chromium resource integration: product logos, `.ico`, installer images, Linux icons, About page and new-tab logo
- [ ] **B.4** Release-page and social preview visuals

</details>
<!-- roadmap:end -->

## Platforms

| OS | CPUs | Packages |
|---|---|---|
| Windows 11 | x64 (AMD, Intel), ARM64 | installer `.exe`, portable `.zip` |
| Ubuntu 24.04 / 26.04 LTS | x64 (AMD, Intel), ARM64 | `.deb` via a signed APT repository, portable `.tar.xz` |

ARM64 builds stay labelled *beta* until they have been tested on real devices.

## Verifying downloads

Each release will include `SHA256SUMS` and its signature `SHA256SUMS.minisig`. The public key will be
published here and in the release notes with the first release.

**Always do both steps.** A checksum alone only proves the file matches `SHA256SUMS`. The signature
proves `SHA256SUMS` itself came from Thoron. [minisign](https://jedisct1.github.io/minisign/) is
available for Windows and Ubuntu.

```powershell
# Windows (PowerShell)
minisign -Vm SHA256SUMS -P <thoron-public-key>            # 1. the checksum list is genuine
Get-FileHash .\Thoron_AVX2_installer.exe -Algorithm SHA256  # 2. compare with its line in SHA256SUMS
```

```shell
# Ubuntu
minisign -Vm SHA256SUMS -P <thoron-public-key>            # 1. the checksum list is genuine
sha256sum --check --ignore-missing SHA256SUMS              # 2. your download matches it
```

Windows binaries are not Authenticode-signed yet, so SmartScreen will warn on first install. Verify
the checksum and signature as shown above.

## Building

Thoron's own build guides arrive in phase **P1**. Until then, the Thorium guides apply:
[Windows](docs/BUILDING_WIN.md) · [Linux](docs/BUILDING.md).

The repository tooling (audit, docs and credits checks) needs only Python 3.11+:

```shell
py -3 -I -m unittest discover -s tools -t . -p "test_*.py" -v   # tests
py -3 -I tools/docs/check_docs.py                               # docs, links, house style
```

## Security

Please report vulnerabilities **privately** through
[GitHub's private reporting](https://github.com/KuchiSofts/thoron/security/advisories/new), never in
public issues. Details: [`SECURITY.md`](SECURITY.md).

## Contributing

Contributions are welcome. [`CONTRIBUTING.md`](CONTRIBUTING.md) covers the commit style, the
definition of done, copyright and attribution, and the content standards.

## Credits

Thoron stands on the work of others. Thank you to **Alexander Frick (Alex313031)**, who created
Thorium, to **Ho Cheung (gz83)**, its current maintainer, to **midzer** and every Thorium contributor,
and to **The Chromium Authors**. Thanks also to the projects whose patches Thorium uses
(ungoogled-chromium, Bromite and Cromite, Debian, Iridium, Vanadium and others), and to
**Raymond Hill** for uBlock Origin. The full list is in [`CREDITS.md`](CREDITS.md).

## License

Code is BSD-3-Clause ([`LICENSE.md`](LICENSE.md), © Alexander Frick, with Thoron changes © KuchiSofts).
Some patches come from GPL-3.0 projects; binaries that contain them are distributed under GPL-3.0
terms with source in this repository. uBlock Origin is GPL-3.0. The Thoron logo is CC BY 4.0.
Details in [`NOTICE`](NOTICE).

<sub>The original Thorium README is preserved at [`docs/upstream/THORIUM_README.md`](docs/upstream/THORIUM_README.md).</sub>
