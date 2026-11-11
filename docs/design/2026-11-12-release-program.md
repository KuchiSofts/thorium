# Release program: the road to Thoron 0.1.1

Status: decided 2026-11-12. This note records what the owner asked for and how it is built. It narrows the
[main design](2026-11-07-thoron-design.md) (sections 7 and 8) to a first release on Windows.

## 1. What the owner asked for

- Windows first. Linux and ARM64 follow once Windows releases run smoothly.
- Thoron has its own versions, starting at **0.1.1**. Every release gets the next number by itself.
- Releases are published on GitHub. The browser updates itself from inside.
- An update never deletes or changes the user's data.
- One installer for good: running it installs the newest release. No new installer per release.
- The first run offers to bring everything over from other browsers and to make Thoron the default.
- The changelog is short: one line per change.
- The repository holds only our open source code, is clean and protected, and has a wiki.
- Security and the safety of people's data come first in every one of these.

## 2. Versions

| | Example | Who uses it |
|---|---|---|
| **Thoron version** | `0.1.1` | People: About page, installer, release title, tag `v0.1.1`, changelog |
| **Build version** | `158.0.8127.3000` | Machines: websites, extensions, Chromium's component updates, Windows, the updater |

- The Thoron version is `0.MINOR.PATCH`. The release script adds one to PATCH for every release. MINOR goes
  up, and PATCH back to 0, when Thoron moves to a new Chromium major version or ships a headline feature.
- The build version keeps the scheme of ROADMAP P2.14 (Chromium's four numbers, the last one carrying the
  rebuild). It must stay Chromium's: websites and extensions ask for the Chromium version, Chromium's
  component updates are served by it, and Windows and the updater only ever install a higher one.
- "Every release" means every published release. Changes that are merged but not released wait under
  `[Unreleased]` in the changelog.
- One source of truth: the release script writes both versions into the build and into the update
  manifest, and refuses a Thoron version that is not the next one or a build version that is not higher.

## 3. What a release holds (Windows x64)

| File | What it is |
|---|---|
| `ThoronSetup.exe` | The small installer that never changes (section 5) |
| `thoron-<version>-win-x64.exe` | The full installer; the small installer and the updater download it |
| `update.json`, `update.json.sig` | The update manifest and its Ed25519 signature |
| `SHA256SUMS`, `SHA256SUMS.sig` | Checksums of every file, signed |
| `BUILDINFO.json` | Chromium version, toolchain, the commit it was built from |
| Release notes | The version's section of the changelog |

One script makes a release: it runs the tests, the docs and privacy linter, the package audit and the
profile check, sets the versions, builds, signs, and creates a **draft**. The owner publishes.

Keys: the Ed25519 private key that signs manifests is never in the repository and never on GitHub. The
public key is compiled into the browser and into the small installer. A Windows code signing certificate
is a purchase the owner decides on; until there is one, Windows shows its "unknown publisher" warning.

## 4. Updates from inside the browser (Windows)

Chromium's own installer already knows how to put a new version next to a running browser and swap it in at
the next start, without touching the profile. Thoron's updater therefore only has to find, check and fetch.

1. **Check:** on a schedule and when the About page is opened, fetch `update.json` and its signature from
   the newest GitHub release. The request carries no identifier. Nothing is sent but the request itself.
2. **Verify first:** the signature is checked before a single byte of the manifest is read as data. A
   manifest that is unsigned, altered, expired or older than the installed build is refused.
3. **Fetch:** download the full installer into a folder only the user can write to; check its size and
   SHA-256 against the signed manifest; keep the file open so it cannot be swapped between check and run.
4. **Apply:** run the installer for this user (no administrator rights, no prompt). It installs the new
   version beside the running one.
5. **Relaunch:** the About page says the update is ready; the next start runs the new version.

Rules:

- The update never opens `User Data`. Every release must pass the profile check on real profiles (Q.7).
- Before an update to a new Chromium major version, the critical profile files are snapshotted, because an
  older version cannot open a profile a newer one has used (P3.7).
- Three settings: update automatically (default), tell me only, off.
- Any failure leaves the installed version as it is and says so on the About page.
- Smaller delta downloads come later (P4); the first updater fetches the full installer.

## 5. One installer for good

`ThoronSetup.exe` is a small program that does what the updater does, once: read the signed manifest,
download the newest full installer, verify it, run it. Because it carries no browser, it does not change
from release to release, so one link is enough for good:
`https://github.com/KuchiSofts/thoron/releases/latest/download/ThoronSetup.exe`.

The full installer stays available in every release for people who install without a network.

## 6. First run

- **Import:** Thoron looks for other browsers on the PC and offers to bring over bookmarks, history,
  passwords, cookies, extensions, settings and open tabs with their groups (P3.13 to P3.15). It copies and
  never moves or changes the other browser's data, and it asks the person to close that browser first.
- **Default browser:** Thoron registers itself for web links and for the file types a browser opens. Windows
  10 and 11 do not let a program make itself the default silently, so Thoron opens Windows' own page for it.
  Declining leaves everything as it was. Nothing is taken over behind the person's back.

## 7. The source in the repository

`main` holds everything a release is built from and nothing else: the build and release tools, the docs,
the brand assets, and the browser's source changes. Those are a patch series on top of Thorium's, so they
are kept as an overlay on one pinned upstream commit:

- `source/UPSTREAM.json`: the upstream repository, the commit, the Chromium version and the hash of the
  finished tree;
- `source/overlay/`: every file Thoron adds or changes on top of that commit;
- `source/REMOVED.txt`: the upstream files Thoron leaves out.

`tools/build/source_tree.py` rebuilds the build tree from these and checks the hash, so anyone can see and
reproduce exactly what a release was built from. Upstream's own files are fetched, not copied into `main`.

A file that must not be published is recorded by its hash only: the patch with Google credentials that
are not Thoron's (L.8) and six patches whose authors publish no licence (L.1). The tree hash still
verifies, and the list is in `source/README.md`. Both lists must be empty before the first release.

## 8. Changelog and wiki

- `CHANGELOG.md`: per Thoron version, one line per change under Added, Changed, Fixed, Removed and Security.
  Explanations live in the design docs. Release notes are that version's section.
- The wiki explains Thoron to people who use it: what it is, install, update, import, privacy and security,
  versions, building, questions and answers. Updating it is a step of every release.

## 9. Security review

| Threat | Answer |
|---|---|
| A forged or altered manifest or installer | Ed25519 signature checked first; installer SHA-256 comes from the signed manifest |
| Being pushed back to an old, vulnerable version | Only a higher build version installs; manifests expire |
| A taken-over GitHub account | It can publish files, but not sign them: the key is not on GitHub |
| The signing key is lost or stolen | A second, offline key can sign a manifest that replaces the first key (`min_updater_version`) |
| A file swapped between check and run | Private download folder; the checked file stays open until it runs |
| Tracking through update checks | No identifier, no telemetry; updates can be turned off |
| An update damaging a profile | The update never opens the profile; profile check before every release; snapshot before a major version |
| A default-browser or import step that oversteps | Both are offers; both do only what is shown; import copies and never changes the source |

## 10. Before the first public release

- The source is in `main` (P2.25) and the repository is clean and protected (P2.26).
- Every patch has a known origin and a compatible licence (L.1), and the release carries the licence
  texts and source pointers (L.2).
- The decision on Google API credentials is final (L.8). Today's build still carries the ones inherited
  from upstream; a public release ships no credentials that are not Thoron's.
- The signing key exists and is kept safely (P2.11).
- Version, updater and installer are in the build (P2.24, P3.19, P3.20); the first run follows (P3.21).
- The owner says yes to publishing.
