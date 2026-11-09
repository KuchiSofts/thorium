# Thoron Roadmap

Thoron aims to be the fastest, smartest and most secure Thorium-based browser for **Windows 11** and
**Ubuntu**, on **x64 (AMD, Intel)** and **ARM64**:
- built from traceable source;
- updated quickly and safely with signed delta updates;
- never touching user data;
- with full credit to everyone it builds on.

**Last updated:** 2026-11-08
**Status legend:** ⬜ todo · 🔄 in progress · ✅ done · ⛔ blocked

Design (the "why" behind every item): [`docs/design/2026-11-07-thoron-design.md`](docs/design/2026-11-07-thoron-design.md) ·
Changes: [`CHANGELOG.md`](CHANGELOG.md) · Credits: [`CREDITS.md`](CREDITS.md)

---

## How this roadmap works

- **IDs.**
  - Every task has a permanent ID: `P<phase>.<n>` for phases, and `S.n`, `Q.n`, `D.n`, `L.n`, `B.n`
    for the cross-cutting tracks.
  - IDs are never reused or renumbered. New work gets the next free number.
- **Task lines** follow this shape: `- [ ] **ID** Title - *Role* · *Depends* · *Done when*`.
- **Marking progress:**
  - A task in progress ends with `· 🔄`.
  - A blocked task ends with `· ⛔ <reason>`.
  - A finished task becomes `- [x]` and ends with `· ✅ YYYY-MM-DD`.
- **Roles:** Chromium engineer, Release engineer, Security researcher, QA/performance engineer, Docs
  maintainer, and Owner (decisions and actions only the project owner can take).
- **Definition of done** for every task, from [`CONTRIBUTING.md`](CONTRIBUTING.md):
  - tests pass;
  - security review done;
  - **this file, `CHANGELOG.md`, and every affected doc updated in the same change**;
  - copyright and attribution kept.
- `tools/docs/check_docs.py` enforces this file's format.

## Phase summary

| Phase | Goal | Status | Exit criteria | Depends on |
|---|---|---|---|---|
| [P0](#p0---foundation) | Repository foundation: docs, credits, tooling, brand | ✅ | P0.1-P0.11 done; owner approved push | - |
| [P1](#p1---build-environment) | Reproduce upstream M156 from source on Windows and Linux; measure (build work done; open: P1.9 on a clean Windows machine, L.1 permission or rewrite for 6 patches) | 🔄 | M156 builds reproduced on both OSes; MV2 verdict; licence inventory complete | P0 |
| [P2](#p2---first-release) | First Thoron release on Chromium 158 (x64) | ⬜ | Signed draft release with full changelog, published by the owner | P1 |
| [P2b](#p2b---arm64) | ARM64 builds for Windows and Linux | ⬜ | ARM64 releases published (beta until device-tested) | P2 |
| [P3](#p3---updater-v1--import) | Updater v1 (full packages) and import from other browsers, including tabs and tab groups | ⬜ | Safe update and rollback; import from the Chromium family | P2 |
| [P4](#p4---updater-v2) | Delta updates, smart behaviour, Firefox import, portable passphrase encryption | ⬜ | Deltas shipped; portable encryption passes its security review | P3 |
| [P5](#p5---quality) | uBlock migration, ad-blocking decision, performance, Windows bug fixes | ⬜ | Issue map items resolved or explained | P2 (some items P3) |
| [Ongoing](#release-policy) | Security releases on schedule, docs current, audits | 🔄 | - | - |

---

## P0 - Foundation

**Goal:** a professional, honest, fully credited home for Thoron before any binary exists.
**Deliverables:** approved design, docs set, tested tooling (audit, docs linter, credits generator),
and the Thoron icon.

- [x] **P0.1** Feature branch, private noreply commit identity, approved design committed - *Role:* Release engineer · *Depends:* - · *Done when:* the design doc is in `docs/design/` and commits carry the GitHub noreply address · ✅ 2026-11-07
- [x] **P0.2** Audit toolkit (`tools/audit`: `audit_diff`, `crx_id`, `compare_release`) - *Role:* Security researcher · *Depends:* P0.1 · *Done when:* unit tests pass, and the smoke run on upstream M156 completes with known findings only · ✅ 2026-11-07
- [x] **P0.3** Docs and privacy linter (`tools/docs/check_docs.py`) - *Role:* Docs maintainer · *Depends:* P0.1 · *Done when:* tests pass; it detects broken links, malformed CHANGELOG/ROADMAP, and personal data without echoing it · ✅ 2026-11-07
- [x] **P0.4** Contributor credits generator (`tools/credits/contributors.py`) - *Role:* Docs maintainer · *Depends:* P0.1 · *Done when:* tests pass; bots excluded; anonymous contributors credited by name only · ✅ 2026-11-07
- [x] **P0.5** `CREDITS.md` and `NOTICE` - *Role:* Docs maintainer · *Depends:* P0.4 · *Done when:* every upstream author and patch source is credited; licences listed, with unverified ones marked pending (L.1) · ✅ 2026-11-07
- [x] **P0.6** Thoron README; original Thorium README preserved at `docs/upstream/` - *Role:* Docs maintainer · *Depends:* P0.5 · *Done when:* the README carries the verbatim disclaimer, platforms, commitments and credits; all links resolve · ✅ 2026-11-07
- [x] **P0.7** This roadmap - *Role:* Docs maintainer · *Depends:* P0.6 · *Done when:* every design item has a task with "done when" criteria; linter passes · ✅ 2026-11-07
- [x] **P0.8** `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md` - *Role:* Security researcher / Docs maintainer · *Depends:* P0.7 · *Done when:* private reporting process, definition of done, and Keep-a-Changelog format are in place · ✅ 2026-11-07
- [x] **P0.9** Thoron icon concepts and the owner's choice (see B.1) - *Role:* Owner / Docs maintainer · *Depends:* P0.1 · *Done when:* the owner has picked a concept from previews at 16-256 px on light and dark backgrounds · ✅ 2026-11-07
- [x] **P0.10** Icon asset pipeline and generated icons (see B.2) - *Role:* Release engineer · *Depends:* P0.9 · *Done when:* PNG 16-512 and a multi-size `.ico` are generated by a tested tool · ✅ 2026-11-07
- [x] **P0.11** Final verification and owner-approved push - *Role:* Owner / Release engineer · *Depends:* P0.1-P0.10, S.6 · *Done when:* all tests and the linter pass, the privacy guard passes, an independent review's findings are fixed, GitHub Issues and private vulnerability reporting are enabled (S.6), and the owner explicitly approves the push · ✅ 2026-11-07

## P1 - Build environment

**Goal:** prove we can build what upstream ships, from source, on the owner's PC, and measure the
risks before changing anything.
**Also in this phase:** L.1 (licence inventory), Q.1 and Q.2 (benchmark suite and baselines).

- [x] **P1.1** Windows toolchain: Visual Studio 2026 (Desktop C++, ATL/MFC), Windows SDK 10.0.28000 plus Debugging Tools, pinned depot_tools, NTFS checkout on a fast local drive that is not cloud-synced - *Role:* Release engineer · *Depends:* P0 · *Done when:* `gn gen` succeeds for stock Chromium 156; tool versions recorded in `docs/build/WINDOWS.md` · ✅ 2026-11-07
- [x] **P1.2** Linux toolchain in WSL2 Ubuntu 24.04: ext4 disk of at least 150 GB, `install-build-deps`, x64 and arm64 sysroots - *Role:* Release engineer · *Depends:* P0 · *Done when:* `gn gen` succeeds for linux-x64 and linux-arm64 targets; recorded in `docs/build/LINUX.md` · dedicated Ubuntu 24.04 distro; stock 156 generates 36,414 targets (x64) and 44,326 (arm64) · ✅ 2026-11-08
- [x] **P1.3** Local-only worktree of gz83 tag `M156.0.8078.28` (`de9a1bc6`, never pushed); fetch Chromium 156.0.8078.28; apply the upstream patch series - *Role:* Chromium engineer · *Depends:* P1.1 · *Done when:* the series applies with 0 rejects; the apply log is kept · 149 of 152 patches apply cleanly for the AVX2 profile (the other 3 are SSE2/Raspberry Pi only) · ✅ 2026-11-07
- [x] **P1.4** Reproduce the Windows x64 AVX2 build of M156 - *Role:* Release engineer · *Depends:* P1.3 · *Done when:* the build launches with a fresh `--user-data-dir`; build time and disk use recorded · 2 h 35 min, 12.4 GB output, smoke test passed (`docs/build/BUILD_BUDGET.md`) · ✅ 2026-11-08
- [x] **P1.5** Reproduce the Linux x64 build of M156 in WSL2 - *Role:* Release engineer · *Depends:* P1.2, P1.3 · *Done when:* it launches under WSLg **with the sandbox enabled** (never `--no-sandbox`) · built in 2 h 37 min, 0 rejects; launches under WSLg; renderers run with seccomp-BPF in their own PID namespace · ✅ 2026-11-08
- [x] **P1.6** `BUILDINFO.json` generator: Chromium tag, Thoron commit, depot_tools revision, VS/SDK versions, GN args hash, build time - *Role:* Release engineer · *Depends:* P1.4 · *Done when:* the generator has unit tests, and its output is attached to each build · ✅ 2026-11-07
- [x] **P1.7** Smoke-test harness (`tools/build/smoke.py`): fresh profile; local pages for JS, WebGL, H.264/HEVC/AV1 video, JPEG XL; no crash dumps - *Role:* QA engineer · *Depends:* P1.4, P1.5 · *Done when:* it exits 0 on both M156 builds and fails on an injected crash · passes on both M156 builds and the Thoron build, with the sandbox proven on each (Windows: renderer token below Medium integrity; Linux: seccomp-BPF and own PID namespace); crash dumps, empty results and missing capabilities fail it (tests) · ✅ 2026-11-08
- [x] **P1.8** Manifest V2 / uBlock Origin viability on Chromium 158: apply the MV2 patches to 158 and load uBO 1.75 - *Role:* Chromium engineer · *Depends:* P1.3 · *Done when:* a verdict (works / needs patches X / fails) is recorded in design §10; it feeds P5.2 · verdict in design §10.1: MV2 itself works on 158 (a minimal MV2 blocker blocks every request); uBlock Origin 1.75.4 hangs at start-up because `chrome.storage.managed.get` never answers on the 158 test build (follow-up **P2.18**); rebase report in `docs/build/M158_REBASE_REPORT.md` · ✅ 2026-11-08
- [ ] **P1.9** Thoron build docs written from scratch and followed end-to-end - *Role:* Docs maintainer · *Depends:* P1.4, P1.5 · *Done when:* a fresh setup that follows only `docs/build/*` succeeds · Linux: followed end to end on a fresh distro; Windows: still to be followed on a clean Windows machine (Q.6) · 🔄
- [x] **P1.10** Release build-matrix time budget (Windows/Linux × AVX2/SSE4, plus ARM64) against the G2 targets - *Role:* Release engineer · *Depends:* P1.4, P1.5 · *Done when:* measured times and a plan (which variants, which order, a second machine?) are documented · both AVX2 builds measured (about 2.5 h each); plan in `docs/build/BUILD_BUDGET.md` · ✅ 2026-11-08

## P2 - First release

**Goal:** the first Thoron release on current Chromium (158), x64 only, built and signed by us, with a
full changelog.
**Also in this phase:** B.3 (icon integration), S.1 (audit), L.2 (GPL compliance), Q.2 and Q.3
(benchmarks and gate).

- [x] **P2.1** Branch `ks/M158`; rebase the upstream patch series from 156 to Chromium 158.0.8127.x - *Role:* Chromium engineer · *Depends:* P1 · *Done when:* all patches apply; every refreshed patch keeps its original attribution header · series rebased on upstream 156.0.8078.80 (`efc0fff`, audited): all 153 patches apply exactly on 158.0.8127.30 (150 for the x64 builds, plus 1 SSE2 and 2 Raspberry Pi patches), 25 ported by hand, Android-only patches not carried over, every patch carries its origin, author and licence; decisions in `docs/build/M158_REBASE.md`; the first 158 build and its checks continue in P2.23 · ✅ 2026-11-09
- [ ] **P2.2** Audit all upstream changes since `de9a1bc6` with `tools/audit` (S.1) - *Role:* Security researcher · *Depends:* P2.1 · *Done when:* every finding is reviewed, and the summary is included in the release notes
- [x] **P2.3** Identity patch, Windows: product name Thoron, `%LOCALAPPDATA%\Thoron`, `HKCU\Software\Thoron`, new app GUID in `chromium_install_modes.h`, ProgIDs, AppUserModelID - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* Thoron installs and runs **side by side** with upstream Thorium, with separate profiles · done first on M156 by `tools/build/thoron_identity.py` (re-applied after every rebase); verified: installs next to Thorium without changing it, separate profile, smoke test passes · ✅ 2026-11-08
- [ ] **P2.4** Identity patch, Linux: package `thoron-browser`, `.desktop` file, `~/.config/thoron`; the keyring entry stays `Chromium Safe Storage` (shared with Thorium, so imported passwords stay readable) - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* it coexists with upstream `thorium-browser` on Ubuntu · code done in `tools/build/thoron_identity.py` (`LINUX_EDITS`), checked against the real 158 files; open: a Linux build and the coexistence test · 🔄
- [ ] **P2.5** About page: Thoron version, Chromium version, verbatim disclaimer, links to credits and changelog - *Role:* Chromium engineer · *Depends:* P2.3 · *Done when:* `chrome://settings/help` shows them; `chrome://credits` is complete · `other/ks-about-page.patch`: below the version, "Based on Chromium <version>" (computed back from the Thoron version when `chrome/VERSION` carries `THORON_REBUILD`), the verbatim disclaimer and a release notes link; credits were already linked; open: check the page in a running build · 🔄
- [ ] **P2.6** Widevine not bundled; fetched by Chromium's component updater at runtime - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* the packages contain no Widevine binaries (checked automatically); DRM test pages play, with any limits documented · `tools/release/package_audit.py` checks a package for a bundled Widevine module, Thorium-named files and upstream-only extras; open: run it on the 158 packages and the DRM test · 🔄
- [ ] **P2.7** Variants AVX2 and SSE4 for Windows x64 and Linux x64 - *Role:* Release engineer · *Depends:* P2.1 · *Done when:* both build; the SSE4 build runs under Intel SDE emulating a CPU without AVX (Westmere) with no illegal-instruction crash
- [ ] **P2.8** Windows packaging: Thoron mini_installer, portable `.zip` with launcher - *Role:* Release engineer · *Depends:* P2.3, P2.7 · *Done when:* install, run, uninstall keeps `User Data` by default; portable runs from paths with spaces and Unicode, and from a USB drive
- [ ] **P2.9** Linux packaging: `.deb` with an AppArmor profile for user namespaces, plus portable `.tar.xz` - *Role:* Release engineer · *Depends:* P2.4, P2.7 · *Done when:* it installs on clean Ubuntu 24.04 and 26.04 VMs; `chrome://sandbox` is fully green; lintian reports no errors
- [ ] **P2.10** Signed APT repository on GitHub Pages (fixes the unsigned-repo problem of upstream #1164 and #1049) - *Role:* Release engineer · *Depends:* P2.9, P2.11 · *Done when:* `apt update` verifies the signature with a `signed-by` keyring; a tampered `InRelease` is rejected
- [ ] **P2.11** Key ceremony: Ed25519 release key (minisign) and APT signing key, offline root, encrypted backups - *Role:* Owner / Security researcher · *Depends:* P1 · *Done when:* keys are generated offline; backup restore is tested by sign/verify; `docs/release/KEYS.md` documents the procedure (no secrets); public keys are in the README
- [ ] **P2.12** Release script `tools/release/release.py`: build matrix → package → `SHA256SUMS` → sign → `BUILDINFO` → **draft** GitHub release; sets the version and refuses a non-increasing one with `tools/release/version.py` (P2.14) - *Role:* Release engineer · *Depends:* P1.6, P2.8, P2.9, P2.11 · *Done when:* a dry run produces the complete artifact set; publishing requires an explicit owner action
- [ ] **P2.13** `tools/release/changelog.py`: release notes generated from commit prefixes, upstream merges (author-credited), the Chromium version diff and security fixes (CVE and severity), patch changes, and issues - *Role:* Release engineer · *Depends:* P2.1 · *Done when:* tested on fixture repos; the owner reviews the generated notes for 158 · `tools/release/changelog.py` written and tested on fixture repos (sections in design order, upstream commits credited by author, no emails, house style); open: the owner reviews the 158 notes · 🔄
- [ ] **P2.14** Version scheme for Thoron rebuilds of the same Chromium version (4-part numeric, Windows-installer compatible) - *Role:* Release engineer · *Depends:* P2.1 · *Done when:* the scheme is documented in design §14 and enforced by the release script · scheme decided and documented (`PATCH = Chromium patch x 100 + rebuild`, so `158.0.8127.3000`, `.3001`, ...); `tools/release/version.py` sets and checks it; open: the release script (P2.12) calls it · 🔄
- [ ] **P2.15** First draft release, Thoron 158.x (Windows x64 and Linux x64) - *Role:* Owner / Release engineer · *Depends:* P2.1-P2.14, P2.16-P2.18, P2.20, P2.21, B.3, L.1, L.2, Q.3 · *Done when:* smoke tests pass on both OSes; benchmarks are recorded against Thorium M156 and Chrome 158; the owner publishes
- [ ] **P2.16** No silent Web Store installs: Thorium's default apps install uBlock Origin from the Chrome Web Store into every new profile, contacting Google when the profile is created; Thoron ships its bundled, SHA-256-pinned uBlock Origin instead and installs nothing from the network without the user's consent - *Role:* Security researcher · *Depends:* P2.1 · *Done when:* a test shows a fresh profile makes no extension download request and has the bundled uBlock Origin
- [x] **P2.17** Privacy review of the inherited build configuration, for example `enable_rlz = true` (Google's promotional RLZ library) and any other upstream GN arg that adds network contact or tracking - *Role:* Security researcher · *Depends:* P2.1 · *Done when:* every such arg is set deliberately, with its reason recorded next to the release build configuration · `tools/build/release_args.py` composes and checks the release `args.gn`; RLZ, the CDM storage ID and Google API keys are off, Widevine is not bundled; review in `docs/build/RELEASE_ARGS.md` · ✅ 2026-11-09
- [ ] **P2.18** uBlock Origin runs on 158: check whether `chrome.storage.managed.get` also hangs in the release configuration and for normally installed extensions; fix it (patch or configuration); verify cosmetic filtering with a normally installed extension in a visible window - *Role:* Chromium engineer · *Depends:* P1.8, P2.1 · *Done when:* `tools/build/mv2_check.py` reports "works" for the bundled uBlock Origin on the release build
- [ ] **P2.19** Thoron's own COM interface IDs (IElevator, tracing service): regenerate the checked-in MIDL output; needed before system-level installs, which register those interfaces - *Role:* Chromium engineer · *Depends:* P2.3 · *Done when:* a system-level Thoron and Thorium share no COM registration
- [x] **P2.20** Program and installer file names: `thoron.exe` instead of `thorium.exe`, the installer name, and no Thorium updater remnants (`thor_ver`) - *Role:* Chromium engineer · *Depends:* P2.3 · *Done when:* no file in a Thoron install is named after Thorium; no registry entry keyed by the program file name (`App Paths`, `Applications`, `OpenWithList`) is shared with Thorium; install, update and uninstall still work and leave Thorium untouched · `thoron.exe` and `thoron_AVX2_mini_installer.exe` on M156; the installer ships no Thorium-named file; Thoron and Thorium each have their own `App Paths` entry; installed over the owner's daily Thoron with a verified backup, the move-over tool (`tools/migrate/exe_rename.py`) and a 1:1 profile check · ✅ 2026-11-08
- [ ] **P2.21** Linux program and package names: `thoron` instead of `thorium` for the binary, the `.deb`/`.rpm` packages, the `.desktop` file and the icons; the developer test shell and the prebuilt `pak` tool are not packaged - *Role:* Chromium engineer · *Depends:* P2.20 · *Done when:* no installed Linux file is named after Thorium; a package upgrade keeps the profile 1:1 · done in code with P2.4 (program `thoron`, package `thoron-browser` in `/opt/kuchisofts/thoron`); open: the Linux build · 🔄
- [ ] **P2.22** Linux dark mode on 158: check whether Chromium 158 follows a GTK theme switch on its own; if not, write Thoron's own fix (the Thorium patch was not carried over, see `docs/build/M158_REBASE.md`) - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* switching the GTK theme between light and dark updates the browser and web content without a restart
- [ ] **P2.23** Check the hand-ported UI patches in a running 158 build: tab search button on the right (default) and on the left (flag), Thorium 2024 UI, classic omnibox, rectangular tabs, custom tab width, open link in this tab - *Role:* QA engineer · *Depends:* P2.1 · *Done when:* each looks and works as on 156 (screenshots recorded)

## P2b - ARM64

**Goal:** ARM64 builds for Windows 11 (for example Snapdragon X) and Ubuntu, labelled *beta* until
tested on real devices.

- [ ] **P2b.1** Windows ARM64 build, cross-compiled on the x64 host; installer and portable - *Role:* Release engineer · *Depends:* P2.15 · *Done when:* artifacts are produced; PE machine type and imports are checked automatically
- [ ] **P2b.2** Linux ARM64 build, cross-compiled with the arm64 sysroot; `.deb` and portable - *Role:* Release engineer · *Depends:* P2.15 · *Done when:* artifacts are produced; ELF architecture is checked automatically
- [ ] **P2b.3** Emulated smoke tests (qemu-user plus headless for Linux ARM64; static checks for Windows ARM64) - *Role:* QA engineer · *Depends:* P2b.1, P2b.2 · *Done when:* the Linux ARM64 headless smoke test passes under QEMU
- [ ] **P2b.4** Beta programme: ARM issue template and community tester checklist - *Role:* Docs maintainer · *Depends:* P2b.3 · *Done when:* 3 independent tester reports per platform are collected
- [ ] **P2b.5** Real-device validation (Windows-on-ARM laptop, ARM64 Linux device); beta label removed - *Role:* Owner / QA engineer · *Depends:* P2b.4 · *Done when:* the full smoke and benchmark run passes on real hardware

## P3 - Updater v1 + Import

**Goal:** safe, signed, full-package updates for installed and portable copies (no admin, never
touching the profile, one-step rollback), plus import from the user's chosen browser, **including
open tabs and tab groups**.
**Also in this phase:** S.2 (threat model).

- [ ] **P3.1** Update manifest schema v1 and spec `docs/update/MANIFEST.md` (channel, version, Chromium version, `critical`, `min_updater_version`, `expires`, per-variant full and delta entries) - *Role:* Release engineer · *Depends:* P2.15 · *Done when:* the schema validator has tests with valid and invalid samples
- [ ] **P3.2** Manifest signing in the release script (Ed25519, detached signature) - *Role:* Release engineer · *Depends:* P2.11, P3.1 · *Done when:* the signed manifest verifies; flipping any byte fails verification
- [ ] **P3.3** Updater core (C++, in-tree, BoringSSL): fetch over HTTPS, **verify the signature before parsing**, anti-downgrade, expiry handling - *Role:* Chromium engineer · *Depends:* P3.1, P3.2 · *Done when:* unit tests prove it rejects bad signatures, older manifests and malformed JSON, and reports "cannot verify" on an expired manifest
- [ ] **P3.4** Download and verify (size plus SHA-256) for full packages - *Role:* Chromium engineer · *Depends:* P3.3 · *Done when:* tests prove it rejects corrupted or truncated downloads and never installs an unverified file
- [ ] **P3.5** Staging and atomic swap: `<new>.staging` → verify every file → rename; keep N-1 - *Role:* Chromium engineer · *Depends:* P3.4 · *Done when:* killing the updater at every step always leaves a launchable browser
- [ ] **P3.6** In-use update: Chromium's `new_thoron.exe` rename on Windows, and the launcher swap on Linux per-user and portable installs; relaunch badge - *Role:* Chromium engineer · *Depends:* P3.5 · *Done when:* updating while the browser runs, then relaunching, gives the new version; the profile is byte-identical except for normal browsing changes
- [ ] **P3.7** Profile snapshot before major-version updates (critical files of all profiles, verified, last 2 kept, stored next to `User Data`) - *Role:* Chromium engineer · *Depends:* P3.5 · *Done when:* tested on a real profile copy: hashes and SQLite integrity verified; size reported
- [ ] **P3.8** Rollback: restore N-1 plus the snapshot, with an explicit warning and confirmation - *Role:* Chromium engineer · *Depends:* P3.6, P3.7 · *Done when:* the update → rollback round trip restores the app directory and profile snapshot byte-identically
- [ ] **P3.9** About page updater states: checking, downloading %, ready to relaunch, up to date, cannot verify, error - *Role:* Chromium engineer · *Depends:* P3.3 · *Done when:* every state renders and is covered by a browser test
- [ ] **P3.10** Scheduling without admin rights: Windows per-user task (Limited), Linux systemd user timer, portable only while running - *Role:* Release engineer · *Depends:* P3.6 · *Done when:* no UAC or sudo prompt ever appears; portable leaves no registry or task traces (diffed before and after)
- [ ] **P3.11** Update settings (auto / notify-only / off) and CLI `--check --apply --status --rollback` - *Role:* Chromium engineer · *Depends:* P3.3 · *Done when:* each mode is tested; the CLI returns documented exit codes
- [ ] **P3.12** Portable launcher (a Windows `.exe` replacing the `.bat`; Linux shell launcher) with swap-on-start - *Role:* Release engineer · *Depends:* P3.6 · *Done when:* a portable N-1 → N update works from paths with spaces and Unicode, and from USB drives
- [ ] **P3.13** Import UI in the installer and in Settings → Import: detected browsers and profiles, per-type checkboxes, a "please close <browser>" prompt (never force-closes) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* it detects Thorium, Chrome, Edge, Brave, Vivaldi and Opera profiles on test machines
- [ ] **P3.14** Chromium-family import engine: copy, never move; verify (hash plus SQLite integrity); bookmarks, history, passwords, cookies, extensions, settings, autofill - *Role:* Chromium engineer · *Depends:* P3.13 · *Done when:* every test source's hashes are identical before and after; the imported data is complete · a command-line version exists (`tools/migrate/import_profile.py`: whole-profile copy, every file verified) and a real Thorium profile came out 1:1 in Thoron (Q.7)
- [ ] **P3.15** Tabs and tab-groups import: our own SNSS session parser (windows, tab order, groups with name, colour and collapsed state, pinned and active tab, per-tab history) - *Role:* Chromium engineer · *Depends:* P3.14 · *Done when:* golden files from each browser restore exactly; 24 h of fuzzing finds no crash
- [ ] **P3.16** Linux keyring check: Thoron keeps the `Chromium Safe Storage` entry that Thorium uses, so no key migration is needed; prove it on import - *Role:* Chromium engineer · *Depends:* P3.14 · *Done when:* imported passwords are readable on GNOME (libsecret) and KDE (KWallet) test VMs
- [ ] **P3.17** Guided Chrome password import (Chrome's own CSV export → import → secure delete); never bypasses app-bound encryption - *Role:* Security researcher · *Depends:* P3.14 · *Done when:* the CSV is overwritten and deleted afterwards; covered by a test
- [ ] **P3.18** Import report (counts per type, what was skipped and why; no secrets) - *Role:* Chromium engineer · *Depends:* P3.14 · *Done when:* the report is generated for every import and contains no secret values (checked by a test)

## P4 - Updater v2

**Goal:** small, smart updates plus the remaining import and portable-security features.

- [ ] **P4.1** Delta packages: per-file Zucchini patches from each of the previous 3 releases, per variant - *Role:* Release engineer · *Depends:* P3 · *Done when:* applying a delta reproduces byte-identical files; delta and full sizes are reported for every release
- [ ] **P4.2** Delta-chain selection (smallest total download) with automatic fallback to the full package on any base-hash mismatch - *Role:* Chromium engineer · *Depends:* P4.1 · *Done when:* tests cover the chain, a mismatch, and the fallback
- [ ] **P4.3** Resumable downloads (HTTP range; Windows BITS optional), pause on metered connections, proxy support - *Role:* Chromium engineer · *Depends:* P3.4 · *Done when:* an interrupted download resumes; metered connections pause; corporate proxy tested
- [ ] **P4.4** CPU variant auto-selection (AVX2 / SSE4 / ARM64), plus the portable "moved to another PC" check - *Role:* Chromium engineer · *Depends:* P2.7 · *Done when:* the right variant is chosen in emulated CPU tests; a moved portable copy warns instead of crashing
- [ ] **P4.5** Freeze and expiry protection with clock-skew tolerance - *Role:* Security researcher · *Depends:* P3.3 · *Done when:* a replayed old manifest triggers the "cannot verify updates" state
- [ ] **P4.6** Updater self-update via `min_updater_version` - *Role:* Chromium engineer · *Depends:* P3.3 · *Done when:* an old updater upgrades itself before applying a browser update
- [ ] **P4.7** Signing-key rotation (the old key signs the new key's statement) - *Role:* Security researcher · *Depends:* P3.2 · *Done when:* a rotation drill passes end to end
- [ ] **P4.8** Firefox import: bookmarks, history and passwords via Chromium's importer; tabs and groups from `sessionstore.jsonlz4` - *Role:* Chromium engineer · *Depends:* P3.15 · *Done when:* golden-file tests pass; the parser is fuzzed
- [ ] **P4.9** Portable passphrase encryption: Argon2id-wrapped profile key, remember-this-PC (DPAPI/libsecret), recovery key, read support for old formats - *Role:* Security researcher / Chromium engineer · *Depends:* S.2 · *Done when:* security review signed off; round-trip tests (encrypt → "new PC" → decrypt) pass; key-file parser fuzzed
- [ ] **P4.10** Upstream portable adoption: copy → verify → encrypt the copy → verify decryption → use; original untouched - *Role:* Chromium engineer · *Depends:* P4.9 · *Done when:* the source folder is hash-identical afterwards; every password and cookie is readable in Thoron
- [ ] **P4.11** Optional APT delta support (`debdelta`) - *Role:* Release engineer · *Depends:* P2.10 · *Done when:* evaluated; adopted or rejected with reasons

## P5 - Quality

**Goal:** fix the bugs and make the performance changes users feel, and settle ad blocking for the
long term.

- [ ] **P5.1** uBlock Origin migration for existing profiles (frozen Web Store copy `cjpalh…` → updatable GitHub copy `fkgk…`), keeping settings and custom filters; never forced - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* settings round trip is verified on test profiles; the user is asked first
- [ ] **P5.2** Ad-blocking phase 2 decision: keep Manifest V2 alive, or build a native engine (as Brave does with `adblock-rust`, MPL-2.0) - *Role:* Security researcher / Chromium engineer · *Depends:* P1.8 · *Done when:* a decision document with prototype measurements (speed, memory, maintenance cost)
- [ ] **P5.3** Investigate the M156 Windows CPU spike and "Unknown Hard Error" (#1313) on Thoron builds - *Role:* QA engineer · *Depends:* P2.15 · *Done when:* reproduced and fixed, or shown not to affect Thoron (with the trace evidence)
- [ ] **P5.4** Intermittent breakpoint crash in `sqlite3_dbdata_init` (#1230) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* the root cause is identified, or the crash is not reproducible across a 48 h soak (Q.4)
- [ ] **P5.5** Suspended-tab crash on the AVX-512 build (#1278) - *Role:* Chromium engineer · *Depends:* P5.11 · *Done when:* resolved before any AVX-512 variant ships
- [ ] **P5.6** `STATUS_ACCESS_VIOLATION` on Discord (#1288) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* fixed or not reproducible on Thoron variants
- [ ] **P5.7** HEVC/AV1 playback regression (#1271) and NVIDIA frame drops (#1285) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* the codec test matrix passes on Intel, AMD and NVIDIA GPUs
- [ ] **P5.8** Passwords not saved (#137, #684, #1199) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* password-manager browser tests pass; the reported sites are verified
- [ ] **P5.9** Random logouts and lost sessions (#1005, #458) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* cookie persistence is verified across restarts and updates
- [ ] **P5.10** Slow start-up with multiple profiles (#803) - *Role:* QA engineer · *Depends:* Q.1 · *Done when:* start-up with 4 profiles is no slower than Chrome of the same major version
- [ ] **P5.11** Evaluate an AVX-512 variant (performance gain versus stability) - *Role:* QA engineer · *Depends:* Q.1 · *Done when:* a benchmark-backed decision is recorded
- [ ] **P5.12** Linux hardware video acceleration (VA-API) on current Ubuntu (#1231) - *Role:* Chromium engineer · *Depends:* P2.15 · *Done when:* `chrome://gpu` shows hardware decode on Intel and AMD test machines

---

## Cross-cutting tracks

### Security (S)
- [x] **S.1** Audit every upstream merge and release with `tools/audit` (`--strict`, with every finding reviewed by a human) - *Role:* Security researcher · *Depends:* P0.2 · *Done when:* the toolkit and process exist; the audit is then repeated for every merge · ✅ 2026-11-07
- [ ] **S.2** Threat model for the updater, import and portable encryption (`docs/security/THREAT_MODEL.md`) - *Role:* Security researcher · *Depends:* P2.15 · *Done when:* it is reviewed and every mitigation is mapped to a test
- [ ] **S.3** Remove `'unsafe-inline'` from the Thorium authors WebUI page CSP - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* the page works with Chromium's default WebUI CSP · `other/ks-authors-page-default-csp.patch`: the page has no scripts, so it now uses the default WebUI policy, and it lost its network permission; open: check the page in a running build · 🔄
- [ ] **S.4** Review every flag that weakens security (for example `allow-insecure-downloads`, `disable-web-security`, `disable-encryption`); each must stay opt-in and carry a warning - *Role:* Security researcher · *Depends:* P2.1 · *Done when:* an inventory table exists and no such flag is on by default · reviewed the 68 Thorium flags: all are off by default; the identity step (`OVERLAY_EDITS` in `tools/build/thoron_identity.py`) starts the risky ones (web security, file access, encryption, insecure downloads, password store) with a plain warning, and `other/ks-security-flag-warnings.patch` restores Chromium's unsupported-flag bar for four switches Thorium silenced; open: check in a running build · 🔄
- [ ] **S.5** Sandbox verification every release (Windows sandbox; Linux AppArmor and user namespaces) - *Role:* QA engineer · *Depends:* P2.9 · *Done when:* the release checklist includes `chrome://sandbox` evidence
- [x] **S.6** Enable GitHub Issues and private vulnerability reporting for the repository, before the docs that link to them go public (part of P0.11) - *Role:* Owner · *Depends:* P0.8 · *Done when:* the "Report a vulnerability" button is visible on the Security tab, and Issues are open · ✅ 2026-11-07
- [x] **S.7** Every patch carries `Origin:`, `Author:` and `License:` headers (with L.1) - *Role:* Security researcher · *Depends:* L.1 · *Done when:* a linter rejects patches without them · `tools/legal/patch_headers.py`: `lint` rejects a patch without the three lines or with a licence that differs from the research; `add` wrote them into the 147 upstream patches of the 158 series from the research · ✅ 2026-11-09
- [ ] **S.8** Authenticode code signing once a certificate exists - *Role:* Owner / Release engineer · *Depends:* P2.12 · *Done when:* every Thoron `.exe` and `.dll` is signed and timestamped
- [ ] **S.9** Security-release process: watch Chrome Releases, triage, fast-track build within the G2 targets - *Role:* Security researcher · *Depends:* P2.15 · *Done when:* the runbook is written and a drill meets the 7-day target
- [ ] **S.10** Publish the list of every network endpoint Thoron contacts and why (upstream #126) - *Role:* Security researcher · *Depends:* P2.15 · *Done when:* `docs/security/NETWORK.md` matches observed traffic from a fresh profile
- [ ] **S.11** Remove Thorium's hidden Easter-egg WebUI pages (`chrome://eggs`, `chrome://robot`) from Thoron: a professional product with a smaller WebUI attack surface (pairs with S.3) - *Role:* Chromium engineer · *Depends:* P2.1 · *Done when:* the pages and their resources are gone from the patch series, and `chrome://chrome-urls` lists none of them · removed by `other/ks-remove-easter-egg-pages.patch` (pages, URL constants, network permission and images; `chrome://authors` stays); open: check `chrome://chrome-urls` in a running build · 🔄
- [x] **S.12** Content standards: written policy in `CONTRIBUTING.md`, plus an automatic `adult_content` check in `tools/audit` (added text and file names, `--strict`) - *Role:* Security researcher · *Depends:* S.1 · *Done when:* the policy is published and the check has regression tests · ✅ 2026-11-07
- [x] **S.13** Inherited history cleaned: three inappropriate image files that upstream added in 2023 and later deleted were purged from every commit; the current tree is unchanged; they were verified absent from the M150 browser build - *Role:* Security researcher · *Depends:* - · *Done when:* no commit references them; GitHub cache removal is tracked in D.6 · ✅ 2026-11-07
- [ ] **S.14** Safe Browsing decision: without Google API keys the built-in Safe Browsing cannot query Google; choose between a key-free setup, another provider, or Google's service with the user's consent, and measure what it contacts - *Role:* Security researcher · *Depends:* P2.17, S.10 · *Done when:* the choice is recorded in the design doc and phishing and malware test pages are blocked

### Quality & performance (Q)
- [ ] **Q.1** Benchmark suite `tools/qa/bench`: Speedometer 3, JetStream 2, MotionMark, start-up with 1 and 4 profiles, idle and 20-tab memory, idle CPU - *Role:* QA engineer · *Depends:* P1.4 · *Done when:* it is repeatable within ±3% across runs
- [ ] **Q.2** Baselines: Thorium M156 and Chrome of the same major version - *Role:* QA engineer · *Depends:* Q.1 · *Done when:* baseline results are committed under `docs/perf/`
- [ ] **Q.3** Regression gate in the release script (a release is blocked until any regression is explained) - *Role:* Release engineer · *Depends:* Q.2, P2.12 · *Done when:* an injected regression blocks a dry-run release
- [ ] **Q.4** Memory-leak soak test (8 h of tab churn; memory-growth threshold) - *Role:* QA engineer · *Depends:* Q.1 · *Done when:* it runs before every release with a pass/fail threshold
- [ ] **Q.5** Crash triage process (local Crashpad dumps; symbol publication decision) - *Role:* QA engineer · *Depends:* P2.15 · *Done when:* the process document and symbol decision are recorded
- [ ] **Q.6** Test VMs: Windows 11 x64, Ubuntu 24.04 and 26.04 x64, clean snapshots - *Role:* QA engineer · *Depends:* P1 · *Done when:* the VMs restore to a clean state in one step
- [x] **Q.7** Profile compatibility gate: a new version is first started offline on a copy of real profiles, and `tools/qa/profile_check.py` must report 1:1 (windows, tabs, pinned tabs, tab groups with names and colours, saved passwords, bookmarks, enabled extensions, cookies within normal expiry, cookie encryption unchanged, no new app-bound key); it never decrypts or prints secrets - *Role:* QA engineer · *Depends:* P1.4 · *Done when:* the tool has tests and a real Thorium 150 profile passed it on the M156 build · ✅ 2026-11-08

### Docs (D)
- [ ] **D.1** Keep README, ROADMAP, CHANGELOG, CREDITS, NOTICE and docs current on every change (definition of done) - *Role:* Docs maintainer · *Depends:* - · *Done when:* ongoing; `check_docs` passes on every commit · 🔄
- [ ] **D.2** User guides: install, import, updates and rollback, portable passphrase (`docs/user/`) - *Role:* Docs maintainer · *Depends:* P3 · *Done when:* each guide is tested by following it on a clean VM
- [x] **D.3** ~~Repair broken links in upstream docs~~: the old upstream docs were removed from `main` with the rest of the unused M138 tree (D.8); the two kept copies in `docs/upstream/` link to the originals - *Role:* Docs maintainer · *Depends:* - · *Done when:* the link check passes · ✅ 2026-11-09
- [ ] **D.4** Release notes for every release (generated by `changelog.py`, highlights written by a person) - *Role:* Docs maintainer · *Depends:* P2.13 · *Done when:* every release carries full notes
- [x] **D.5** Rebrand the GitHub issue and PR templates for Thoron (bug, feature, ARM beta report, security redirect) - *Role:* Docs maintainer · *Depends:* P0.8 · *Done when:* the templates are live · bug, feature and ARM64 beta templates; security problems go to private reporting · ✅ 2026-11-09
- [ ] **D.6** Repository identity: renamed to `KuchiSofts/thoron` with Thoron description and topics; the owner asks GitHub Support to detach it from the Thorium fork network and to remove cached views and old pull-request references to purged history - *Role:* Owner / Docs maintainer · *Depends:* P0.11, S.13 · *Done when:* GitHub no longer shows "forked from", Support confirms the cache cleanup, and every link uses the new name · 🔄
- [x] **D.7** README shows the live roadmap: overall progress, per-phase bars, what's next and the full task list, generated from this file by `tools/docs/roadmap_progress.py`; `check_docs` fails if it is stale, and validates every heading anchor - *Role:* Docs maintainer · *Depends:* P0.6 · *Done when:* the README section is generated and enforced · ✅ 2026-11-07
- [x] **D.8** Repository cleanup: remove the unused upstream Thorium M138 tree from `main` (sources, logos, infra, old build scripts, submodules, old docs, about 1,500 files) so `main` holds only Thoron's own work; keep Thorium's M138 `PATCHES.md` and README as licence evidence; drop the upstream Sponsor button; Thoron issue templates - *Role:* Docs maintainer · *Depends:* - · *Done when:* tests and the docs check pass and nothing Thoron uses is gone · ✅ 2026-11-09

### Legal & licensing (L)
- [ ] **L.1** Licence inventory of every patch (origin, author, licence); resolve pending sources (Debian, chromium-ubuntu-build, Vanadium, Supermium); rewrite or drop anything incompatible - *Role:* Security researcher · *Depends:* P1.3 · *Done when:* an inventory table covers 100% of the patches; `NOTICE` has no "pending" entries · all 152 researched (method in `docs/legal/PATCH_ORIGINS.md`): 0 unknown, 2 more GPL-3.0 patches found (Cromite), no GPL-2.0-only code; re-run for the Chromium 158 series: 154 patches, 0 unknown, 6 not stated (Hibbiki code rewritten, the qcasey/icepie patch not carried over); open: 6 patches use code from authors who publish no licence (RobRich999, win32ss, Muril-o) and need permission or a rewrite · 🔄
- [ ] **L.2** GPL compliance per release: source tag and Chromium tag in `BUILDINFO`, GPL text in the licence bundle, notes in the release - *Role:* Release engineer · *Depends:* L.1, P2.12 · *Done when:* the release script refuses to build a release without them
- [ ] **L.3** Regenerate contributors and update `NOTICE` and `CREDITS` every release - *Role:* Docs maintainer · *Depends:* P0.4 · *Done when:* this is a step in the release script
- [ ] **L.4** Courtesy note to Alex313031 and gz83 introducing Thoron and its credits - *Role:* Owner · *Depends:* P0.11 · *Done when:* the owner has sent it (the owner decides wording and timing)
- [ ] **L.5** Name and logo check: "Thoron" in trademark registries and existing software in target markets; logo similarity to other browser marks (for example Chrome's three-segment logo) - *Role:* Owner · *Depends:* B.1 · *Done when:* the search results are recorded and no conflict was found (or the name or logo is adjusted)
- [x] **L.6** No prebuilt or proprietary binaries in the repository: removed the Widevine CDM (Google proprietary, no redistribution right), Flash Player (Adobe, end-of-life), `shc`-compiled launchers whose embedded script cannot be verified, and prebuilt tools and packages; `tools/audit/binary_policy.py` enforces it - *Role:* Security researcher · *Depends:* P0 · *Done when:* the policy passes on `main` with an empty allowlist · ✅ 2026-11-07
- [ ] **L.7** Remove those binaries from the repository's git history as well, and include them in the GitHub Support cache request (D.6) - *Role:* Owner · *Depends:* L.6 · *Done when:* no commit reachable on GitHub contains them

### Branding (B)
- [x] **B.1** Icon concepts (3 original concepts, previews at 16-256 px on light and dark backgrounds) and the owner's choice - *Role:* Docs maintainer / Owner · *Depends:* P0.1 · *Done when:* the owner has chosen · ✅ 2026-11-07
- [x] **B.2** Final asset set: colour and mono SVG, PNG 16-512, multi-size `.ico` - *Role:* Release engineer · *Depends:* B.1 · *Done when:* generated by the tested pipeline and committed · ✅ 2026-11-07
- [ ] **B.3** Chromium resource integration: product logos, `.ico`, installer images, Linux icons, About page and new-tab logo - *Role:* Chromium engineer · *Depends:* B.2, P2.3 · *Done when:* no Thorium logo appears in Thoron's product surfaces (credits excepted)
- [ ] **B.4** Release-page and social preview visuals - *Role:* Docs maintainer · *Depends:* B.2 · *Done when:* the GitHub social preview and release banner are in place

---

## Upstream issue map

Upstream Thorium issues that Thoron will address, and where.

| Upstream issue | Summary | Thoron task | Status |
|---|---|---|---|
| [#1313](https://github.com/Alex313031/thorium/issues/1313) | M156 high CPU and "Unknown Hard Error" on Windows | P5.3 | ⬜ |
| [#1230](https://github.com/Alex313031/thorium/issues/1230) | Breakpoint crash in `sqlite3_dbdata_init` | P5.4 | ⬜ |
| [#1278](https://github.com/Alex313031/thorium/issues/1278) | Suspended tabs crash (AVX-512 build) | P5.5 | ⬜ |
| [#1288](https://github.com/Alex313031/thorium/issues/1288) | Discord `STATUS_ACCESS_VIOLATION` | P5.6 | ⬜ |
| [#1271](https://github.com/Alex313031/thorium/issues/1271) | HEVC/AV1 playback regression | P5.7 | ⬜ |
| [#1285](https://github.com/Alex313031/thorium/issues/1285) | Video stutter on NVIDIA GPUs | P5.7 | ⬜ |
| [#137](https://github.com/Alex313031/thorium/issues/137), [#684](https://github.com/Alex313031/thorium/issues/684), [#1199](https://github.com/Alex313031/thorium/issues/1199) | Passwords not saved | P5.8 | ⬜ |
| [#1005](https://github.com/Alex313031/thorium/issues/1005), [#458](https://github.com/Alex313031/thorium/issues/458) | Logged out of sites / lost sessions | P5.9 | ⬜ |
| [#803](https://github.com/Alex313031/thorium/issues/803) | Slow start-up with multiple profiles | P5.10 | ⬜ |
| [#1164](https://github.com/Alex313031/thorium/issues/1164), [#1049](https://github.com/Alex313031/thorium/issues/1049) | APT repository not signed | P2.10 | ⬜ |
| [#1231](https://github.com/Alex313031/thorium/issues/1231) | Hardware acceleration not working on Ubuntu | P5.12 | ⬜ |
| [#126](https://github.com/Alex313031/thorium/issues/126) | Which servers does the browser contact? | S.10 | ⬜ |
| [#592](https://github.com/Alex313031/thorium/issues/592) | Portable is not fully portable | P3.12, P4.9 | ⬜ |
| [#1295](https://github.com/Alex313031/thorium/issues/1295) | Get uBlock Origin from its GitHub release | P5.1 | ⬜ |

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chromium removes Manifest V2 support, so bundled uBlock Origin stops working | High | Medium | P1.8 measures it early; uBO Lite stopgap for new profiles; P5.2 native-engine decision; security releases never wait for ad blocking |
| Rebasing patches onto each new Chromium takes longer than the G2 targets allow | Medium | High | P1.10 time budget; keep the Thoron patch set small; prioritise security-only rebuilds |
| Single build machine (hardware failure, availability) | Medium | High | Documented reproducible setup (P1.9); `BUILDINFO`; consider a second builder or self-hosted runner |
| Signing-key loss or compromise | Low | Critical | Offline root, tested backups (P2.11), rotation procedure (P4.7) |
| Portable encryption bug makes passwords unreadable | Low | Critical | Separate security review, fuzzing, round-trip tests, recovery key, read support for old formats (P4.9) |
| Import corrupts or loses data | Low | Critical | Copy-never-move, hash and SQLite verification, source unchanged by design (P3.14) |
| SmartScreen warnings scare new users | High | Medium | Checksum verification guide; code signing when possible (S.8) |
| ARM64 builds untested on real hardware | High | Medium | Beta label, emulation, community testers (P2b) |
| Upstream Thorium diverges or changes direction | Medium | Medium | Audit every merge (S.1); own patch series; regular rebase review |
| A patch's licence turns out incompatible | Medium | Medium | L.1 inventory before first release; rewrite or drop |
| Name conflict for "Thoron" | Low | Medium | L.5 name check before first release |

## Release policy

- **Security releases (G2):**
  - within **7 days** of a Chrome release that fixes an in-the-wild exploit;
  - within **14 days** of a new Chrome major version.
- **Draft first:** every release is created as a **draft**; only the owner publishes.
- **Every release contains:**
  - installer and portable packages per variant;
  - `SHA256SUMS` and its signature;
  - a signed update manifest;
  - `BUILDINFO.json`;
  - the licence bundle;
  - the **full changelog**: Chromium security fixes, our changes, upstream changes credited to their
    authors, patch changes, fixed and known issues, checksums, and credits.
- **Release gates:**
  - smoke tests pass;
  - the profile compatibility check passes on real profiles (Q.7);
  - no unexplained benchmark regression;
  - the audit of upstream changes has been reviewed;
  - the docs are current.

## Decision log

The owner decisions are recorded in design §16:
[`docs/design/2026-11-07-thoron-design.md`](docs/design/2026-11-07-thoron-design.md#16-owner-decisions-log-2026-11-07).
