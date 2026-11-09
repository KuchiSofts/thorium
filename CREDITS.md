# Credits

Thoron exists because of the work of many people and projects. This file credits them. Every
original copyright notice in this repository is kept exactly as its authors wrote it. For the
licence of each component, see [`NOTICE`](NOTICE).

> Thoron is an independent browser by KuchiSofts, based on Thorium by Alex313031 and Chromium by The
> Chromium Authors. It is not affiliated with or endorsed by the Thorium project or Google.

## The Chromium Authors

[Chromium](https://www.chromium.org/) is the open-source browser project that Thoron, Thorium,
Google Chrome and many other browsers are built on. Thoron would not be possible without the
thousands of Chromium contributors. Their third-party credits ship inside the browser at
`chrome://credits`.

## Thorium

Thoron is a fork of [Thorium](https://github.com/Alex313031/thorium), and most of its features,
patches, build tooling and documentation come from the Thorium project.

- **Alexander Frick ([@Alex313031](https://github.com/Alex313031))** created Thorium and has
  maintained it since 2021. Thorium is © 2021-2026 Alexander Frick, BSD-3-Clause
  ([`LICENSE.md`](LICENSE.md)). To support his work, see
  [github.com/sponsors/Alex313031](https://github.com/sponsors/Alex313031).
- **Ho Cheung ([@gz83](https://github.com/gz83), [@hocheung-chromium](https://github.com/hocheung-chromium))**
  is the current day-to-day maintainer of Thorium (M144 onwards) and the author of most recent
  Thorium development.
- **[@midzer](https://github.com/midzer)** maintains Thorium's APT repository and website, and has
  helped with builds.
- **[@RobRich999](https://github.com/RobRich999)** contributed information and fixes credited in
  Thorium's README. His [Chromium_Clang](https://github.com/RobRich999/Chromium_Clang) optimisation
  work is also the origin of several Thorium patches and build settings (see `docs/upstream/PATCHES_M138.md`).

### Upstream Thorium contributors

This list is generated from GitHub by `tools/credits/contributors.py`. Bots are excluded, and
anonymous contributors are credited by name only.

<!-- contributors:start -->
- [@Alex313031](https://github.com/Alex313031) (4905 commits)
- [@gz83](https://github.com/gz83) (18 commits)
- [@hocheung-chromium](https://github.com/hocheung-chromium) (18 commits)
- [@midzer](https://github.com/midzer) (5 commits)
- [@RoyalOughtness](https://github.com/RoyalOughtness) (2 commits)
- [@szepeviktor](https://github.com/szepeviktor) (2 commits)
- Alexander Frick (1 commit)
- [@brian6932](https://github.com/brian6932) (1 commit)
- [@Delphox](https://github.com/Delphox) (1 commit)
- [@dougluce](https://github.com/dougluce) (1 commit)
- [@eifr](https://github.com/eifr) (1 commit)
- [@tomByrer](https://github.com/tomByrer) (1 commit)
- [@yochananmarqos](https://github.com/yochananmarqos) (1 commit)
- [@ziemek99](https://github.com/ziemek99) (1 commit)
<!-- contributors:end -->

## Projects whose patches Thorium and Thoron use

Thorium is built from patches by many projects, as documented in Thorium's [`PATCHES.md`](docs/upstream/PATCHES_M138.md) (M138 copy).
Each patch keeps its original attribution.

| Project | Link | Licence of the project |
|---|---|---|
| ungoogled-chromium | https://github.com/ungoogled-software/ungoogled-chromium | BSD-3-Clause |
| Bromite | https://github.com/bromite/bromite | GPL-3.0 |
| Cromite (successor of Bromite) | https://github.com/uazo/cromite | GPL-3.0 |
| Debian Chromium packaging | https://salsa.debian.org/chromium-team/chromium | see licence inventory (ROADMAP **L.1**) |
| chromium-ubuntu-build (saiarcot895) | https://github.com/saiarcot895/chromium-ubuntu-build | BSD-3-Clause (its `debian/copyright` licenses the patches as the patched Chromium sources) |
| Iridium | https://github.com/iridium-browser/iridium-browser | BSD-3-Clause |
| Vanadium (GrapheneOS) | https://github.com/GrapheneOS/Vanadium | GPL-2.0-only (no current patch uses its code) |
| Inox patchset | https://github.com/gcarq/inox-patchset | BSD-2-Clause |
| Supermium (win32ss) | https://github.com/win32ss/supermium | not stated (no licence published) |
| Brave | https://github.com/brave/brave-core | MPL-2.0 |
| Chromium_Clang (RobRich999) | https://github.com/RobRich999/Chromium_Clang | not stated (no licence published) |
| enable-chromium-hevc-hardware-decoding (StaZhu) | https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding | MIT |
| chromium-win64 (Hibbiki) | https://github.com/Hibbiki/chromium-win64 | not stated (no licence published) |
| chromium-patches (qcasey) | https://github.com/qcasey/chromium-patches | not stated (no licence published) |
| electron-chromium-codecs (Muril-o) | https://github.com/Muril-o/electron-chromium-codecs | not stated (no licence published) |
| ungoogled-chromium-windows | https://github.com/ungoogled-software/ungoogled-chromium-windows | BSD-3-Clause |
| ungoogled-software contrib | https://github.com/ungoogled-software/contrib | public domain (its README, for files without a licence) |
| chromium_os-raspberry_pi (FydeOS) | https://github.com/FydeOS/chromium_os-raspberry_pi | BSD-2-Clause |

Patch contributors named in Thorium's patch copyright lines are credited too: icepie, not-lucky,
qcasey, tomByrer and win32ss (Shane Fournier).

The origin and licence of every patch is in the licence inventory
[`docs/legal/PATCH_LICENSES.md`](docs/legal/PATCH_LICENSES.md), with the research method in
[`docs/legal/PATCH_ORIGINS.md`](docs/legal/PATCH_ORIGINS.md) (ROADMAP **L.1**). "Not stated" means the
author publishes no licence; those patches need the author's permission, or a rewrite, before a release.

## Bundled and related software

- **adblock-rust** (native ad blocking, in development): Brave Software and contributors,
  [brave/adblock-rust](https://github.com/brave/adblock-rust), MPL-2.0. Vendored unmodified with the crates it
  needs, each under MIT or Apache-2.0: `addr`, `arrayvec`, `flatbuffers` (Google), `form_urlencoded`, `idna`,
  `idna_adapter`, `percent-encoding`, `precomputed-hash`, `psl`, `psl-types`, `rustc-hash`, `rustc_version`,
  `seahash`, `semver`, `thiserror` 1.x, `url`. Two small build fixes are kept as patches (the MIT text `seahash`
  does not ship; FlatBuffers without nightly-only features).
- **uBlock Origin**: Raymond Hill ([@gorhill](https://github.com/gorhill)) and contributors,
  GPL-3.0. Thoron bundles the **unmodified** official release as a separate extension
  (https://github.com/gorhill/uBlock).
- **pak tool**: [@myfreeer](https://github.com/myfreeer)'s
  [chrome-pak-customizer](https://github.com/myfreeer/chrome-pak-customizer), with changes by
  Alex313031. It is MIT, with LGPL-2.1 parts (`pak_src/` in the upstream repository). Thoron does not
  ship it.
- **thorium-win-upgrade**: [@hezhizheng](https://github.com/hezhizheng)'s Windows upgrader,
  [thorium-win-upgrade](https://github.com/hezhizheng/thorium-win-upgrade) (MIT). It is referenced by
  the upstream repository as the `infra/upgrader` submodule; Thoron does not ship it.
- **JPEG XL support**: [thorium-libjxl](https://github.com/Alex313031/thorium-libjxl) (BSD-3-Clause),
  built on [libjxl](https://github.com/libjxl/libjxl) by the JPEG XL authors.
- **Thorium-WinUpdater**: ltguillaume and Alex313031 (https://codeberg.org/ltguillaume/thorium-winupdater),
  the community Windows updater that inspired Thoron's own updater. Thoron does not bundle it.

## Thoron by KuchiSofts

Thoron's own work covers the updater, import, packaging, security tooling, branding and
documentation. It is developed by [KuchiSofts](https://github.com/KuchiSofts) and released under the
same BSD-3-Clause terms as Thorium, unless a file says otherwise. The Thoron logo artwork is
© 2026 KuchiSofts, licensed CC BY 4.0.

If we have missed or mis-credited anyone, please open an issue on
[KuchiSofts/thoron](https://github.com/KuchiSofts/thoron). Correct credit matters to us.
