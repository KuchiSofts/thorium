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
- Icon asset pipeline (`tools/branding`): PNG sizes 16–512 and a multi-size Windows `.ico` generated
  from the SVG logo using only the standard library and a headless browser.

### Changed
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
