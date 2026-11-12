<div align="center">

<img src="branding/thoron/thoron-logo.svg" alt="Thoron logo" width="128" height="128">

# Thoron

**A fast, secure and private browser for Windows, based on Thorium and Chromium.**

[![Status](https://img.shields.io/badge/status-pre--release-F72F8E?style=flat-square)](#roadmap) <!-- progress-badge:start -->[![Roadmap progress](https://img.shields.io/badge/roadmap-38%25-7B2FF7?style=flat-square)](#roadmap)<!-- progress-badge:end --> [![Platforms](https://img.shields.io/badge/platforms-Windows%20first-24292f?style=flat-square)](#platforms) [![CPU](https://img.shields.io/badge/cpu-x64%20%7C%20ARM64-24292f?style=flat-square)](#platforms) [![License](https://img.shields.io/badge/license-BSD--3--Clause-24292f?style=flat-square)](LICENSE.md)

[Why Thoron](#why-thoron) · [Features](#features) · [Install and update](#install-and-update) · [Versions](#versions) · [Roadmap](#roadmap) · [Platforms](#platforms) · [Verify](#verifying-downloads) · [Security](#security) · [Contributing](#contributing) · [Credits](#credits) · [Wiki](https://github.com/KuchiSofts/thoron/wiki)

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
| **Updates itself** | The browser checks for a new release, verifies its signature, installs it and asks for one relaunch. Your data is never touched. Smaller delta downloads, portable copies and one-step rollback follow. | [P3](ROADMAP.md#p3---updater-v1--import) · [P4](ROADMAP.md#p4---updater-v2) |
| **One installer for good** | A small `ThoronSetup.exe` that always installs the newest release, so one download link stays valid. The full installer is in every release too. | [P3](ROADMAP.md#p3---updater-v1--import) |
| **Import from your browser** | Brings over **open tabs and tab groups** (names, colours, pinned tabs), bookmarks, history, passwords, settings and extensions from Thorium, Chrome, Edge, Brave, Vivaldi, Opera and later Firefox. Your old browser is never modified. | [P3](ROADMAP.md#p3---updater-v1--import) |
| **A first run that moves you in** | On first start Thoron offers to import from the browsers it finds and to become your default browser. Both are offers: nothing is taken over silently. | [P3](ROADMAP.md#p3---updater-v1--import) |
| **Built-in ad blocking** | Today: the genuine, unmodified uBlock Origin, pinned and signature-verified. Being built: a blocker inside the browser itself that reads the same lists and replaces it. It already measures faster and lighter than uBlock Origin with the same blocking, and stays off by default until its last correctness checks are done. To try it, turn on "Built-in ad blocking" at `chrome://flags/#thoron-native-adblock` (and turn uBlock Origin off, or both do the same work). Its lists and your own rules are on `chrome://adblock`. It also keeps pop-up ads and pages its lists name as harmful from opening. | [P5](ROADMAP.md#p5---quality) |
| **Protected portable mode** | Saved passwords and cookies in the portable version are encrypted with your passphrase, so they work on any PC and stay safe if the folder is lost. | [P4](ROADMAP.md#p4---updater-v2) |
| **Right build, automatically** | The installer picks the fastest build your CPU supports (AVX2, SSE4 or ARM64). | [P4](ROADMAP.md#p4---updater-v2) |
| **Measured performance** | Every release is benchmarked (Speedometer, JetStream, MotionMark, startup, memory, idle CPU). A regression blocks the release. | [Q track](ROADMAP.md#quality--performance-q) |

## Install and update

There is no public release yet. The first one is **Thoron 0.1.1 for Windows x64**; what is left before it
is listed at the top of the [roadmap](ROADMAP.md#now-the-road-to-thoron-011-windows-x64).

From that release on:

- **Install:** download `ThoronSetup.exe` from the newest
  [release](https://github.com/KuchiSofts/thoron/releases) and run it. It installs for your user account,
  without administrator rights, and offers to import from your other browser.
- **Update:** nothing to do. Thoron updates itself and asks for one relaunch. You can also look for an
  update on the About page, or turn automatic updates off.
- **Your data:** an update only replaces the program. Bookmarks, passwords, history, tabs and extensions
  are never deleted, moved or changed by it.

## Versions

Thoron has its own version numbers, `0.MINOR.PATCH`, starting at **0.1.1**. Every release gets the next
one. The About page shows the Thoron version and, below it, the Chromium version it is built on. What
changed in each version is in the [changelog](CHANGELOG.md), one line per change.

## Roadmap

Generated from [`ROADMAP.md`](ROADMAP.md) on every change, so it is always current.

<!-- roadmap:start -->
**Overall:** `████████░░░░░░░░░░░░` 63 of 168 tasks done (38%) · roadmap updated 2026-11-12

| Area | Progress | Done | Status |
|---|---|---|---|
| [P0 - Foundation](ROADMAP.md#p0---foundation) | `████████████████████` | 11/11 | ✅ Done |
| [P1 - Build environment](ROADMAP.md#p1---build-environment) | `██████████████████░░` | 9/10 | 🔄 In progress |
| [P2 - First release](ROADMAP.md#p2---first-release) | `████░░░░░░░░░░░░░░░░` | 5/26 | 🔄 In progress |
| [P2b - ARM64](ROADMAP.md#p2b---arm64) | `░░░░░░░░░░░░░░░░░░░░` | 0/5 | ⬜ Not started |
| [P3 - Updater v1 + Import](ROADMAP.md#p3---updater-v1--import) | `░░░░░░░░░░░░░░░░░░░░` | 0/21 | ⬜ Not started |
| [P4 - Updater v2](ROADMAP.md#p4---updater-v2) | `░░░░░░░░░░░░░░░░░░░░` | 0/11 | ⬜ Not started |
| [P5 - Quality](ROADMAP.md#p5---quality) | `███████████░░░░░░░░░` | 22/39 | 🔄 In progress |
| [Security (S)](ROADMAP.md#security-s) | `██████████░░░░░░░░░░` | 8/16 | 🔄 In progress |
| [Quality & performance (Q)](ROADMAP.md#quality--performance-q) | `███░░░░░░░░░░░░░░░░░` | 1/7 | 🔄 In progress |
| [Docs (D)](ROADMAP.md#docs-d) | `████████░░░░░░░░░░░░` | 4/10 | 🔄 In progress |
| [Legal & licensing (L)](ROADMAP.md#legal--licensing-l) | `██░░░░░░░░░░░░░░░░░░` | 1/8 | 🔄 In progress |
| [Branding (B)](ROADMAP.md#branding-b) | `██████████░░░░░░░░░░` | 2/4 | 🔄 In progress |

**What's next**

- 🔄 **P1.9** Thoron build docs written from scratch and followed end-to-end
- 🔄 **P2.4** Identity patch, Linux: package `thoron-browser`, `.desktop` file, `~/.config/thoron`; the keyring entry stays `Chromium Safe Storage` (shared with Thorium, so imported passwords stay readable)
- 🔄 **P2.5** About page: Thoron version, Chromium version, verbatim disclaimer, links to credits and changelog
- 🔄 **P2.6** Widevine not bundled; fetched by Chromium's component updater at runtime
- 🔄 **P2.12** Release script `tools/release/release.py`: build matrix → package → `SHA256SUMS` → sign → `BUILDINFO` → **draft** GitHub release; sets the version and refuses a non-increasing one with `tools/release/version.py` (P2.14)
- 🔄 **P2.13** `tools/release/changelog.py`: release notes generated from commit prefixes, upstream merges (author-credited), the Chromium version diff and security fixes (CVE and severity), patch changes, and issues

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

- [x] **P1.1** Windows toolchain: Visual Studio 2026 (Desktop C++, ATL/MFC), Windows SDK 10.0.28000 plus Debugging Tools, pinned depot_tools, NTFS checkout on a fast local drive that is not cloud-synced
- [x] **P1.2** Linux toolchain in WSL2 Ubuntu 24.04: ext4 disk of at least 150 GB, `install-build-deps`, x64 and arm64 sysroots
- [x] **P1.3** Local-only worktree of gz83 tag `M156.0.8078.28` (`de9a1bc6`, never pushed); fetch Chromium 156.0.8078.28; apply the upstream patch series
- [x] **P1.4** Reproduce the Windows x64 AVX2 build of M156
- [x] **P1.5** Reproduce the Linux x64 build of M156 in WSL2
- [x] **P1.6** `BUILDINFO.json` generator: Chromium tag, Thoron commit, depot_tools revision, VS/SDK versions, GN args hash, build time
- [x] **P1.7** Smoke-test harness (`tools/build/smoke.py`): fresh profile; local pages for JS, WebGL, H.264/HEVC/AV1 video, JPEG XL; no crash dumps
- [x] **P1.8** Manifest V2 / uBlock Origin viability on Chromium 158: apply the MV2 patches to 158 and load uBO 1.75
- [ ] **P1.9** Thoron build docs written from scratch and followed end-to-end
- [x] **P1.10** Release build-matrix time budget (Windows/Linux × AVX2/SSE4, plus ARM64) against the G2 targets

**P2 - First release**

- [x] **P2.1** Branch `ks/M158`; rebase the upstream patch series from 156 to Chromium 158.0.8127.x
- [ ] **P2.2** Audit all upstream changes since `de9a1bc6` with `tools/audit` (S.1)
- [x] **P2.3** Identity patch, Windows: product name Thoron, `%LOCALAPPDATA%\Thoron`, `HKCU\Software\Thoron`, new app GUID in `chromium_install_modes.h`, ProgIDs, AppUserModelID
- [ ] **P2.4** Identity patch, Linux: package `thoron-browser`, `.desktop` file, `~/.config/thoron`; the keyring entry stays `Chromium Safe Storage` (shared with Thorium, so imported passwords stay readable)
- [ ] **P2.5** About page: Thoron version, Chromium version, verbatim disclaimer, links to credits and changelog
- [ ] **P2.6** Widevine not bundled; fetched by Chromium's component updater at runtime
- [ ] **P2.7** Variants AVX2 and SSE4 for Windows x64 and Linux x64
- [ ] **P2.8** Windows packaging: Thoron mini_installer, portable `.zip` with launcher
- [ ] **P2.9** Linux packaging: `.deb` with an AppArmor profile for user namespaces, plus portable `.tar.xz`
- [ ] **P2.10** Signed APT repository on GitHub Pages (fixes the unsigned-repo problem of upstream #1164 and #1049)
- [ ] **P2.11** Key ceremony: Ed25519 release key (minisign) and APT signing key, offline root, encrypted backups
- [ ] **P2.12** Release script `tools/release/release.py`: build matrix → package → `SHA256SUMS` → sign → `BUILDINFO` → **draft** GitHub release; sets the version and refuses a non-increasing one with `tools/release/version.py` (P2.14)
- [ ] **P2.13** `tools/release/changelog.py`: release notes generated from commit prefixes, upstream merges (author-credited), the Chromium version diff and security fixes (CVE and severity), patch changes, and issues
- [x] **P2.14** Version scheme for Thoron rebuilds of the same Chromium version (4-part numeric, Windows-installer compatible)
- [ ] **P2.15** First draft release, Thoron 158.x (Windows x64 and Linux x64)
- [ ] **P2.16** No silent Web Store installs: Thorium's default apps install uBlock Origin from the Chrome Web Store into every new profile, contacting Google when the profile is created; Thoron ships its bundled, SHA-256-pinned uBlock Origin instead and installs nothing from the network without the user's consent
- [x] **P2.17** Privacy review of the inherited build configuration, for example `enable_rlz = true` (Google's promotional RLZ library) and any other upstream GN arg that adds network contact or tracking
- [ ] **P2.18** uBlock Origin runs on 158: check whether `chrome.storage.managed.get` also hangs in the release configuration and for normally installed extensions; fix it (patch or configuration); verify cosmetic filtering with a normally installed extension in a visible window
- [ ] **P2.19** Thoron's own COM interface IDs (IElevator, tracing service): regenerate the checked-in MIDL output; needed before system-level installs, which register those interfaces
- [x] **P2.20** Program and installer file names: `thoron.exe` instead of `thorium.exe`, the installer name, and no Thorium updater remnants (`thor_ver`)
- [ ] **P2.21** Linux program and package names: `thoron` instead of `thorium` for the binary, the `.deb`/`.rpm` packages, the `.desktop` file and the icons; the developer test shell and the prebuilt `pak` tool are not packaged
- [ ] **P2.22** Linux dark mode on 158: check whether Chromium 158 follows a GTK theme switch on its own; if not, write Thoron's own fix (the Thorium patch was not carried over, see `docs/build/M158_REBASE.md`)
- [ ] **P2.23** Check the hand-ported UI patches in a running 158 build: tab search button on the right (default) and on the left (flag), Thorium 2024 UI, classic omnibox, rectangular tabs, custom tab width, open link in this tab
- [ ] **P2.24** Thoron's own version: `0.MINOR.PATCH`, starting at 0.1.1, shown on the About page, in `chrome://version`, in the installer and as the release tag (`v0.1.1`); the release script gives every release the next number by itself; the four-part build version stays Chromium-based (`158.0.8127.<n>`), because websites, extensions, Chromium's component updates and the installer's upgrade order rely on it
- [ ] **P2.25** The browser's source in `main`: the patch series for Chromium 158 was only on the build machine; publish it as an overlay on a pinned upstream commit, so that `main` holds everything a release is built from and nothing else
- [ ] **P2.26** Repository hygiene and protection

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
- [ ] **P3.16** Linux keyring check: Thoron keeps the `Chromium Safe Storage` entry that Thorium uses, so no key migration is needed; prove it on import
- [ ] **P3.17** Guided Chrome password import (Chrome's own CSV export → import → secure delete); never bypasses app-bound encryption
- [ ] **P3.18** Import report (counts per type, what was skipped and why; no secrets)
- [ ] **P3.19** One installer for good, `ThoronSetup.exe`: a small program that never changes with a release; it reads the signed update manifest, downloads the newest full installer, checks the signature and the SHA-256, and runs it
- [ ] **P3.20** Updates from inside the browser, Windows: a check on a schedule and from the About page, the signed manifest (P3.3), a verified download (P3.4), then Chromium's own installer applies the new version while the browser runs and the About page offers to relaunch; `User Data` is never opened by the update
- [ ] **P3.21** First run on Windows: offers to import from the browsers it finds (P3.13, P3.14) and to make Thoron the default browser for web links and for the file types a browser opens; where Windows wants the person to confirm, it opens Windows' own page for it and takes nothing over silently

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
- [x] **P5.2** Ad-blocking phase 2 decision: keep Manifest V2 alive, or build a native engine (as Brave does with `adblock-rust`, MPL-2.0)
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
- [x] **P5.13** Native ad blocking, spike: link `adblock-rust` into a 158 build, block with EasyList, measure (throwaway)
- [x] **P5.14** Native ad blocking, engine: vendored crates (licence-checked, credited), C++ bridge, request throttle, `ERR_BLOCKED_BY_CLIENT`, redirect resources, tests
- [x] **P5.15** Native ad blocking, lists: compiled lists bundled in each release, safe background updates, validation that never falls back to "allow everything"
- [ ] **P5.16** Native ad blocking, UI: per-site switch in page info and Settings; local blocked-count badge
- [ ] **P5.17** Native ad blocking, proof: the measurements in the design's section 9 (blocking, speed, CPU, memory, breakage) and fuzzing; on by default only when all pass
- [ ] **P5.18** Native ad blocking, later: CNAME uncloaking
- [x] **P5.19** Native ad blocking, resources and stand-ins: uBlock Origin's scriptlets and redirect resources taken from the pinned package at build time; a blocked request with a `$redirect` or `redirect-rule` filter is answered with the harmless stand-in instead of an error
- [x] **P5.20** Native ad blocking, scriptlets and site-specific cosmetic filtering: sent to the renderer with the document and applied at document start; trusted scriptlets only from uBlock Origin's own lists
- [x] **P5.21** Native ad blocking, generic cosmetic filtering: the page reports its classes and ids, the engine answers with the selectors to hide
- [x] **P5.22** Native ad blocking, the rest of the syntax: procedural cosmetic filters, `$removeparam`, `$csp`
- [ ] **P5.23** Native ad blocking, signed updates of scriptlets and resources between releases
- [ ] **P5.24** Native ad blocking, hand-over from uBlock Origin: new profiles no longer get the built-in uBlock Origin once native blocking is on by default; a one-time notice when both run; existing profiles untouched
- [x] **P5.25** Native ad blocking, redirect hops: a request that a server redirects is checked again at each hop, so a redirect to a blocked host is blocked and a redirect to an address with a `$removeparam` parameter is cleaned (uBlock Origin does both; found while building P5.22)
- [x] **P5.26** Native ad blocking, the filter syntax still missing: `$urlskip` (238 rules in the bundled lists), `$replace` (76, trusted lists only), `$header` (39), `$uritransform` (14), `$permissions` (11), `:shadow()` (2), HTML filtering
- [x] **P5.27** Native ad blocking, the requests that do not pass the request proxy: the main script of a worker and of a service worker, prefetches, preloads announced by early hints, downloads (found while building P5.25)
- [x] **P5.28** Native ad blocking, preloads announced by early hints: Chromium fetches them without asking the browser layer or extensions, so a server can make the browser ask a tracker for a script before its page arrives (the script does not run; uBlock Origin cannot see these either)
- [x] **P5.29** Native ad blocking, WebSocket connections: a WebSocket is not a request for a file, so the request proxy never saw it; uBlock Origin blocks such connections
- [x] **P5.31** Native ad blocking, the shield in the toolbar and its menu, like uBlock Origin's: a badge with what was blocked on the page; a menu with the switch for the site, the counts, the blocked sites, the per-site switches (pop-ups, large media, no hiding, remote fonts, JavaScript) and the tools
- [x] **P5.32** Native ad blocking, the element picker and zapper, from the menu: pick an element, choose or edit a rule (specific to general, or the address of an image or frame), preview, create; the zapper removes elements until a reload
- [x] **P5.33** Native ad blocking, the dashboard like uBlock Origin's: the sites where ads are allowed and the per-site switches (each removable), a live logger of blocked requests per tab, the total
- [x] **P5.34** Native ad blocking, uBlock Origin's optional lists on `chrome://adblock`: cookie notices, annoyances, privacy, phishing, regions and languages, grouped, one checkbox each
- [x] **P5.35** Native ad blocking, no empty boxes where ads were: a blocked image, frame or embedded object is collapsed, as uBlock Origin hides placeholders
- [x] **P5.36** Native ad blocking, pop-ups: the lists' `$popup` rules (and `$all`) keep a page from opening ad windows, and the menu's "no pop-ups" stops every window of a site, as in uBlock Origin
- [x] **P5.37** Native ad blocking, strict blocking as in uBlock Origin: a page a rule for whole pages (`$doc`, `$all`) or a rule for its whole host blocks is not opened, and a page says why
- [x] **P5.38** Native ad blocking, Settings as uBlock Origin's on `chrome://adblock`: the badge, the privacy options, the default behavior for every site with exceptions from the menu, ignoring generic hide rules
- [x] **P5.39** Native ad blocking, the menu's counts as uBlock Origin's: the share of the page's requests blocked, and the domains connected out of all
- [ ] **P5.30** Native ad blocking, a page in Settings that a person can work with: one switch for the blocker; the filter lists with a checkbox each; add a list by its address and remove it again; "My filters", the person's own rules in the syntax of the lists; the sites where blocking is off

**Security (S)**

- [x] **S.1** Audit every upstream merge and release with `tools/audit` (`--strict`, with every finding reviewed by a human)
- [ ] **S.2** Threat model for the updater, import and portable encryption (`docs/security/THREAT_MODEL.md`)
- [x] **S.3** Remove `'unsafe-inline'` from the Thorium authors WebUI page CSP
- [x] **S.4** Review every flag that weakens security (for example `allow-insecure-downloads`, `disable-web-security`, `disable-encryption`); each must stay opt-in and carry a warning
- [ ] **S.5** Sandbox verification every release (Windows sandbox; Linux AppArmor and user namespaces)
- [x] **S.6** Enable GitHub Issues and private vulnerability reporting for the repository, before the docs that link to them go public (part of P0.11)
- [x] **S.7** Every patch carries `Origin:`, `Author:` and `License:` headers (with L.1)
- [ ] **S.8** Authenticode code signing once a certificate exists
- [ ] **S.9** Security-release process: watch Chrome Releases, triage, fast-track build within the G2 targets
- [ ] **S.10** Publish the list of every network endpoint Thoron contacts and why (upstream #126)
- [x] **S.11** Remove Thorium's hidden Easter-egg WebUI pages (`chrome://eggs`, `chrome://robot`) from Thoron: a professional product with a smaller WebUI attack surface (pairs with S.3)
- [x] **S.12** Content standards: written policy in `CONTRIBUTING.md`, plus an automatic `adult_content` check in `tools/audit` (added text and file names, `--strict`)
- [x] **S.13** Inherited history cleaned: three inappropriate image files that upstream added in 2023 and later deleted were purged from every commit; the current tree is unchanged; they were verified absent from the M150 browser build
- [ ] **S.14** Safe Browsing decision: without Google API keys the built-in Safe Browsing cannot query Google; choose between a key-free setup, another provider, or Google's service with the user's consent, and measure what it contacts
- [ ] **S.15** Turn off the Google contacts a fresh profile makes without need: optimization guide hints (`optimizationguide-pa.googleapis.com`), Google sign-in checks (`accounts.google.com`) and the `www.google.com` requests, measured in `docs/security/NETWORK.md`
- [ ] **S.16** Chromium's Gemini plumbing ("Glic") in a browser that cannot use it: Chromium 158 registers its internal "Gemini in Chrome" component extension in every profile it opens and shows "AI innovations" in Settings, a feature Thoron does not want: Gemini works for a Google account signed in to the browser, which the Google credentials inherited from upstream still allow (L.8); turn the feature and its component off by default, so that nothing of it is loaded or shown

**Quality & performance (Q)**

- [ ] **Q.1** Benchmark suite `tools/qa/bench`: Speedometer 3, JetStream 2, MotionMark, start-up with 1 and 4 profiles, idle and 20-tab memory, idle CPU
- [ ] **Q.2** Baselines: Thorium M156 and Chrome of the same major version
- [ ] **Q.3** Regression gate in the release script (a release is blocked until any regression is explained)
- [ ] **Q.4** Memory-leak soak test (8 h of tab churn; memory-growth threshold)
- [ ] **Q.5** Crash triage process (local Crashpad dumps; symbol publication decision)
- [ ] **Q.6** Test VMs: Windows 11 x64, Ubuntu 24.04 and 26.04 x64, clean snapshots
- [x] **Q.7** Profile compatibility gate: a new version is first started offline on a copy of real profiles, and `tools/qa/profile_check.py` must report 1:1 (windows, tabs, pinned tabs, tab groups with names and colours, saved passwords, bookmarks, enabled extensions, cookies within normal expiry, cookie encryption unchanged, no new app-bound key); it never decrypts or prints secrets

**Docs (D)**

- [ ] **D.1** Keep README, ROADMAP, CHANGELOG, CREDITS, NOTICE and docs current on every change (definition of done)
- [ ] **D.2** User guides: install, import, updates and rollback, portable passphrase (`docs/user/`)
- [x] **D.3** ~~Repair broken links in upstream docs~~: the old upstream docs were removed from `main` with the rest of the unused M138 tree (D.8); the two kept copies in `docs/upstream/` link to the originals
- [ ] **D.4** Release notes for every release (generated by `changelog.py`, highlights written by a person)
- [x] **D.5** Rebrand the GitHub issue and PR templates for Thoron (bug, feature, ARM beta report, security redirect)
- [ ] **D.6** Repository identity: renamed to `KuchiSofts/thoron` with Thoron description and topics; the owner asks GitHub Support to detach it from the Thorium fork network and to remove cached views and old pull-request references to purged history
- [x] **D.7** README shows the live roadmap: overall progress, per-phase bars, what's next and the full task list, generated from this file by `tools/docs/roadmap_progress.py`; `check_docs` fails if it is stale, and validates every heading anchor
- [x] **D.8** Repository cleanup: remove the unused upstream Thorium M138 tree from `main` (sources, logos, infra, old build scripts, submodules, old docs, about 1,500 files) so `main` holds only Thoron's own work; keep Thorium's M138 `PATCHES.md` and README as licence evidence; drop the upstream Sponsor button; Thoron issue templates
- [ ] **D.9** Project wiki: what Thoron is, install, update, import, privacy and security, versions, building, questions and answers; updated with every release
- [ ] **D.10** Short changelog: one line per change under Added, Changed, Fixed, Removed and Security, per Thoron version; the long explanations stay in the design docs

**Legal & licensing (L)**

- [ ] **L.1** Licence inventory of every patch (origin, author, licence); resolve pending sources (Debian, chromium-ubuntu-build, Vanadium, Supermium); rewrite or drop anything incompatible
- [ ] **L.2** GPL compliance per release: source tag and Chromium tag in `BUILDINFO`, GPL text in the licence bundle, notes in the release
- [ ] **L.3** Regenerate contributors and update `NOTICE` and `CREDITS` every release
- [ ] **L.4** Courtesy note to Alex313031 and gz83 introducing Thoron and its credits
- [ ] **L.5** Name and logo check: "Thoron" in trademark registries and existing software in target markets; logo similarity to other browser marks (for example Chrome's three-segment logo)
- [x] **L.6** No prebuilt or proprietary binaries in the repository: removed the Widevine CDM (Google proprietary, no redistribution right), Flash Player (Adobe, end-of-life), `shc`-compiled launchers whose embedded script cannot be verified, and prebuilt tools and packages; `tools/audit/binary_policy.py` enforces it
- [ ] **L.7** Remove those binaries from the repository's git history as well, and include them in the GitHub Support cache request (D.6)
- [ ] **L.8** Google API keys and OAuth credentials compiled in by upstream's `thorium-default-api-keys.patch` belong to Google and other projects; decide before the first release whether Thoron ships without them (Google sync, sign-in, translation and Safe Browsing then off, see S.14) or with keys of its own; kept for now by the owner's decision (2026-11-09); the patch that carries them is withheld from `source/` (P2.25), so the repository does not publish them

**Branding (B)**

- [x] **B.1** Icon concepts (3 original concepts, previews at 16-256 px on light and dark backgrounds) and the owner's choice
- [x] **B.2** Final asset set: colour and mono SVG, PNG 16-512, multi-size `.ico`
- [ ] **B.3** Chromium resource integration: product logos, `.ico`, installer images, Linux icons, About page and new-tab logo
- [ ] **B.4** Release-page and social preview visuals

</details>
<!-- roadmap:end -->

## Platforms

| Platform | When | Packages |
|---|---|---|
| Windows 11 x64 (AMD, Intel) | first | `ThoronSetup.exe`, full installer |
| Windows 11 ARM64 | later | installer, portable `.zip` |
| Ubuntu 24.04 / 26.04 LTS, x64 and ARM64 | later | `.deb` via a signed APT repository, portable `.tar.xz` |

Windows comes first. ARM64 builds stay labelled *beta* until they have been tested on real devices.

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

Thoron's own build guides, each step verified on a real build:
[Windows 11](docs/build/WINDOWS.md) (toolchain, source, Thoron identity, build and smoke test) and
[Linux / Ubuntu 24.04](docs/build/LINUX.md) (WSL2 or native), with measured build times in
[`BUILD_BUDGET.md`](docs/build/BUILD_BUDGET.md). The original Thorium guides are in the
[Thorium repository](https://github.com/Alex313031/thorium/tree/main/docs).

The repository tooling (audit, docs and credits checks) needs only Python 3.11+:

```shell
py -3 -I -m unittest discover -s tools -t . -p "test_*.py" -v   # tests
py -3 -I tools/docs/check_docs.py                               # docs, links, house style
py -3 -I tools/audit/binary_policy.py                            # no prebuilt or proprietary binaries
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
