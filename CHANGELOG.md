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
  for all 152 upstream M156 patches (29 confirmed, 123 still to research; ROADMAP **L.1**).
- `tools/build/pipeline.py`: build preflight (free space, cloud-synced or spaced paths, Backblaze-backed
  drives, WSL memory), an upstream setup wrapper that stops on any rejected patch, and a `buildinfo` entry point.
- `tools/build/smoke.py`: smoke-tests a build with a fresh throwaway profile; fails on crashes, a bad
  exit code, an empty result (the page script did not run), or any capability (JS, WebGL, H.264, HEVC,
  AV1, JPEG XL) not reported true. On Windows it also proves the sandbox is in force by reading the
  security token of every renderer of the running browser (it must be below Medium integrity) and
  rejecting any child process started with `--no-sandbox` (ROADMAP **P1.7**, in progress until it
  passes on our own Linux build too).
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

### Security
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
