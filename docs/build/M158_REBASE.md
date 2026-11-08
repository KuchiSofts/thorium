# Rebase to Chromium 158 (ROADMAP P2.1)

This records how the Thorium patch series was moved from Chromium 156 to **Chromium 158.0.8127.30**,
and every decision taken on the way. The starting point was the report in
[`M158_REBASE_REPORT.md`](M158_REBASE_REPORT.md) (95 applied, 21 fuzz, 33 rejected).

## Base

- **Upstream:** gz83 `main` at `efc0fff` ("M156 Stable: Refresh patches", 156.0.8078.80), newer than
  the M156.0.8078.28 tag that P1 reproduced. It carries upstream's own refreshed patches and build fixes.
- **Audit:** the 18 upstream commits since the tag were checked with `tools/audit/audit_diff.py --strict`:
  no binaries, no submodule changes. The network endpoints and `--no-sandbox` hits are in macOS smoke-test
  scripts that Thoron does not use. The new `developer-crx-installation.patch` adds a developer-mode
  "install a local CRX" button and leaves signature checks unchanged.
- **Branch:** `ks/M158`, local only. Like the M156 audit ref, it holds the full upstream tree, which still
  carries files that must not be published (ROADMAP **L.6**, **L.7**), and the local push hook refuses it.

## Method

Every patch was applied in series order to Chromium 158 and committed on a local branch, cleanly or
with a 3-way merge against the Chromium 156.0.8078.80 sources. Conflicts were resolved by hand,
keeping Chromium 158's code and re-applying Thorium's change on top of it. The refreshed patches were
then exported, and the new series was checked on an untouched 158 checkout with both
`tools/build/rebase_report.py` and upstream's `apply_series.py`.

Result: the series lists **149 patches**. The **146** that the Windows AVX2 build uses all apply exactly
(the other 3 are for SSE2 and Raspberry Pi builds only). 25 were ported by hand, and 2 are new Thoron
patches (`ks-native-gpc`, `ks-ffmpeg-158-no-duplicate-bswapdsp`).

## Decisions

| Patch | Decision | Why |
|---|---|---|
| `android-thorium-branding`, `android-extensions-support`, `android-extensions-opt-in-ui`, `enable-android-devtools-frontend`, `enable-extension-in-incognito` | not carried over | Android only (the last one's desktop edits only guard the Android extension code). Thoron builds Windows and Linux. Three of them are Cromite code (GPL-3.0). |
| `GPC.patch` (Cromite, GPL-3.0) | replaced by `ks-native-gpc.patch` | Chromium 158 implements Global Privacy Control itself (the `Sec-GPC` header and `navigator.globalPrivacyControl`) with a settings toggle. Thoron turns it on by default, as Thorium did, and always shows the toggle (Chromium shows it only in some locations, so it could not be switched back on). |
| `add-flag-for-auto-dark-mode` | not carried over | Linux GTK only; Chromium 158 rewrote the theme code it changes, and its code comes from an author who publishes no licence (L.1). Whether Linux still needs it is ROADMAP **P2.22**. |
| `enable-ctrl-tab-mru` | dropped | Chromium 158 enables most-recently-used Ctrl+Tab by default. |
| `fix-policy-templates` | rewritten | Chromium 158 already checks the Chromium branding first, so only the names are changed. This removes the code taken from chromium-win64, whose author publishes no licence (L.1). |
| `tab-strip-combo-button-position` | ported | Chromium 158 always places the tab search button by hand. For Thorium's default right-hand position, the space after the window drag area is reserved and the button is placed there. |
| `thorium-2024-ui-core`, `disable-thorium-icons`, `classic-omnibox`, `rectangular-tabs`, `custom-tab-width` | ported | Re-applied on top of 158's refactored code (new layout constants, icon helpers, tree view without model icons). |
| `enable-sharing-hub-page-action` | ported | 158 moved the sharing policy code into `browser_command_controller.cc`. |
| `open_in_same_tab` | ported | 158 took the context menu UMA values 36, 172 and 173; the new item uses 37 and 174. |
| `thorium-browser-resource-branding` | path updated | 158 renamed `resources/omnibox` to `resources/omnibox_internals`. |
| `disable-thorium-icons` | ChromeOS files dropped | Two ChromeOS Quick Answers views no longer exist in 158. |
| (new) `ks-ffmpeg-158-no-duplicate-bswapdsp.patch` | added | Chromium 158's FFmpeg already builds bswapdsp for the targets the HEVC patch adds it to; GN stopped with a duplicate object file. |
| `thorium-build-config-and-simd` | Rust flag removed | The LLVM in 158's Rust toolchain no longer has `-fp-contract`, so rustc stopped. C and C++ keep Thorium's FMA contraction setting; Rust keeps its default (no contraction). |

The licence inventory was regenerated for this series (`docs/legal/PATCH_LICENSES.md`): 0 unknown and
6 not stated, down from 8 (details in `docs/legal/PATCH_ORIGINS.md`).

The build also needs the PGO profiles (`checkout_pgo_profiles` in `.gclient`, then `gclient runhooks`),
which a checkout made only for testing does not have.

## Still to do

- Build, smoke test, sandbox proof and profile check on 158 (ROADMAP **P2.1**).
- Look at the ported UI patches in a running build (tab search position, Thorium 2024 UI, classic
  omnibox): ROADMAP **P2.23**.
- uBlock Origin on 158 (ROADMAP **P2.18**).
