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
  maintained it since 2021. Thorium is © 2021–2026 Alexander Frick, BSD-3-Clause
  ([`LICENSE.md`](LICENSE.md)).
- **Ho Cheung ([@gz83](https://github.com/gz83), [@hocheung-chromium](https://github.com/hocheung-chromium))**
  is the current day-to-day maintainer of Thorium (M144 onwards) and the author of most recent
  Thorium development.
- **[@midzer](https://github.com/midzer)** maintains Thorium's APT repository and website, and has
  helped with builds.
- **[@robrich999](https://github.com/robrich999)** contributed information and fixes credited in
  Thorium's README.

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

Thorium is built from patches by many projects, as documented in [`docs/PATCHES.md`](docs/PATCHES.md).
Each patch keeps its original attribution.

| Project | Link | Licence of the project |
|---|---|---|
| ungoogled-chromium | https://github.com/ungoogled-software/ungoogled-chromium | BSD-3-Clause |
| Bromite | https://github.com/bromite/bromite | GPL-3.0 |
| Cromite (successor of Bromite) | https://github.com/uazo/cromite | GPL-3.0 |
| Debian Chromium packaging | https://salsa.debian.org/chromium-team/chromium | see licence inventory (ROADMAP **L.1**) |
| chromium-ubuntu-build (saiarcot895) | https://github.com/saiarcot895/chromium-ubuntu-build | see licence inventory (ROADMAP **L.1**) |
| Iridium | https://github.com/iridium-browser/iridium-browser | BSD-3-Clause |
| Vanadium (GrapheneOS) | https://github.com/GrapheneOS/Vanadium | see licence inventory (ROADMAP **L.1**) |
| Inox patchset | https://github.com/gcarq/inox-patchset | BSD-2-Clause |
| Supermium | https://github.com/win32ss/supermium | see licence inventory (ROADMAP **L.1**) |
| Brave | https://github.com/brave/brave-core | MPL-2.0 |

## Bundled and related software

- **uBlock Origin**: Raymond Hill ([@gorhill](https://github.com/gorhill)) and contributors,
  GPL-3.0. Thoron bundles the **unmodified** official release as a separate extension
  (https://github.com/gorhill/uBlock).
- **pak tool**: [@myfreeer](https://github.com/myfreeer)'s
  [chrome-pak-customizer](https://github.com/myfreeer/chrome-pak-customizer), MIT, with LGPL-2.1
  parts (`pak_src/`).
- **JPEG XL support**: [thorium-libjxl](https://github.com/Alex313031/thorium-libjxl) (BSD-3-Clause),
  built on [libjxl](https://github.com/libjxl/libjxl) by the JPEG XL authors.
- **Thorium-WinUpdater**: ltguillaume and Alex313031 (https://codeberg.org/ltguillaume/thorium-winupdater),
  the community Windows updater that inspired Thoron's own updater. Thoron does not bundle it.

## Thoron by KuchiSofts

Thoron's own work covers the updater, import, packaging, security tooling, branding and
documentation. It is developed by [KuchiSofts](https://github.com/KuchiSofts) and released under the
same BSD-3-Clause terms as Thorium, unless a file says otherwise. The Thoron logo artwork is
© 2026 KuchiSofts, licensed CC BY 4.0.

If we have missed or mis-credited anyone, please
[open an issue](https://github.com/KuchiSofts/thorium/issues). Correct credit matters to us.
