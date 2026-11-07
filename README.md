# Thoron

**A fast, secure, Thorium-based browser for Windows 11 and Ubuntu.**

> Thoron is an independent browser by KuchiSofts, based on Thorium by Alex313031 and Chromium by The
> Chromium Authors. It is not affiliated with or endorsed by the Thorium project or Google.

*Thoron* is the gas that thorium naturally turns into: a browser **born from
[Thorium](https://github.com/Alex313031/thorium)**.

---

## Status

**Pre-release: there are no Thoron builds yet.** Phase **P0 (foundation)** is in progress. See the
[roadmap](ROADMAP.md) for what is being built, in what order, and how each step is verified.

## Why Thoron

Thoron keeps everything that makes Thorium fast and adds a strict set of commitments:

- **Builds you can trace.** Every release is built from a tagged commit in this repository, and the
  tag points to exactly what was built. Build details (Chromium version, toolchain, our commit) ship
  with every release in `BUILDINFO.json`.
- **Signed updates.** Every update manifest and every checksum file is signed. The updater refuses
  anything unsigned, altered, or older than what you have.
- **Fast security fixes.** Our target is to ship within **7 days** of a Chrome release that fixes an
  actively exploited vulnerability, and within **14 days** of each new Chrome major version.
- **A full changelog every release.** It covers Chromium security fixes, our changes, upstream Thorium
  changes (credited to their authors), fixed and known issues, and checksums.
- **Your data is never touched.** Updates and imports never delete, move or modify your profile.
  Before every major-version update your profile is snapshotted, so it can be rolled back.
- **Full credit, no shortcuts with licences.** See [Credits](#credits) and [`NOTICE`](NOTICE).
- **No telemetry.** The only thing Thoron fetches for itself is the signed update manifest and update
  packages.

## Platforms

| OS | CPUs | Packages |
|---|---|---|
| Windows 11 | x64 (AMD, Intel), ARM64 | installer `.exe`, portable `.zip` |
| Ubuntu 24.04 / 26.04 LTS | x64 (AMD, Intel), ARM64 | `.deb` via a signed APT repository, portable `.tar.xz` |

You never have to choose a build variant. The installer and the updater detect your CPU and pick the
fastest build it supports: **AVX2**, with an **SSE4** fallback for older PCs, or **ARM64**. ARM64
builds stay labelled *beta* until they have been tested on real devices.

## Planned features

| Feature | What it does | Roadmap |
|---|---|---|
| Smart updater | Small delta downloads for installed **and** portable copies. Updates are staged in the background and applied on relaunch, with a one-step rollback. Full installers stay available. | [P3](ROADMAP.md#p3--updater-v1--import) · [P4](ROADMAP.md#p4--updater-v2) |
| Import from your browser | Brings over **open tabs and tab groups** (names, colours, pinned tabs), bookmarks, history, passwords, settings and extensions from Thorium, Chrome, Edge, Brave, Vivaldi, Opera, and later Firefox. Your old browser is never modified. | [P3](ROADMAP.md#p3--updater-v1--import) |
| Built-in ad blocking | The genuine, unmodified uBlock Origin, pinned and verified, kept up to date. | [P5](ROADMAP.md#p5--quality) |
| Protected portable profiles | Saved passwords and cookies in the portable version are encrypted with **your passphrase**, so they work on any PC and stay safe if the folder is lost. | [P4](ROADMAP.md#p4--updater-v2) |
| Performance tracking | Every release is benchmarked (Speedometer, JetStream, MotionMark, startup, memory, idle CPU). A regression blocks the release. | [Q track](ROADMAP.md#quality--performance-q) |

## Verifying downloads

Each release will include `SHA256SUMS` and its signature `SHA256SUMS.minisig`. The public key will be
published in this README and in the release notes with the first release.

```powershell
# Windows (PowerShell): compare with the matching line in SHA256SUMS
Get-FileHash .\Thoron_AVX2_installer.exe -Algorithm SHA256
```

```shell
# Ubuntu
minisign -Vm SHA256SUMS -P <thoron-public-key>
sha256sum --check --ignore-missing SHA256SUMS
```

Thoron's Windows binaries are **not Authenticode-signed yet**, so Windows SmartScreen will warn on
first install, as it does for upstream Thorium today. Verify the checksum as shown above. Code signing
is on the [roadmap](ROADMAP.md).

## Building

Thoron's own build documentation arrives in **P1**. Until then, the Thorium build guides apply:
[Windows](docs/BUILDING_WIN.md) · [Linux](docs/BUILDING.md).

## Security

Please report vulnerabilities **privately**, never in public issues. See [`SECURITY.md`](SECURITY.md).
Every upstream change is audited with [`tools/audit`](tools/audit/README.md) before it is merged.

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the commit style, the
definition of done (which includes keeping these docs current), and copyright rules.

## Credits

Thoron stands entirely on the work of others. **Thank you to Alexander Frick (Alex313031)**, who created
Thorium, to **Ho Cheung (gz83)**, Thorium's current maintainer, to **midzer** and every Thorium
contributor, and to **The Chromium Authors**. Thanks also to the projects whose patches Thorium uses
(ungoogled-chromium, Bromite/Cromite, Debian, Iridium, Vanadium and others), and to **Raymond Hill** for
uBlock Origin. Full list: [`CREDITS.md`](CREDITS.md).

## Licence

Code: BSD-3-Clause ([`LICENSE.md`](LICENSE.md), © Alexander Frick, with Thoron changes © KuchiSofts).
Some patches originate from GPL-3.0 projects; binaries containing them are distributed under GPL-3.0
terms, with source in this repository. uBlock Origin is GPL-3.0. Details: [`NOTICE`](NOTICE).

The original Thorium README is preserved at
[`docs/upstream/THORIUM_README.md`](docs/upstream/THORIUM_README.md).
