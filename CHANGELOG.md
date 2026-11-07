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
- Patch licence inventory: `tools/legal/patch_licenses.py` and the generated `docs/legal/PATCH_LICENSES.md`
  for all 152 upstream M156 patches (29 confirmed, 123 still to research; ROADMAP **L.1**).
- `tools/build/pipeline.py`: build preflight (free space, cloud-synced or spaced paths, Backblaze-backed
  drives, WSL memory), an upstream setup wrapper that stops on any rejected patch, and a `buildinfo` entry point.
- `tools/build/smoke.py`: smoke-tests a build with a fresh throwaway profile and the sandbox always on;
  fails on crashes, a bad exit code, or any missing capability (JS, WebGL, H.264, HEVC, AV1, JPEG XL)
  (ROADMAP **P1.7**, in progress until it passes on our own builds).
- `tools/build/wslconfig.py`: raises WSL memory and swap only for a Linux build (swap file on the build
  drive) and restores the original `.wslconfig` byte for byte. It never restarts WSL itself; the owner
  approves every `wsl --shutdown`.
- `tools/build/buildinfo.py`: writes `BUILDINFO.json` for every build (Chromium version, Thoron and
  upstream commits, depot_tools revision, GN args and their digest, toolchain, timing) with every path
  relative to the build root and user directories redacted (ROADMAP **P1.6**).
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
