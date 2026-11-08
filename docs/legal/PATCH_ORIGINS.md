# Patch origins: how the licence inventory was researched

This page explains how the origin of each upstream Thorium patch was established for the licence
inventory ([`PATCH_LICENSES.md`](PATCH_LICENSES.md), ROADMAP **L.1**). The findings themselves are kept
as data in [`tools/legal/patch_origins.tsv`](../../tools/legal/patch_origins.tsv) and turned into the
inventory by `tools/legal/patch_licenses.py`.

Researched: Thorium M156.0.8078.28 (gz83, de9a1bc6), 2026-11-08. Of its 152 patches, 29 already had a
clear origin in the upstream `docs/PATCHES.md`; the other 123 were researched as described below.

## Evidence used, strongest first

1. **Identical code.** For every patch, the distinctive lines it adds (24 characters or longer, not
   just braces, includes or `return`) were compared with every patch file in the projects below. A
   patch counts as derived from another project only when a large share of its lines match, or when
   the match is the whole of a small change. One or two shared lines are boilerplate and were ignored.
2. **Copyright lines in the patch.** Thorium patches change the header of the files they touch, for
   example `Copyright 2026 The Chromium Authors, Alex313031, qcasey and icepie`. Every name found in
   these lines is credited.
3. **Thorium's own records.** The older `docs/PATCHES.md` of Thorium M138 (kept in this repository as `docs/upstream/PATCHES_M138.md`)
   names the source of many features, even where the code was later rewritten.
4. **The project's licence.** Read from each project's `LICENSE` file, its README or
   `debian/copyright`, and GitHub's licence detection.

A patch with no outside match, inside the Thorium tree, is Thorium's own work under its BSD-3-Clause
`LICENSE.md`. This includes work by Thorium contributors, whose contributions to the repository are
under the same licence.

## Projects compared

| Project | Commit compared | Licence |
|---|---|---|
| ungoogled-chromium | `de09e0c70c` | BSD-3-Clause |
| ungoogled-chromium-windows | `f85bc55429` | BSD-3-Clause |
| ungoogled-software contrib | `fe0c03d9bf` | public domain (README, for files without a licence) |
| Cromite | `3724efc6ed` | GPL-3.0 |
| Bromite | `6f40f8341a` | GPL-3.0 |
| Helium | `cfedec96da` | GPL-3.0 |
| Vanadium | `99a6c8285b` | GPL-2.0-only |
| chromium-ubuntu-build (saiarcot895) | `07da3edbf3` | BSD-3-Clause (patches licensed as the patched sources) |
| enable-chromium-hevc-hardware-decoding (StaZhu) | `027325135a` | MIT |
| Chromium_Clang (RobRich999) | `c687f786a1` | not stated |
| chromium-win64 (Hibbiki) | `1e8c812330` | not stated |
| chromium-patches (qcasey) | `1c8a3774be` | not stated |
| Supermium (win32ss) | `bf7e71c95f` | not stated |

Iridium (BSD-3-Clause) and electron-chromium-codecs (licence not stated) were checked through the
commits that Thorium's docs name.

## Results

- **0 unknown.** Every patch now has an origin with evidence.
- **Two more GPL-3.0 patches, both from Cromite:** `GPC.patch` (126 of 140 lines identical to Cromite's
  Global Privacy Control patch) and `enable-android-devtools-frontend.patch` (Android only, not part
  of Thoron's builds). With the four already known, Thoron's builds contain GPL-3.0 code, so each
  release follows the GPL-3.0 rules (ROADMAP **L.2**). Every other licence found (BSD, MIT, public
  domain) can be combined with GPL-3.0.
- **No GPL-2.0-only code.** Vanadium is GPL-2.0-only, which cannot be combined with GPL-3.0. No current
  patch uses its code.
- **8 patches use code from authors who publish no licence ("not stated").** Without a licence the
  author keeps all rights, so these are release blockers until the author gives permission or the
  change is rewritten from scratch:

| Patch | Author | What is needed |
|---|---|---|
| `disable-vulkan-gpu-log-warnings.patch` | RobRich999 | permission, or rewrite (11 lines) |
| `enable-webrtc-h265-l1t2-l1t3-by-default.patch` | RobRich999 | permission, or rewrite (a two-line default) |
| `llvm-optimized-toolchain-build.patch` | RobRich999 | permission, or rewrite the build flags |
| `thorium-build-config-and-simd.patch` | RobRich999 (30 of 210 lines) | permission, or rewrite those lines |
| `enable-mpeg2-ac3-eac3-decoding.patch` | RobRich999, Muril-o | permission from both, or rewrite |
| `fix-policy-templates.patch` | Hibbiki (6 of 22 lines) | rewritten for Chromium 158 (see below) |
| `add-flag-for-auto-dark-mode.patch` | qcasey, icepie | not carried over to Chromium 158 (see below) |
| `disable-encryption.patch` | win32ss (Supermium) | permission for the profile reversion part, or rewrite it |

RobRich999 has worked with Thorium for years and is credited in its README, so asking for a written
licence statement is the natural first step. Asking any author is the owner's decision.

## Chromium 158 series

Re-run on 2026-11-08 for the series rebased to Chromium 158.0.8127.30 (ROADMAP **P2.1**,
`docs/build/M158_REBASE.md`): **150 patches, 0 unknown, 6 not stated** (was 8).

- `fix-policy-templates.patch` was rewritten for 158 and no longer uses Hibbiki's code: the 8 lines
  it still shares with Hibbiki's patch are all lines of Chromium's own `writer_configuration.py`.
- `add-flag-for-auto-dark-mode.patch` (qcasey, icepie) is not carried over (Linux, ROADMAP **P2.22**).
- `GPC.patch` (Cromite, GPL-3.0) is replaced by Thoron's `ks-native-gpc.patch`, which only turns on
  Chromium 158's own Global Privacy Control. The other Cromite patches stay, so releases still follow
  the GPL-3.0 rules (ROADMAP **L.2**).
- The Android-only patches and `enable-ctrl-tab-mru.patch` are gone; their research rows were removed.
- Two patches new in upstream since the M156 tag, `developer-crx-installation.patch` and
  `thorium-first-run-branding.patch`, were written in the Thorium repo by gz83 (BSD-3-Clause). Compared
  with the 13 projects above, they share only common Chromium code (includes, file dialog and feature
  checks).
- The three new Thoron patches carry `Origin:` and `License:` headers (BSD-3-Clause).

The six patches that still need permission or a rewrite are the five RobRich999 ones (one also
Muril-o) and the profile reversion part of `disable-encryption.patch` (win32ss) in the table above.

## Keeping it current

Run the inventory after every upstream rebase (the Chromium 158 rebase, ROADMAP **P2.1**):

```powershell
py -3 -I tools/legal/patch_licenses.py --tree <upstream tree> --credits CREDITS.md `
    --research tools/legal/patch_origins.tsv --source "<upstream tag>" --out docs/legal/PATCH_LICENSES.md
```

It fails while any patch is unknown or not stated, and when a research row names a patch that is no
longer in the series. A new or renamed patch shows up as unknown until it is researched the same way.
