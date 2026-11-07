# Contributing to Thoron

Thank you for helping build Thoron. This guide keeps the project secure, honest and well credited.
Please also read our [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

- Look at the [roadmap](ROADMAP.md) and reference the task ID (for example **P3.14**) in your pull
  request.
- Security problems go through the private process in [`SECURITY.md`](SECURITY.md), never through
  public issues.

## Commit messages

Use one of these prefixes; the release-notes generator groups changes by them:

| Prefix | For |
|---|---|
| `sec:` | security fixes and hardening |
| `perf:` | performance and resource use |
| `fix:` | bug fixes |
| `ui:` | user interface and branding |
| `build:` | build, packaging, release tooling |
| `docs:` | documentation only |

Example: `fix: keep tab group colours when importing from Edge (P3.15)`

## Definition of done

A change is complete only when **all** of these are true:

1. **Tests:** new behaviour has tests that failed before the change and pass after it. Run them with
   `py -3 -I -m unittest discover -s tools -t . -p "test_*.py" -v`, plus any browser tests for the area.
2. **Security review:** you have checked for new network endpoints, binaries, flags, permissions and
   data paths, and explained them in the PR.
3. **Docs updated in the same change:**
   - `README.md` if anything user-facing changed;
   - `ROADMAP.md`: tick the task, set `· ✅ YYYY-MM-DD`, update `Last updated`, and add any new work
     you discovered. Then run `py -3 -I tools/docs/roadmap_progress.py` to refresh the README's
     roadmap section (the linter fails if you forget);
   - `CHANGELOG.md`: an entry under `## [Unreleased]`;
   - `CREDITS.md` / `NOTICE` if code came from someone else;
   - any affected file under `docs/`.
4. **Linter passes:** `py -3 -I tools/docs/check_docs.py --private`.

## Copyright and attribution

- **Never remove or alter** an existing copyright header or licence file.
- New code files start with:
  `Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.`
  Use the comment syntax of the language.
- **Patches taken from other projects** keep their original headers and add these lines to the patch
  description:

  ```text
  Origin: <project name and URL of the original patch>
  Author: <original author>
  License: <SPDX identifier of the original licence>
  ```

- Only take code whose licence is known and compatible. If you are unsure, ask in the PR first.
- **Credit people:** add new upstream sources to `CREDITS.md` and their licence to `NOTICE`.

## Content standards

Thoron is a professional product. Nothing in the code, assets, commit messages, pull requests or
hidden "Easter egg" pages may contain sexual, NSFW, hateful or otherwise offensive material, or link
to it.

- **Images:** every new or changed image must be reviewed by a maintainer before merging. That covers
  icons, illustrations, screenshots and anything embedded as data inside patches.
- **Automatic check:** `tools/audit/audit_diff.py --strict` fails on adult terms and sites, both in
  added text and in **file names**. It is a safety net, not a replacement for review.
- **Hidden pages and Easter eggs:** Thoron does not ship them (see ROADMAP **S.11**).

## Merging upstream (Thorium or Chromium)

Every upstream merge is audited first:

```shell
# Audit only what upstream added since our last common commit (not our own divergence):
py -3 -I tools/audit/audit_diff.py . "$(git merge-base HEAD <upstream-ref>)" <upstream-ref> --section all --strict
```

A `--strict` failure is not automatically malicious, but **every finding must be reviewed by a person**,
with the outcome noted in the PR.

## Privacy rules

- Never commit browser profile files, keys, tokens, crash dumps, or personal paths and emails.
- Commit with your **GitHub noreply** e-mail address.
- Test builds always use a separate profile: `--user-data-dir=<temporary folder>`.

## Pull requests

- Keep each PR focused on one roadmap task where possible.
- Describe what changed, why, how you tested it, and the security impact.
- PRs that don't meet the definition of done will be asked to update before review.
