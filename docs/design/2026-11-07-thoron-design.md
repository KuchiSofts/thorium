# Thoron (a Thorium-based browser by KuchiSofts) - Design
### Windows 11 + Ubuntu · x64 + ARM64

Status: **approved by owner 2026-11-07** · Date: 2026-11-07 · Owner: KuchiSofts

**Name [owner]: Thoron.** Thoron is the radioactive gas (radon-220) that thorium naturally decays
into: "born from Thorium". Every surface (README, installer, About page) credits Thorium by
Alex313031 as the origin, and states that Thoron is independent and not endorsed by the Thorium
project. The source repository is `KuchiSofts/thoron` (renamed on 2026-11-07 and being detached from the Thorium fork network to stand alone; credit to Thorium stays in the docs and in the full git history).

This document describes what we are building in the `KuchiSofts/thoron` fork and why,
so that a builder can plan the work without further back-and-forth. Items marked
**[owner]** were decided by the owner. Items marked **[call]** are the author's
defaults; the owner may override them.

---

## 1. Intent and why

Thorium is a performance-focused Chromium fork created by Alex313031 and maintained today by a
small group of volunteers. Thoron builds on their work. A review of upstream in November 2026
(source, releases and issues) shaped the goals below.

**Observations** (all verifiable from public data on 2026-11-07):

- **Version gap.** Chrome stable was 158.0.8127.18, and the newest Thorium release was
  156.0.8078.28. Older Thorium releases lack later Chromium security fixes.
- **Release traceability.** The `M150.0.7871.47` and `M150.0.7871.101` release tags (in
  Alex313031/thorium and gz83/thorium) point to commit `91b29e1`, which is the M138 `main`
  branch. The M150 source branch linked from those release pages is no longer available. The M156
  release commit is reachable only through its tag. This makes it hard for outsiders to match a
  binary to its exact source.
- **Release process.** Upstream's maintainer has described building, packaging and publishing
  releases as a manual process. Automating it is a stated hope
  ([upstream issue #1313](https://github.com/Alex313031/thorium/issues/1313)). Releases are not
  code-signed.
- **Windows updates.** Upstream does not currently ship a Windows updater. Users update by
  downloading new installers (about 190-310 MB), or use the community Thorium-WinUpdater.
- **Code review result.** No telemetry, crypto-mining, remote-execution, persistence or unknown
  network endpoints were found in the M156 changes. A sample installed M150 build was byte-identical
  to its official release.

The goal is **traceable builds, faster security updates and a built-in updater**. Upstream's code
and its maintainers are not in question.

**[owner]** The goal is the fastest, smartest and most secure Thorium: no memory leaks, no CPU
hogging. Releases are built from public, audited source, ship with a full changelog, always
credit upstream authors, never infringe copyright, and update themselves in small downloads
without ever touching user data.

## 2. Who it is for **[owner]**

Public users on GitHub, specifically:
1. **Existing Thorium users**, who switch in place and keep everything (bookmarks, passwords,
   history, extensions, settings).
2. **New users.**
3. **The owner**, as a daily driver.

Platforms **[owner, updated 2026-11-07]**:

| OS | CPUs |
|---|---|
| Windows 11 | x64 (AMD, Intel), ARM64 (for example Snapdragon X) |
| Ubuntu Linux | x64 (AMD, Intel), ARM64 |

**[call]** Supported Ubuntu releases are the current LTS releases (24.04 and 26.04). Other
Debian/Ubuntu derivatives are best-effort.

## 3. Goals, non-goals, anti-goals

### Goals
- **G1 Trustworthy builds.** Every release is built from a tagged commit in this repo; the tag
  points to exactly what was built. Every artifact has a SHA-256 checksum and an Ed25519
  signature. Binaries are Authenticode-signed once a certificate exists (see §11).
- **G2 Security currency.** Track Chrome stable. Targets **[call]**: ship within 7 days of a
  Chrome release that fixes an in-the-wild exploit, and within 14 days of a new Chrome major
  version.
- **G3 Smart updater** for installed and portable builds: small delta downloads with a full
  package fallback, background staging, swap on relaunch, automatic CPU-variant selection,
  pre-update profile snapshots, one-step rollback, signed manifests. **[owner]**: it must never
  remove user data, and full installers and portable packs stay downloadable.
- **G4 Full changelog every release [owner]**: Chromium version and security fixes, Thorium
  patch changes, our changes, fixed issues, known issues, checksums, and credits.
- **G5 Credits and copyright [owner]**: always credit; keep every copyright and license notice;
  never infringe.
- **G6 Built-in ad blocking** based on uBlock Origin, kept up to date.
- **G7 Measured performance**: no CPU or memory regressions release over release, tracked with
  repeatable benchmarks.

### Non-goals (for now)
- macOS, Android, ChromiumOS, 32-bit (x86 or ARM), non-Ubuntu Linux packaging (Fedora RPM,
  Flatpak, Arch), and Windows 10 builds. Windows 10 may work but is untested.
- Running our own update servers or databases. Everything is served from GitHub as static files.
- Supporting every SIMD variant upstream ships. We ship the minimum set in §6.3.

### Anti-goals (failure even if it "works")
- Any loss of user data, ever, including on update, rollback, uninstall or migration.
- Any telemetry or phoning home beyond fetching the update manifest and packages.
- Shipping a binary that cannot be traced to a public commit.
- Taking over an existing upstream Thorium install without the user's explicit consent.
- Implying that Alex313031 or upstream maintainers endorse this fork.
- Updates that need admin rights or a UAC prompt.
- Personal or profile data ever entering the repository.

## 4. Constraints and known facts

- **Build host.** Chromium cannot build on free GitHub-hosted runners (6-hour limit, about 14 GB
  of disk). Builds run on a maintainer-owned high-end Windows 11 workstation (16+ cores, AVX2 and
  AVX-512, 64 GB-class RAM, well over 1 TB free), which is enough for Chromium builds. That
  machine may later become a self-hosted runner.
- **Build hosts per platform [call]:**
  - **Windows x64 and Windows ARM64:** built on the Windows PC. Chromium supports cross-compiling
    ARM64 from x64.
  - **Linux x64 and Linux ARM64:** built in **WSL2 Ubuntu 24.04** on the same PC, with ARM64
    cross-compiled using the Chromium sysroot. Chromium cannot build Linux targets from Windows.
  - **Disk:** budget about 150 GB per checkout and output directory.
- **ARM testing:** ARM builds are cross-compiled. Until the owner has ARM hardware, they get smoke
  tests under emulation (QEMU) plus community testers. A real Windows-on-ARM device and an ARM64
  Linux device are recommended before ARM leaves "beta".
- **Linux sandbox:** Ubuntu 23.10+ restricts unprivileged user namespaces. The `.deb` must install
  an AppArmor profile so Chromium's sandbox works. Builds must never fall back to `--no-sandbox`.
- **Toolchain.** Visual Studio 2022, Windows 11 SDK 10.0.22621.x, depot_tools, and 100+ GB per
  checkout (see `docs/BUILDING_WIN.md`).
- **Starting source.** Upstream's newest release source is gz83 tag `M156.0.8078.28`
  (commit `de9a1bc6`). Upstream `main` is still M138.
- **Upstream patch series.** M156 applies an ordered patch series (`patch_scripts/series/series`)
  plus overlay files under `src/`.
- **Manifest V2.** Chromium is removing Manifest V2 extension support, which uBlock Origin
  needs. Thorium currently keeps it working with patches, and the cost grows with each Chromium
  version.
- **Delta tooling.** Chromium ships Zucchini (`//components/zucchini`), Google's binary-diff tool
  for Windows executables.
- **GitHub API limits.** Unauthenticated GitHub API calls are capped at 60 per hour per IP, so
  update checks must use static release-asset URLs, not the API.

## 5. Repository and source strategy [call]

- Keep upstream as read-only remotes (`Alex313031/thorium`, `gz83/thorium`). Never rewrite upstream
  history.
- Default branch `main` holds the README, ROADMAP, CREDITS, SECURITY, CHANGELOG, docs and tools.
  Build branches are named `ks/M<major>`, for example `ks/M156` from gz83 `de9a1bc6`, then
  `ks/M158`.
- Our own changes live as separate, clearly named patches (`other/ks-*.patch`) with our header,
  so the upstream patch series stays recognisable and attributable.
- Every upstream merge is reviewed with the audit scripts (§9) before it lands.
- Tags are signed and match the exact commit built. Commits are made under a GitHub noreply
  identity (see §11).

## 6. Build, variants and packaging

### 6.1 Build
- A single scripted entry point (Python) runs: sync to the pinned Chromium tag, apply the series,
  build, package, sign, and produce release metadata.
- It writes `BUILDINFO.json` into every release: Chromium tag, our commit, depot_tools
  revision, VS/SDK versions, GN args hash, and build timestamp.
- Deterministic-build options are enabled where Chromium supports them, so a second builder can
  compare hashes later. That comparison is a stretch goal.

### 6.2 What ships in each release
- A full installer (mini_installer based), per variant.
- A portable ZIP, per variant.
- Delta packages from each of the previous 3 releases, per variant.
- `update-manifest.json` with its signature.
- `SHA256SUMS` with its signature.
- `BUILDINFO.json`, release notes (changelog excerpt), and a license bundle.

### 6.3 Variants [call]

| Platform | Variants | Packages |
|---|---|---|
| Windows x64 | **AVX2** (primary), **SSE4** (fallback) | installer `.exe`, portable `.zip` |
| Windows ARM64 | **ARM64** (armv8-a baseline) | installer `.exe`, portable `.zip` |
| Linux x64 | **AVX2** (primary), **SSE4** (fallback) | `.deb` (signed APT repo), portable `.tar.xz` |
| Linux ARM64 | **ARM64** | `.deb` (signed APT repo), portable `.tar.xz` |

- **SSE4 fallback** covers PCs without AVX2. Windows 11 still supports some Celeron, Pentium Silver
  and Pentium Gold models that lack it.
- **AVX-512** is not shipped at first, because of upstream crash report #1278. It can be added once
  stable.
- **Automatic choice:** the installer and updater pick the variant from the CPU's features (§7.5).
  Users never have to choose.
- **One `.deb` per architecture:** Linux packaging cannot choose a variant at install time, so the
  x64 `.deb` installs both AVX2 and SSE4 binaries, and a tiny launcher picks one at start.
  - **[call]** The size cost of this (about double the binaries) is accepted for correctness.
  - Alternative for the builder to evaluate: separate packages `-avx2` and `-sse4`, with a meta
    package.

## 7. Smart update system (installed and portable)

### 7.1 Architecture [call]
- **The updater is our own**: a small `thorium_updater.exe` built inside the Chromium tree. It reuses
  Chromium's Zucchini, BoringSSL (signature checks) and base libraries.
- **One engine for both modes.** The same updater serves installed and portable builds.
- **No server.** It reads a signed static manifest from GitHub Releases.
- **Why not Chrome's own Omaha updater:** the Chromium updater (`//chrome/updater`) needs a dynamic
  Omaha server and does not support portable mode.
- **Reuse Chromium's existing update experience.** The "relaunch to update" badge and the
  in-use executable swap (`new_thoron.exe` plus rename on next start) are used wherever
  possible, rather than reinventing them.

### 7.2 Manifest and trust
- A stable URL serves `update-manifest.json` plus a detached Ed25519 signature:
  `https://github.com/KuchiSofts/thoron/releases/latest/download/update-manifest.json`.
- **Contents:** channel, version, Chromium version, release date, a `critical` flag (security release),
  `min_updater_version`, an `expires` timestamp, and, per variant, the full package and the deltas
  (`from_version`, URL, size, SHA-256).
- **Verification:** the public key is compiled into the updater. The signature is checked before
  anything is parsed. HTTPS only.
- **Freeze-attack protection** (inspired by The Update Framework): if the only manifest the updater
  can obtain has expired, it warns that it "cannot verify updates" instead of silently reporting
  "up to date".
- **Downgrade protection:** a manifest older than the installed version is rejected, except through
  the explicit rollback command.
- **Key management:** the root signing key is kept offline. A key rotation is valid only if the old
  key signed it.

### 7.3 Delta packages
- **Per-file operations** against the installed version directory: `keep`, `patch` (Zucchini),
  `add`, `delete`.
- Each operation lists the old SHA-256 and the new SHA-256.
- **Staging:** applied into `Application\<new>.staging\`. Every file's hash is checked, then the
  folder is atomically renamed to `Application\<new>\`. Chromium's side-by-side version folders make
  this safe while the browser is running.
- **Fallback:** if any base file doesn't match (modified or damaged install), the updater
  automatically downloads the full package instead. It never patches a file it can't verify.
- **Cheapest route:** the updater compares the size of chaining deltas with the full package and
  downloads whichever is smaller.

### 7.4 Applying the update
- **Browser running:** stage the new version, show the relaunch badge, and swap on the next start
  using Chromium's existing mechanism.
- **Browser closed:** swap immediately.
- The previous version folder (N-1) is kept for rollback; older ones are removed.
- **Portable:** the same steps, inside the portable folder.
  - The portable launcher performs the swap on its next start.
  - It leaves **no trace** outside its folder: no registry entries, no scheduled task.
- **Updater self-update:** the updater updates itself through the same manifest
  (`min_updater_version`).

### 7.5 Smart behaviour
- **Picks the right build:** it chooses the fastest variant the CPU supports.
  - If a portable copy is moved to a PC that can't run its variant, the launcher warns instead of
    crashing, and offers the compatible build.
- **Downloads politely:** downloads resume after interruptions (HTTP range requests or Windows BITS),
  run at low priority, pause on metered connections, and respect proxy settings.
- **Checks on a schedule:**
  - Installed builds check 60 seconds after browser start, and daily via a per-user scheduled task
    (no admin rights).
  - Portable builds check only while the browser is running.
- **Shows its status on the About page** (`chrome://settings/help`): checking, downloading %, ready to
  relaunch, or up to date, plus a "What's new" link to the changelog.
- **Urgent updates stand out:** critical security updates get a more prominent prompt.
- **User controls:** automatic, notify-only, or off. The command line supports `--check`, `--apply`,
  `--status` and `--rollback`.
- **Local log only:** it keeps a local log with no personal data. No telemetry.

### 7.5a Linux update model [call]

Linux has three install types, each with one updater (never both):

**1. System install (`.deb`)**
- Updated **only through our signed APT repository**. It is static, hosted on GitHub Pages, and has a
  signed `InRelease` file.
  - Upstream's APT repository is unsigned (issues #1164, #1049). Ours never is.
- `apt` owns these files. Our updater never modifies dpkg-managed files.
- Downloads are full packages. Delta support via `debdelta` is a later optional improvement.
- **Before a major version:** the snapshot (§7.6) is taken **per user, by the browser itself**,
  before the profile is first opened by the new major version. The root-run package scripts never
  read or copy anyone's profile (least privilege).

**2. Per-user self-updating install** (`~/.local/share/thoron`)
- The same delta updater as Windows: Zucchini supports ELF on x64 and ARM64.
- No root is needed.
- It is the recommended choice for users who want small, fast updates.

**3. Portable (`.tar.xz`)**
- The same delta updater, inside its folder, leaving no trace outside it.

**Common to all three**
- Profile location: `~/.config/thoron` (Chromium's default), or inside the portable folder.

### 7.6 Data-safety model **[owner: never remove user data]**
- **Never touches the profile:** the updater never writes, moves or deletes anything inside
  `User Data`. Its only write targets are the application folder and the snapshot folder.
- **Snapshot before every major-version jump** (Chromium profiles cannot be opened by older
  versions):
  - **When:** at the swap moment, while the browser is closed.
  - **What:** a snapshot of every profile's critical files: `Local State`, `Preferences`,
    `Secure Preferences`, `Bookmarks`, `Login Data*`, `Web Data`, `History`, `Cookies`,
    extension settings, and sessions.
  - **Where:** stored next to `User Data`, never inside it: `Thorium Snapshots\<from>-<to>\`.
  - **Verified:** SHA-256 hashes plus an SQLite integrity check.
  - **Kept:** the last 2 snapshots.
  - Optionally, a full snapshot.
- **Rollback** restores the previous app folder and, if the profile was migrated, the snapshot.
  - It warns clearly that changes made since the update (new bookmarks, new passwords) will be
    lost.
  - It needs explicit confirmation.
- **Uninstall:** keeps user data by default. "Also delete browsing data" stays unchecked.

### 7.7 Own identity + import from existing Thorium **[owner: own identity + import]**

The product has its **own identity** and never installs over upstream Thorium. That identity covers:
- **Windows:** the product name, the install folder `%LOCALAPPDATA%\Thoron\`, the registry key
  `HKCU\Software\Thoron`, the app GUID in `chromium_install_modes.h`, ProgIDs, and the
  AppUserModelID.
- **Linux:** the package name, the `.desktop` file, the profile directory `~/.config/thoron`, and
  the keyring entry `Thoron Safe Storage`.

Upstream and ours can coexist on the same machine. Version numbers are independent of upstream's.

**Importing on first run (or later from Settings)**
- **Detection:** if an upstream Thorium profile exists, the browser offers to import it. Locations:
  Windows `%LOCALAPPDATA%\Thorium\User Data`; Linux `~/.config/thorium`; or an upstream portable folder
  chosen by the user.
- **What happens:**
  1. Upstream Thorium must be closed.
  2. The whole profile is **copied, never moved**.
  3. The copy is verified: SHA-256 of every file plus SQLite integrity.
  4. Only then does our browser start on the copy.
- **The original stays untouched**, and so works as a natural backup.
- **Passwords and cookies must survive the import:**
  - **Windows:** the DPAPI-wrapped key travels inside the copied `Local State`, which works because it
    is the same Windows user.
  - **Linux:** upstream's key lives in the system keyring under `Thorium Safe Storage`. The import
    reads that entry and re-stores it under our product's name. This is an explicit builder task
    with its own test, because a wrong keyring name silently makes every saved password unreadable.
- **Extensions:** they come along in the copy. The frozen Chrome Web Store copy of uBlock Origin
  triggers the optional migration in §10.
- **Afterwards:** the import never disables, modifies or uninstalls upstream Thorium or its updater.
  The user can remove upstream themselves once satisfied, and is told how.

### 7.7a Import from the browser the user selects - including tabs and tab groups **[owner]**

**The installer step**

The installer, and later Settings, shows **"Import from…"** with:
- **Every browser profile it detects**, with each profile's name. Supported sources (P2):
  - **Chromium family:** upstream Thorium, Chrome, Edge, Brave, Chromium, Vivaldi, Opera.
  - **Firefox:** later (P4).
- **A checkbox for each data type:**
  - open windows, **tabs and tab groups** (group name, colour, collapsed state, pinned tabs, and each
    tab's back/forward history where available);
  - bookmarks;
  - history;
  - saved passwords;
  - cookies and logged-in sessions;
  - extensions;
  - settings and search engines;
  - autofill.

**Safety**
- **The source browser must be closed**, because open tabs are only consistent then. The installer
  asks the user to close it and **never** force-closes it.
- **Read-only:** the source is never modified. Everything is copied, and verified (hash plus SQLite
  integrity) before use.

**Tabs and tab groups**
- They are read from the source's session files (`Sessions/` SNSS files for the Chromium family,
  `sessionstore.jsonlz4` for Firefox).
- They are rebuilt by **our own parser**, not by copying the session files blindly. Other vendors add
  their own session data (Edge workspaces and vertical tabs, Vivaldi stacks), which could crash or
  corrupt a copied session.
- On first start, the windows open exactly as they were: tab order, groups, pinned tabs, and the
  active tab.
- Parser requirements: fuzzing, plus golden test files from each supported browser.

**What can and cannot be copied (stated honestly in the UI)**

| Source | Tabs + groups | Bookmarks, history, settings | Passwords | Cookies / logins |
|---|---|---|---|---|
| Upstream Thorium, Chromium, Brave, Vivaldi, Opera | ✅ | ✅ | ✅ (same OS user) | ✅ (same OS user) |
| Edge | ✅ | ✅ | ✅ if not app-bound, else via guided export | ⚠ best-effort |
| Chrome 127+ | ✅ | ✅ | ⚠ guided: Chrome's own "Export passwords" CSV, imported, then the CSV is securely deleted | ❌ Chrome's app-bound encryption blocks this by design, so sites need a fresh login |
| Firefox (P4) | ✅ | ✅ (Chromium's existing Firefox importer) | ✅ (existing importer) | ❌ |

**Rules**
- **Never** bypass another browser's protection (for example Chrome's app-bound encryption).
  Techniques for that are what password-stealing malware uses, and contradict "most secure".
- Every import writes a short local report: what was imported, counts per type, and what was skipped
  and why. The report contains no secrets.

### 7.8 Portable encryption **[owner: passphrase-encrypted]**
- **How it works:** portable profiles encrypt saved passwords and cookies with a random profile key.
  That key is wrapped by a key derived from a **user passphrase** (Argon2id, with strong parameters
  recorded in the profile).
- **On any PC:** the profile opens anywhere once the passphrase is entered.
- **Remember this PC (optional):** stores a second copy of the profile key, wrapped by the OS
  (DPAPI on Windows, libsecret on Linux), so trusted PCs don't prompt.
- **Changing the passphrase** rewraps only the profile key; the data is never re-encrypted.
- **Forgotten passphrase:** passwords and cookies cannot be recovered. That is the point of the
  feature. The setup screen says so plainly and offers a printable recovery key, which is a second
  wrap of the profile key.
- **Importing an upstream portable folder** (upstream keeps it unencrypted, using
  `--disable-encryption`):
  1. Copy the folder.
  2. Verify the copy.
  3. Encrypt the copy.
  4. Verify that it decrypts.
  5. Only then use it. The original is left as it was.
- **Risk control:** this changes Chromium's `os_crypt`, a component that can lose data if it is wrong.
  It needs:
  - its own security review;
  - fuzzing of the key-file parser;
  - round-trip tests (encrypt, move to a "new PC" with a fresh OS key store, decrypt).

  It ships behind a version check, and reading old formats stays supported for good.

## 8. Release process and full changelog **[owner]**

- **Draft first:** releases are always created as GitHub **drafts**. A human reviews and publishes
  them; publishing is never automatic.
- **Release notes** are generated by `tools/release/changelog.py`, and a human then edits the
  "Highlights". They include:
  1. Highlights (human-written).
  2. Chromium version change, with a link to the Chrome Releases post and the list of security fixes
     (CVE, severity).
  3. Our changes, grouped by category: security, performance, fixes, UI, build.
  4. Upstream Thorium commits merged, **credited by author**.
  5. Patches added, removed and refreshed.
  6. Fixed issues and known issues.
  7. Artifacts with sizes and SHA-256 checksums, plus how to verify signatures.
  8. Credits.
- **`CHANGELOG.md`** follows the "Keep a Changelog" format and accumulates every release.
- **Commit prefixes** (`sec:`, `perf:`, `fix:`, `ui:`, `build:`, `docs:`) let the generator group
  changes reliably.

## 9. Credits, licensing and copyright **[owner: always credit, never infringe]**

- **Keep every existing notice:** every existing copyright header and license file stays.
  - `LICENSE.md` (BSD-3-Clause, Alex313031) stays as-is.
  - New files we create carry our own header.
  - Patches taken from other projects keep their original headers, with attribution in the patch
    description.
- **`CREDITS.md`** credits:
  - The Chromium Authors.
  - Alex313031 (Thorium creator).
  - gz83 / Ho Cheung (current upstream maintainer).
  - midzer.
  - All upstream contributors, generated from git history.
  - Projects whose patches Thorium uses: Bromite, ungoogled-chromium, Debian, Iridium,
    Vanadium/GrapheneOS, and saiarcot895's chromium-ubuntu-build.
  - myfreeer (pak tool).
  - Raymond Hill and the uBlock Origin contributors.
- **`NOTICE`** lists each bundled component with its license. `chrome://credits` must remain complete.
- **GPL-licensed patches [call]: comply, don't strip.** Some Thorium desktop patches come from GPLv3
  sources (for example Bromite, as listed in `docs/PATCHES.md`). We keep those features and meet the
  GPLv3 obligations for the Windows binaries:
  - Every release links the exact source: our tag, the Chromium tag, and the patch series.
  - The GPLv3 text ships in the license bundle.
  - `NOTICE`, `LICENSE` notes and the README state which components are GPLv3.
  - Not bundling proprietary Widevine (below) keeps this clean.
  - The builder produces a license inventory of every patch source, and flags any patch whose license
    is unknown or incompatible. Such a patch is rewritten or dropped **before release**.
  - Code whose author publishes no licence counts as not licensed: it needs the author's written
    permission or a clean rewrite before release. GPL-2.0-only code is incompatible with the GPLv3
    patches and is never taken. The 2026-11-08 research is in `docs/legal/PATCH_ORIGINS.md`.
- **Disclaimer** in the README, installer and About page: "Thoron is an independent browser by
  KuchiSofts, based on Thorium by Alex313031 and Chromium by The Chromium Authors. It is not affiliated
  with or endorsed by the Thorium project or Google."
- **Branding:**
  - Thoron gets its **own logo and icons**. Thorium's logo artwork is not reused as Thoron's brand.
  - **Icon redesign [owner, approved 2026-11-07]:** a new icon that fits the name Thoron.
    - **Theme:** radiant gas or energy "born from" an element.
    - **Original artwork** authored as vector SVG source, so copyright is clearly ours.
    - **Every size and format Chromium needs:**
      - Windows: a multi-size `.ico` (16-256 px), plus taskbar, Start tiles and installer images.
      - Linux: `.desktop` PNG icons at 16-512 px, plus scalable SVG.
      - In the browser: product logo resources, the About page, and the new-tab logo.
    - **Readability:** works at 16 px; light and dark variants; meets contrast requirements.
    - Licensed in `NOTICE` under our terms.
  - Thorium's name appears only as credit and origin.
  - Thorium logo files that remain in the source tree for history keep their attribution.
- **Widevine [call, follows the owner's copyright rule]:** Widevine is Google's proprietary DRM
  module, which Netflix and similar services need.
  - We **do not redistribute** it inside our packages.
  - It is fetched from Google at runtime by Chromium's component updater, as Chromium normally
    does.
  - The builder must verify that DRM streaming sites still work, and document any limits.
- **uBlock Origin** (GPLv3, see §10):
  - It is shipped as a separate bundled extension, never compiled into the browser's own code.
    This keeps the browser's license intact.
  - Its license and a source link ship with it.
  - If we ever modify it, we give it a different name, credit uBlock Origin, publish our changes
    under GPLv3, and offer good fixes back to its author.
- **Media codecs:** proprietary codecs (H.264/HEVC/AAC) carry patent, not copyright, questions. We
  follow common Chromium-fork practice and state it in the NOTICE.

## 10. Built-in ad blocking

- **Phase 1 [call]:** for new profiles, bundle the **genuine** uBlock Origin CRX, as upstream M156
  already does.
  - The file comes from gorhill's GitHub release, pinned by SHA-256. Its extension ID is
    `fkgkibajhfbepljeaefdnfnegdcjomkh`, derived from gorhill's own signing key.
  - The builder confirms how that CRX keeps itself updated.
- **Migration for existing profiles:** existing profiles have the Chrome Web Store copy
  (`cjpalhdlnbpafiamejdnhcphjbkeiagm`), which Google no longer updates.
  - We offer a guided switch to the updatable copy that **keeps their uBlock settings and custom
    filters**, using uBlock's own backup and restore.
  - It is never forced.
- **Phase 2 (research):** decide between continuing to keep Manifest V2 alive, or a native
  ad-blocking engine in the browser that reads the same filter lists (as Brave does with
  `adblock-rust`, MPL-2.0).
  - That choice is made once Manifest V2 viability in Chromium 158+ is measured.
- **Priority rule [owner: "always think on security first"]:** security releases (G2) always beat
  ad blocking (G6). Porting Manifest V2 is never on the critical path of a security release.
- **If the bundled Manifest V2 uBlock Origin stops working on a new Chromium:**
  - The release ships anyway.
  - **New profiles** get uBlock Origin Lite (MV3) as a stopgap.
  - **Existing profiles** keep their current blocker for as long as it runs, and the release notes
    say so.
- **Measure early:** Manifest V2 viability is measured in **P1** on Chromium 158, not in P5.

### 10.1 Verdict on Chromium 158 (P1.8, 2026-11-08)

**Needs work, but Manifest V2 itself is viable.** Measured with `tools/build/mv2_check.py` (offline,
fresh profiles, sandbox on, a control run without the extension) on Chromium 158.0.8127.30 with
only upstream's `allow_manifest_v2_extensions.patch` applied (it applies cleanly), against the
reproduced Thorium M156 build:

| Test | Thorium M156 | Chromium 158 + MV2 patch |
|---|---|---|
| Minimal MV2 extension: persistent background page, blocking `webRequest` | blocks every request | blocks every request |
| uBlock Origin 1.75.4 (gorhill CRX, signature verified), network filtering | works (blocks, swaps in its stand-in script) | **does nothing** |
| `chrome.storage.managed.get` from an extension with a managed schema | answers | **never answers** |

- **Root cause found:** at start-up uBlock Origin first reads its admin settings from managed
  storage. On the 158 test build that call never answers, so uBlock waits forever without an error:
  its filter engine is never built (no storage written) and nothing is blocked. Every other start-up
  call it makes (`storage.local`, IndexedDB, `tabs.query`) answers normally.
- **Open question:** the 158 test build is a development configuration (component build, not
  official), while the M156 build is a release build. Whether the managed-storage hang also happens
  in a 158 release build, or only for extensions loaded from the command line, is checked first in
  **P2.1**, where the release configuration is built anyway. The fix is either that answer or a
  small patch in the managed-storage path; tracked as ROADMAP **P2.18**.
- **Cosmetic filtering** could not be observed in headless runs on either version (no element
  hiding, even with highly generic EasyList rules); it needs a test with a normally installed
  extension in a visible window (**P2.18**).
- **Thorium's default apps** install the Web Store copy of uBlock Origin into every new profile;
  Thoron replaces that with the bundled copy (**P2.16**).

## 11. Security program

- **Before every upstream merge:** run the audit tools, committed under `tools/audit/`:
  - added binaries;
  - new network endpoints;
  - suspicious patterns;
  - changes to security features.
- **`SECURITY.md`** explains how to report vulnerabilities privately (GitHub private advisories).
- **Hardening backlog from the audit:** remove `'unsafe-inline'` from the Thorium authors WebUI page,
  and review every flag that weakens security so that it stays opt-in.
- **Privacy guard:** the local pre-push privacy guard remains in place. The repository never contains
  profile data, keys or personal paths.
- **Identity:** commits and tags use a GitHub **noreply** email, never a personal email.
- **Code signing [owner: start unsigned, sign later]:**
  - **Integrity until then:** Ed25519 signatures on the update manifest and on `SHA256SUMS`.
    The updater refuses anything unsigned.
  - **What users see:** Windows SmartScreen shows a warning on first install, as it does for upstream
    today. The README explains this and how to verify a download.
  - **Later:** Authenticode signing slots into the release script once a certificate exists. It is
    used on every `.exe` and `.dll` we build, but not on Google's Widevine.

## 12. Performance and resource health

- **Benchmarks for every release**, compared against the previous release and against Chrome of the
  same major version:
  - Speedometer 3, JetStream 2 and MotionMark;
  - startup time with 1 and with 4 profiles;
  - idle and 20-tab memory;
  - CPU at idle.
- **A regression blocks the release** until it is explained.
- **Windows issues to investigate first:**
  - #1313 (M156 CPU spike and "Unknown Hard Error");
  - #1230 (crash in SQLite);
  - #1278 (AVX-512 crash with suspended tabs);
  - #1288 (STATUS_ACCESS_VIOLATION);
  - #1271 (HEVC/AV1 regression);
  - #137, #684, #1199 (passwords not saved);
  - #1005 (random logouts);
  - #803 (slow start with multiple profiles).

## 13. Roadmap phases

| Phase | Outcome |
|---|---|
| P0 Foundation | README, ROADMAP, CREDITS, NOTICE, SECURITY, CHANGELOG, audit tools, this design |
| P1 Build environment | Reproduce upstream M156 AVX2 from source on the owner's PC (Windows) and in WSL2 Ubuntu (Linux); BUILDINFO; smoke tests; measure Manifest V2 / uBlock viability on Chromium 158; license inventory of patches |
| P2 First release | Rebase to Chromium 158; our patches; signed manifest and checksums; Windows x64 installer and portable, Linux x64 `.deb` (signed APT repo) and portable; full changelog |
| P2b ARM64 | Windows ARM64 and Linux ARM64 builds (cross-compiled), emulated smoke tests, published as "beta" until tested on real devices |
| P3 Updater v1 + Import | Full-package updates, signed manifest, staging and swap, snapshots, rollback, About page; installed and portable. Import from upstream Thorium and other Chromium-family browsers, including tabs and tab groups |
| P4 Updater v2 | Zucchini deltas, resumable downloads, automatic variant selection, freeze protection, updater self-update, Firefox import (tabs and groups included), portable passphrase encryption |
| P5 Quality | uBlock migration, performance work, Windows bug fixes, ad-blocking Phase 2 decision |
| Ongoing | Security releases on the G2 schedule |

## 14. Left to the builder

- Exact file formats (manifest schema, delta container) and their versioning.
- UI wording, and the About page and installer screens.
- Test strategy (unit tests for the updater, an end-to-end update test between two real builds, a
  rollback test, a portable-move test).
- Tooling language for the release scripts (Python is the default, to match upstream).
- Whether the in-use swap reuses the installed `setup.exe` logic or is implemented in the updater.

## 15. Author's calls (for owner review)

1. A custom static-manifest updater built in the Chromium tree, rather than Chrome's Omaha updater.
2. Variants: AVX2 plus an SSE4 fallback, with AVX-512 deferred.
3. Widevine is not bundled; Google's component updater fetches it at runtime.
4. Branch layout `main` + `ks/M<major>`; our patches named `other/ks-*.patch`.
5. Security-release targets of 7 and 14 days.
6. Keep 3 deltas per release; keep the N-1 app folder and the last 2 profile snapshots.
7. Releases are always drafts until a human publishes them.
8. Ubuntu LTS 24.04 and 26.04 only. Linux builds run in WSL2 on the same PC. ARM64 is cross-compiled
   and stays "beta" until tested on real hardware.
9. Linux: system `.deb` installs are updated only by our signed APT repo. Per-user and portable
   installs use the delta updater.
10. Licensing: comply with the GPL for GPL-sourced patches rather than strip the features.
11. Security releases beat ad blocking. Fallback: uBlock Origin Lite for new profiles.

## 16. Owner decisions log (2026-11-07)

| Question | Decision |
|---|---|
| Audience | Public users: existing Thorium users, new users, and the owner |
| Platforms | Windows 11 + Ubuntu; x64 (AMD, Intel) + ARM64 |
| Identity | Own identity; import from existing browsers; never install over upstream |
| Name | **Thoron** |
| Import | From the browser the user selects, **including open tabs and tab groups** |
| Code signing | Start unsigned (Ed25519-signed updates and checksums); add Authenticode later |
| Portable secrets | Passphrase-encrypted, with optional "remember this PC" and a recovery key |
| Priorities | Security first; never lose user data; always credit and never infringe copyright |
| Docs | Every change updates README, ROADMAP, CHANGELOG and every affected `.md` |
| Roadmap | `ROADMAP.md` must be highly detailed |
| Work order (2026-11-08) | Windows first, then Linux: the owner deferred the Linux build tasks and resumed them the same day; both M156 builds are reproduced. Ubuntu stays a target platform |
| Patch licences (2026-11-08) | All 152 M156 patches researched: 6 GPL-3.0 (Cromite, Bromite), the rest BSD, MIT or public domain; 8 use code from authors with no published licence and need permission or a rewrite before the first release (L.1) |
| Rename order (2026-11-08) | The Thoron identity is done first on M156, before the Chromium 158 rebase, by a re-appliable tool; the owner's Thorium profile moves to Thoron by verified copy (§7.7) and Thorium stays as an untouched backup |
| Repository binaries (2026-11-07) | No prebuilt or proprietary binaries in the repository (ROADMAP **L.6**); purging them from history (**L.7**) waits for the owner's decision |

No open questions remain. Anything further found during planning is either a builder decision (§14)
or comes back to the owner as a single batch.
