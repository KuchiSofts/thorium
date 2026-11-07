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

### Security
- Every upstream change is now audited before merging (`tools/audit`, ROADMAP **S.1**).
- `.gitignore` excludes Python bytecode caches produced by the tools.
