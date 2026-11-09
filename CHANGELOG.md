# Changelog

All notable changes to Thoron are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each release lists:
- the Chromium version and its security fixes;
- Thoron changes;
- upstream Thorium changes, credited to their authors;
- fixed and known issues;
- artifact checksums.

## [Unreleased]

### Added
- Native ad blocking shows what it did on a page (ROADMAP **P5.16**, off by default): an address bar icon
  appears when something was blocked, and its bubble says how many ads and trackers were blocked on the page,
  with a checkbox to always allow them on that site. The count is kept only in memory with the page; nothing
  is stored or sent. Checked offline with `tools/qa/adblock_site_switch_check.py` (10 blocked, count 10).
- While native ad blocking is on, page info and Settings call the Ads setting "Ads and trackers" and say what
  it does (ROADMAP **P5.16**); with it off, Chromium's wording stays.
- Native ad blocking can be turned off per site (ROADMAP **P5.16**, off by default): it follows the browser's
  per-site "Ads" setting in page info and Settings, so allowing ads on a site, or everywhere, turns it off
  there. The choice is kept with the profile's other site settings. Checked offline with
  `tools/qa/adblock_site_switch_check.py`.
- Native ad blocking keeps its filter lists current (ROADMAP **P5.15**, off by default): at most every 4 days,
  from the addresses uBlock Origin uses, over HTTPS without cookies. A list that is too large, not a list,
  shrinks by more than half or allows every request keeps its previous copy, and an update that would stop
  blocking known ads is refused whole. Checked offline with `tools/qa/adblock_update_check.py`.
- Native ad blocking ships a pre-compiled engine (ROADMAP **P5.15**, step 1): each build compiles the bundled
  filter lists into a saved engine and checks that it loads again; the browser loads it at start instead of
  parsing the lists, and falls back to the lists if it is missing or broken. Both files are in the installer.
- Native ad blocking connected to page loading (ROADMAP **P5.14**, off by default): Thoron's built-in
  engine sits first in front of every page's requests and ends blocked ones before they leave the browser.
  On the local ad test page it blocked all 10 ad requests on its own (uBlock Origin: 9 of 10).
- Native ad blocking, first step (ROADMAP **P5.14**): `adblock-rust` 0.13.3 and its crates are vendored with
  Chromium's own tooling (`tools/build/rust_crates.py`), and the engine component builds in the 158 tree with
  its tests passing. Not yet connected to page loading.
- Native ad blocking spike (ROADMAP **P5.13**): `adblock-rust` with the lists Thoron ships loads in 5 ms,
  uses 9.7 MB and checks a request in about 5 µs (uBlock Origin's extension process: 110.8 MB). Verdict: go.
- Design for native ad blocking (`docs/design/2026-11-09-native-adblock-design.md`, approved): a built-in
  filter engine (`adblock-rust`, MPL-2.0) blocks ads and trackers before requests leave the browser, faster than
  an extension and independent of Manifest V2; uBlock Origin stays for cosmetic filtering. Steps P5.13-P5.18.
- `tools/qa/netlog_hosts.py` and `docs/security/NETWORK.md` (ROADMAP **S.10**): the outside hosts a fresh
  profile contacts on its own, with why and what Thoron does about each; first measurement on Thoron 156.
- `tools/qa/bench.py` (ROADMAP **Q.1**): offline benchmarks (start-up time, private memory with 1 and 20
  tabs, idle CPU) on throwaway profiles and local pages only, with median and spread per measure.
- Thoron wordmark (logo and name) and the Thoron logo replace Thorium's wordmark and mascot on
  `chrome://version` (ROADMAP **B.3**); `tools/branding/wordmark.py` builds the wordmark from the logo SVG.
- About page (ROADMAP **P2.5**): below the version it says which Chromium version the build is based on,
  shows the disclaimer ("Thoron is an independent browser by KuchiSofts, based on Thorium by Alex313031 and
  Chromium by The Chromium Authors...") and links to the release notes.
- Patch series rebased to Chromium 158.0.8127.30 (ROADMAP **P2.1**), starting from upstream's newer 156.0.8078.80 patches after an audit of the upstream changes. All 146 patches apply exactly; 25 were ported by hand to 158's code. Global Privacy Control now uses Chromium's own implementation instead of the Cromite patch, Android-only patches are not carried over, and two small Thoron patches fix the 158 build (FFmpeg duplicate sources, a Rust compiler flag). Every decision is recorded in `docs/build/M158_REBASE.md`.
- Linux identity in code (ROADMAP **P2.4**, **P2.21**): the program `thoron`, the package `thoron-browser`
  installed in `/opt/kuchisofts/thoron`, its own desktop file and app ID, and the profile folder
  `~/.config/thoron`, so Thoron installs next to upstream `thorium-browser` and never reads or changes its
  profile. The keyring entry stays `Chromium Safe Storage`, as in Thorium, so passwords in a copied profile
  stay readable. Upstream's developer test shell and prebuilt `pak` tool are not packaged. Not yet built on
  Linux.
- Every patch in the 158 series now names its origin, author and licence at the top (ROADMAP **S.7**),
  written from the audited licence research; `tools/legal/patch_headers.py lint` rejects a patch without
  them, or one whose licence differs from the research.
- `tools/release/release.py` (ROADMAP **P2.12**): one command checks a build (release args, version,
  installer contents) before packaging, names the files `thoron-<version>-<variant>-...`, writes `SHA256SUMS`,
  BUILDINFO and the release notes, signs with minisign when a key is given, and publishes only as a draft,
  never without a signature.
- `tools/release/changelog.py` (ROADMAP **P2.13**): release notes from git and local files, in the
  design's order: Chromium change and its security fixes, Thoron changes grouped by commit prefix, upstream
  Thorium commits credited by author, patch changes, fixed issues, downloads with SHA-256, credits.
- `tools/release/package_audit.py` (ROADMAP **P2.6**): a package must contain the Thoron program and
  no Widevine module, no file named after Thorium (licence and credit texts excepted) and none of the
  upstream-only extras (Thorium updater marker, prebuilt pak tool, test shell).
- Version scheme for Thoron builds (ROADMAP **P2.14**): Chromium's version with the last part widened to
  `patch x 100 + rebuild`, for example `158.0.8127.3000` and its rebuild `158.0.8127.3001`, so rebuilds of
  the same Chromium upgrade cleanly and a newer Chromium always wins. `tools/release/version.py` sets
  and checks it.
- Release build configuration reviewed for privacy (ROADMAP **P2.17**): `tools/build/release_args.py`
  builds the release `args.gn` from upstream's and turns off Google's RLZ promotion-tracking library and the
  DRM storage ID that upstream enabled, never bundles Widevine and refuses Google API keys. Every choice
  and its reason is in `docs/build/RELEASE_ARGS.md`.
- Licence inventory regenerated for the Chromium 158 series (ROADMAP **L.1**): 157 patches, 0 unknown,
  6 that still need the author's permission or a rewrite (was 8). The policy templates patch was rewritten
  without the unlicensed code, and the two new upstream patches were researched (both Thorium,
  BSD-3-Clause). Details in `docs/legal/PATCH_ORIGINS.md`.
- First reproduced Linux build: Chromium 156.0.8078.28 with the upstream M156 AVX2 configuration
  (no bundled Widevine) in a dedicated Ubuntu 24.04 WSL2 distro, built in about 2 hours 37 minutes.
  It passes the smoke test with the sandbox proven (renderers under seccomp-BPF in their own PID
  namespace) and launches under WSLg (ROADMAP **P1.2**, **P1.5**, **P1.7**). Guide: `docs/build/LINUX.md`;
  measured times for both OSes in `docs/build/BUILD_BUDGET.md` (ROADMAP **P1.10**).
- Thoron's own identity on Windows (ROADMAP **P2.3**, done first on M156): `tools/build/thoron_identity.py`
  applies the name Thoron (UI strings and translations, without touching URLs, paths or
  identifiers), its own install and profile folder `%LOCALAPPDATA%\Thoron`, registry key, app ID,
  ProgIDs, `thoron` link scheme, Active Setup GUID, COM class IDs and sandbox SID prefix, the
  Radiant Core icons, and `BRANDING`. The About page and copyright credit The Chromium Authors,
  Alex313031 and KuchiSofts, and lines that name Alex313031 are never renamed. Translations follow
  the rename: the tool recomputes each renamed message's ID with GRIT and updates the translation
  files, so no language loses a translation. It is anchored and idempotent, so it re-applies after
  every rebase. Thoron installs and runs next to Thorium with its own folder, registry key and
  ProgIDs (Thorium's files, registry key and ProgIDs verified unchanged). Until the program file
  is renamed (ROADMAP **P2.20**), one Windows entry keyed by `thorium.exe` is shared: installing
  Thoron points `App Paths\thorium.exe` at Thoron, and uninstalling Thoron would remove Thorium's
  `App Paths` and Open-with entries.
- `tools/migrate/import_profile.py`: brings a Thorium profile into Thoron by a verified copy (never a
  move; every file checked by SHA-256; refuses if either browser runs or Thoron already has a
  profile). A real Thorium profile came out 1:1 in Thoron (ROADMAP **P3.14**, command-line version).
- Windows Start-menu tile icons (70 and 150 px) and `export_icons.py --sizes`.
- Windows 11 build guide `docs/build/WINDOWS.md` (toolchain, Defender, depot_tools, Chromium source)
  and `tools/build/win_env.ps1`, which prepares one PowerShell window for building: build folder,
  temporary files off the system drive, pinned depot_tools, Visual Studio 2026, and a build-only git
  config that keeps the user's own config and hooks. `gn gen` succeeds on stock Chromium 156 with
  this toolchain (ROADMAP **P1.1**). The upstream M156 overlay and patch series apply to Chromium
  156.0.8078.28 with 0 rejects (ROADMAP **P1.3**); `pipeline.py apply --log` keeps the full log.
- First reproduced Windows build: Chromium 156.0.8078.28 with the upstream M156 AVX2 configuration,
  without bundled Widevine. It builds in 2 hours 35 minutes, writes a `BUILDINFO.json` free of
  personal paths, and passes the smoke test (JS, WebGL, H.264, HEVC, AV1, JPEG XL, no crashes)
  (ROADMAP **P1.4**). Measured times and a draft release-build plan are in
  `docs/build/BUILD_BUDGET.md` (ROADMAP **P1.10**, in progress).
- `tools/build/rebase_report.py`: applies a patch series to a temporary git index of a newer Chromium,
  never touching the checkout, and reports each patch as applied, fuzz, already applied, rejected or
  missing. First report: `docs/build/M158_REBASE_REPORT.md` (upstream M156 series on Chromium
  158.0.8127.30: 95 apply, 21 need a refresh, 33 need a rebase) (ROADMAP **P1.8**, **P2.1**).
- `tools/build/mv2_check.py`: offline ad-blocking check that runs the browser with and without an
  extension (fresh profiles, sandbox on) and measures network blocking and cosmetic filtering. It
  found that Thorium's default apps install uBlock Origin from the Web Store into every new profile;
  Thoron will not (ROADMAP **P2.16**).
- `tools/qa/profile_check.py`: checks that a new version keeps a profile 1:1 on what it measures:
  windows, tabs, pinned tabs and tab groups (from the session file), the number of saved passwords,
  bookmarks, enabled extensions, cookies and their encryption scheme. It never decrypts or prints a
  secret, refuses a running browser or a wrong folder, records anything unreadable as unreadable
  (never as zero), and reports a new version that wrote no session. History, autofill and site data
  are not checked yet. A real Thorium 150 profile, opened offline by the M156 build, came out 1:1.
  It is now a release gate (ROADMAP **Q.7**).
- Manifest V2 verdict for Chromium 158 (ROADMAP **P1.8**, design §10.1): Manifest V2 itself still
  works with upstream's patch (a minimal blocking extension blocks every request), but uBlock Origin
  1.75.4 hangs at start-up because `chrome.storage.managed.get` never answers on the 158 test build.
  Follow-up: ROADMAP **P2.18**. The 158 test build took 3.3 hours with 10 jobs.
- Patch licence inventory: `tools/legal/patch_licenses.py` and the generated `docs/legal/PATCH_LICENSES.md`
  for all 152 upstream M156 patches (ROADMAP **L.1**). All 152 are now researched: every patch's
  added code was compared with 13 credited projects, its copyright lines and Thorium's older patch
  notes (method: `docs/legal/PATCH_ORIGINS.md`, findings: `tools/legal/patch_origins.tsv`). Result:
  0 unknown; `GPC.patch` and `enable-android-devtools-frontend.patch` come from Cromite (GPL-3.0);
  no GPL-2.0-only code; 8 patches use code from authors who publish no licence and need their
  permission or a rewrite before a release. `CREDITS.md` and `NOTICE` list the confirmed licences
  and the newly found contributors (icepie, not-lucky, qcasey, tomByrer, win32ss).
- `tools/build/pipeline.py`: build preflight (free space, cloud-synced or spaced paths, Backblaze-backed
  drives, WSL memory), an upstream setup wrapper that stops on any rejected patch, and a `buildinfo` entry point.
- `tools/build/smoke.py`: smoke-tests a build with a fresh throwaway profile; fails on crashes, a bad
  exit code, an empty result (the page script did not run), or any capability (JS, WebGL, H.264, HEVC,
  AV1, JPEG XL) not reported true. On Windows it also proves the sandbox is in force by reading the
  security token of every renderer of the running browser (it must be below Medium integrity) and
  rejecting any child process started with `--no-sandbox`. On Linux it reads `/proc`: every renderer
  must run under a seccomp-BPF filter and in its own PID namespace (ROADMAP **P1.7**).
- `tools/build/wslconfig.py`: raises WSL memory and swap only for a Linux build (swap file on the build
  drive) and restores the original `.wslconfig` byte for byte. It never overwrites a backup, refuses a
  second raise before a restore, and restores only from its own backup of that file. It never restarts
  WSL itself; the owner approves every `wsl --shutdown`.
- `tools/build/buildinfo.py`: writes `BUILDINFO.json` for every build (Chromium version, Thoron and
  upstream commits, depot_tools revision, GN args and their digest, toolchain, timing). Every string,
  at any depth and GN args included, has build-root paths made relative and user-folder paths
  redacted, and the file is not written if a user-folder path survives anywhere (ROADMAP **P1.6**).
- Approved Thoron design for Windows 11 and Ubuntu, x64 and ARM64 (`docs/design/`).
- Audit toolkit for upstream merges and release verification (`tools/audit`): `audit_diff`,
  `crx_id`, `compare_release`.
- Docs and privacy linter enforcing the definition of done (`tools/docs/check_docs.py`).
- Contributor credits generator (`tools/credits/contributors.py`).
- `CREDITS.md` and `NOTICE` with full upstream credits and per-component licences.
- Thoron `README.md`, a detailed `ROADMAP.md`, `SECURITY.md` (private reporting, coordinated disclosure)
  and `CONTRIBUTING.md`.
- Thoron logo "Radiant Core", chosen by the owner from three original concepts, with a single-colour
  variant (`branding/thoron/`, CC BY 4.0).
- Icon asset pipeline (`tools/branding`): PNG sizes 16-512 and a multi-size Windows `.ico` generated
  from the SVG logo using only the standard library and a headless browser.

### Changed
- Windows program file renamed to `thoron.exe` and the installer to `thoron_<variant>_mini_installer.exe` (ROADMAP **P2.20**). The installer no longer ships Thorium-named files (`thor_ver`, Thorium icons, content shell entries), and Thoron no longer shares Thorium's `App Paths\thorium.exe` entry, so either browser can be uninstalled without affecting the other. `tools/migrate/exe_rename.py` moves an install made before the rename over: it gives `App Paths\thorium.exe` back to Thorium, fixes shortcuts and registry values the installer did not, and moves the leftovers into a backup it can restore.
- Work order: Windows first. The Linux build tasks (ROADMAP **P1.2**, **P1.5**) are deferred by the
  owner's decision; Ubuntu remains a target platform (design §16).
- New README with the Thoron logo, badges and quick navigation. Its roadmap section (overall
  progress, per-phase progress bars, what's next and the full task list) is generated from
  `ROADMAP.md` by `tools/docs/roadmap_progress.py`, and `check_docs` fails if it is out of date.
- `check_docs` now validates heading anchors in links, which fixed 10 links broken by the dash cleanup.
- House style: long dashes replaced by a plain "-" across all our docs, code and assets. `check_docs` now enforces this rule.
- Repository renamed from `KuchiSofts/thorium` to `KuchiSofts/thoron` (old links redirect), with a Thoron description and topics. Detaching from the Thorium fork network has been requested (ROADMAP **D.6**). The design document is now `docs/design/2026-11-07-thoron-design.md`.
- The original Thorium README moved to `docs/upstream/THORIUM_README.md`, unchanged except for relative
  links (including a fix for a pre-existing broken link).

- More credits:
  - patch sources RobRich999 (Chromium_Clang), StaZhu, Hibbiki, qcasey, Muril-o and FydeOS;
  - hezhizheng's thorium-win-upgrade;
  - Alex313031 as co-author of the pak tool.

  `NOTICE` gained a catch-all line covering every other patch source pending the licence inventory.
- `NOTICE` patent wording corrected; it now states that no patent licence is granted.
- README and `SECURITY.md` now separate what is in place today from what is planned. Windows
  download verification now includes the signature step.
- The design document's background section was rewritten as neutral, linked, verifiable
  observations about upstream.

### Removed
- Thorium's hidden `chrome://eggs` and `chrome://robot` pages (ROADMAP **S.11**): they only showed pictures,
  yet were allowed to make network requests. `chrome://authors`, which credits the Thorium authors, stays.
- The old copy of the upstream Thorium M138 tree that the repository still carried (about 1,500 files:
  sources, logos, build scripts, submodules and old docs). Thoron's builds never used it; they use the
  pinned, audited upstream source. Thorium's M138 `PATCHES.md` and README stay in `docs/upstream/` as
  licence evidence, and the upstream Sponsor button is gone; Alex313031 stays credited (ROADMAP **D.8**).

### Fixed
- `tools/build/rebase_report.py` now puts upstream's overlay files into its scratch index, as the real setup
  does before the series runs, so a patch that changes an overlay file is no longer reported as rejected;
  and it writes its temporary git objects to a scratch folder instead of the Chromium checkout.

### Security
- Flags that weaken security (`disable-web-security`, `allow-file-access-from-files`, `disable-encryption`,
  `allow-insecure-downloads`, the password store choice) now start with a plain warning in `chrome://flags`,
  and Chromium's unsupported-flag bar is back for `--extensions-on-chrome-urls`, `--enable-blink-features`,
  `--disable-blink-features` and `--enable-unsafe-webgpu` (ROADMAP **S.4**). Every flag still works and all
  stay off by default.
- `chrome://authors` (the Thorium credits page) now uses Chromium's default WebUI security policy
  instead of allowing inline scripts, and may no longer make network requests (ROADMAP **S.3**). The page
  and its credits are unchanged.
- Thoron reads extra command-line flags only from its own file on Windows (`%APPDATA%\Thoron\thoron-flags.conf`
  or `thoron-flags.conf` next to `thoron.exe`). The upstream patch read Thorium's file, so switches meant for
  Thorium, unsafe ones included, would have applied to Thoron. On Linux the file is
  `~/.config/thoron/thoron-flags.conf`.
- `.gitignore` now excludes every browser-profile file type (passwords, cookies, sessions, history,
  keys) whose names cannot be mistaken for source folders, on top of the privacy checks that block
  such data at commit and push time.
- Removed `infra/hangout_services/bin/hangout_services_1.4.1.pem`, an upstream private signing key for
  the (already removed) hangout_services package. It was referenced nowhere; a published private key
  lets anyone sign packages under that extension's identity.
- Proprietary and unverifiable binaries removed from the repository (ROADMAP **L.6**):
  - Google's Widevine CDM for Windows, macOS, Linux and ChromeOS (13 files plus signatures and
    import libraries, one of them a patched copy). Its licence forbids redistribution; Chromium's
    component updater still downloads it from Google when a site needs it;
  - Adobe Flash Player (`infra/libpepflashplayer.so`), proprietary and end-of-life since 2020;
  - the Linux portable launchers `THORIUM-PORTABLE` and `THORIUM-SHELL`, compiled with `shc`, which
    embeds the script encrypted so it cannot be checked against its source (the `.sh` scripts stay),
    and the unexplained `infra/APPIMAGE/files/outc`;
  - prebuilt tools and packages: `cgpt`, the `pak` tool binaries (its source stays in `pak_src/`),
    a `vdpau-va-driver` package and an unused `hangout_services` CRX.
- `tools/audit/binary_policy.py` now fails on any prebuilt executable, library, package or archive
  without an allowlisted SHA-256, licence and source, and always on proprietary blobs.
- Inherited git history cleaned: three inappropriate image files that upstream added in 2023 and
  later deleted were purged from every commit (current files unchanged; verified absent from the
  M150 browser build). Commit IDs changed as a result.
- Content standards added to `CONTRIBUTING.md`; `tools/audit` gains an `adult_content` check on added
  text and file names (ROADMAP **S.12**).
- Every upstream change is now audited before merging (`tools/audit`, ROADMAP **S.1**).
- `audit_diff` hardened against crafted diffs. It now:
  - reads files by blob and parses hunks by their declared line counts;
  - splits text on `\n` only;
  - ignores the user's git diff settings;
  - reports submodule and `.gitmodules` changes, type changes, executables disguised as images,
    SVG content, and upload hosts (by owner or bucket);
  - recognises more Windows and Linux download-and-run and persistence forms.

  The changes come with 14 regression tests.
- `crx_id` verifies CRX3 RSA signatures (standard library only) and supports `--expect <id>`.
- `compare_release` no longer reports an install with injected executables as identical; it also
  gains `--strict`.
- `check_docs`:
  - detects lowercase, Git-Bash, WSL and macOS user paths;
  - reads private lists that have a byte-order mark or are UTF-16;
  - scans our `.py`, `.svg` and `.html` files too;
  - checks reference-style, nested-badge and HTML links with exact case, inside the repository, and
    not git-ignored;
  - defaults to the repository root.
- The contributors generator writes atomically and never truncates `CREDITS.md`.
- `.gitignore` excludes Python bytecode caches produced by the tools.
