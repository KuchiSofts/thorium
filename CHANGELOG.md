# Changelog

All notable changes to Thoron are listed here, one line per change.
Thoron versions are `0.MINOR.PATCH`; the first release is 0.1.1. Each release names the Chromium version it is built on.
Explanations live in the design docs under `docs/design/`.

## [Unreleased]

### Added

- **Ad blocking:** built-in `adblock-rust` engine ends ad and tracker requests before they leave the browser.
- **Ad blocking:** off by default; "Built-in ad blocking" on `chrome://flags/#thoron-native-adblock` turns it on or off.
- **Ad blocking:** ships a pre-compiled engine of the bundled filter lists and falls back to the lists if it is broken.
- **Ad blocking:** updates its filter lists at most every 4 days over HTTPS without cookies and refuses a bad update.
- **Ad blocking:** follows the per-site "Ads" setting, shown as "Ads and trackers" while the blocker is on.
- **Ad blocking:** address bar icon and bubble count the ads and trackers blocked on a page; nothing is stored or sent.
- **Ad blocking:** runs uBlock Origin's scriptlets before any page script and answers blocked requests with stand-ins.
- **Ad blocking:** hides page elements by specific, generic and procedural rules and supports `$removeparam` and `$csp`.
- **Ad blocking:** rechecks every redirect, stops blocked targets and strips the tracking parameters the lists name.
- **Ad blocking:** a link to a tracking redirector goes straight to its destination (`$urlskip`, 240 list rules).
- **Ad blocking:** switches off the browser features the lists name for ad targeting and fingerprinting (`$permissions`).
- **Ad blocking:** stops a request when the server's answer gives an ad server away (`$header`, 50 list rules).
- **Ad blocking:** rewrites tracking addresses that uBlock Origin's lists name (`$uritransform`).
- **Ad blocking:** hides ads inside page widgets' shadow trees, open or closed (`:shadow()`).
- **Ad blocking:** blocks files a server asks the browser to preload with "103 Early Hints".
- **Ad blocking:** the shield's bubble lists the sites blocked on the page.
- **Ad blocking:** a shield in the toolbar shows what was blocked on the page and opens a uBlock-style menu.
- **Ad blocking:** per-site switches in the menu: pop-ups, large media, no hiding, remote fonts, JavaScript.
- **Ad blocking:** element picker and zapper: pick an element, make a rule for it, or remove it for now.
- **Ad blocking:** `chrome://adblock` lists allowed sites and switches, and has a live logger of blocked requests.
- **Ad blocking:** `chrome://adblock` offers uBlock Origin's 62 optional lists: cookie notices, annoyances, regions.
- **Ad blocking:** blocked images and frames leave no empty boxes on the page.
- **Ad blocking:** pop-up and pop-under ads are blocked: the lists' 3,112 pop-up rules now work.
- **Ad blocking:** the menu's "no pop-ups" switch stops every window a site opens, as in uBlock Origin.
- **Ad blocking:** `chrome://adblock` has uBlock Origin's settings: the badge, privacy options (pre-fetching,
  hyperlink auditing, WebRTC, CSP reports), default behavior for every site, ignoring generic hide rules.
- **Ad blocking:** the menu shows the share of the page's requests blocked and the domains connected, as
  uBlock Origin's.
- **Ad blocking:** back up the ad blocking setup to a file, restore it from the file, or reset it to the
  defaults, on `chrome://adblock`.
- **Ad blocking:** "Block element..." in the page's right-click menu opens the picker on what was clicked.
- **Ad blocking:** the logger also shows requests let through, and makes Block and Allow rules from them.
- **Ad blocking:** switches for third-party scripts and frames, per site or for every site ("medium mode").
- **Ad blocking:** "My rules": uBlock Origin's dynamic filtering rules (block, allow, noop by site and host).
- **Ad blocking:** the menu's grid of rules for the page, as uBlock Origin's, with Save and Revert.
- **Version:** Thoron has its own version, 0.1.1, on the About page, `chrome://version` and in Windows.
- **Ad blocking:** checks worker and service worker scripts and imports, and blocks WebSockets to hosts the lists block.
- **Ad blocking:** settings page `chrome://adblock`: lists on and off, add a list by address, your own rules.
- **Ad blocking:** every change on that page is in use at once and survives a restart and a browser update.
- **UI:** About page names the Chromium version the build is based on, shows the disclaimer and links to release notes.
- **Brand:** the UI, all translations and `chrome://version` carry the Thoron name, logo and wordmark.
- **Brand:** icon pipeline builds every PNG size, the `.ico` and the tile icons from the logo SVG (CC BY 4.0).
- **Privacy:** release build settings turn off Google's RLZ tracking and the DRM storage ID and take no API keys.
- **Privacy:** `docs/security/NETWORK.md` lists the hosts a fresh profile contacts and what Thoron does about each.
- **Security:** `tools/audit` checks upstream merges and releases with `audit_diff`, `crx_id` and `compare_release`.
- **Install:** Thoron installs next to Thorium on Windows with its own folder, profile, registry key and app ID.
- **Install:** Linux identity is in code (program `thoron`, package `thoron-browser`, own profile); not yet built.
- **Install:** `import_profile.py` brings a Thorium profile into Thoron by a verified copy, never a move.
- **Build:** patch series is rebased to Chromium 158.0.8127.30; Global Privacy Control uses Chromium's own code.
- **Build:** reproduces upstream's Chromium 156.0.8078.28 build on Windows and Linux, without bundled Widevine.
- **Build:** Manifest V2 extensions still work on Chromium 158.
- **Build:** the browser's patch series is in `source/` as an overlay on a pinned upstream commit, with a tree hash.
- **Build:** `source_tree.py` exports, verifies and rebuilds that tree; files that may not be published are withheld.
- **Build:** `pipeline.py` preflights a build and stops on a rejected patch; `BUILDINFO.json` keeps no personal paths.
- **Build:** `smoke.py` tests a build on a throwaway profile and proves that the renderer sandbox is in force.
- **Build:** `wslconfig.py` raises WSL memory and swap for a Linux build and restores the original file byte for byte.
- **Build:** `rebase_report.py` reports how a patch series applies to a newer Chromium without touching the checkout.
- **Legal:** every patch names its origin, author and licence; `patch_headers.py lint` rejects one that does not.
- **Legal:** patch licence inventory covers every patch: none unknown, 6 need the author's permission or a rewrite.
- **Legal:** `CREDITS.md` and `NOTICE` carry upstream credits and per-component licences; a tool lists contributors.
- **Release tools:** `release.py` checks, names, checksums and signs a build and publishes only as a signed draft.
- **Release tools:** `changelog.py` writes release notes from git and local files and credits upstream authors.
- **Release tools:** `package_audit.py` rejects a package with Widevine, Thorium-named files or upstream-only extras.
- **Release tools:** `version.py` sets build numbers: Chromium's version with the last part as `patch x 100 + rebuild`.
- **Release tools:** `version.py rebuild` moves a build tree to the next rebuild of the same Chromium, never back.
- **Release tools:** `version.py thoron` sets Thoron's own version; `check --new-thoron` refuses one not higher.
- **QA tools:** `profile_check.py` and `profile_rehearsal.py` verify on a copy that an update keeps a profile 1:1.
- **QA tools:** `bench.py` measures start-up time, memory and idle CPU offline on throwaway profiles.
- **QA tools:** `adblock_proof.py`, `adblock_breakage.py` and `mv2_check.py` compare blocking with uBlock Origin.
- **QA tools:** offline checks cover filter syntax, redirects, workers, hide rules, the site switch and list updates.
- **QA tools:** `adblock_settings_check.py` works the settings page like a person, offline, in 14 steps.
- **QA tools:** `adblock_urlskip_check.py` checks `$urlskip` offline with real rules of the lists.
- **QA tools:** `adblock_header_check.py` checks `$header` offline with real rules of the lists.
- **QA tools:** `adblock_uritransform_check.py` and `adblock_earlyhints_check.py` check those offline.
- **QA tools:** `profile_rehearsal.py --minimized` keeps the rehearsal copy out of the way.
- **QA tools:** `adblock_menu_check.py` drives the menu, its switches, the picker and the zapper offline.
- **QA tools:** `fuzz_lists` feeds changed filter list lines to the engine to check that list reading survives any text.
- **Docs:** README, `ROADMAP.md`, `SECURITY.md` and `CONTRIBUTING.md` describe Thoron; designs live in `docs/design/`.
- **Docs:** build guides cover Windows 11 and Linux with measured build times; `win_env.ps1` prepares a build window.
- **Docs:** `check_docs.py` checks the docs for broken links, house style and private data.
- **Docs:** release program: Thoron versions from 0.1.1, GitHub releases, self-update, one installer, first run.
- **Docs:** the project wiki is written in `docs/wiki/` and published by `publish_wiki.py`.

### Changed

- **Ad blocking:** the built-in blocker is to replace uBlock Origin; an installed uBlock Origin is never touched.
- **Brand:** new icon "Vortex", three turning violet blades around a core, replaces "Radiant Core" everywhere.
- **Install:** the Windows program file is now `thoron.exe` and the installer `thoron_<variant>_mini_installer.exe`.
- **Install:** Thoron no longer shares Thorium's `App Paths` entry; `exe_rename.py` moves an older install over.
- **Build:** work order is Windows first; the Linux build tasks are deferred and Ubuntu stays a target platform.
- **Legal:** more patch sources and tools are credited, and `NOTICE` states that no patent licence is granted.
- **Repository:** renamed to `KuchiSofts/thoron` (old links redirect); the Thorium README moves to `docs/upstream/`.
- **Docs:** the new README has the logo, badges and a roadmap section generated from `ROADMAP.md`.
- **Docs:** house style allows only the plain hyphen; `check_docs` enforces it and validates heading anchors in links.
- **Docs:** README and `SECURITY.md` separate what is in place from what is planned; the design background is neutral.
- **Docs:** this changelog is now one line per change; the roadmap opens with the road to Thoron 0.1.1.
- **Repository:** merged branches are gone and delete themselves; `main` cannot be force-pushed or deleted.
- **Repository:** every push runs the tests and linters and verifies the browser source against upstream.

### Fixed

- **Tools:** the profile rehearsal also sees a profile written a moment ago when the drive's clock runs ahead.
- **Ad blocking:** ads in frames are blocked; a frame's own document was loaded without being checked.
- **Ad blocking:** on a new profile, switches and settings changed before the first list update are kept.
- **Ad blocking:** the menu shows the count blocked on the page in full size again.
- **Ad blocking:** rules for one request method (`method=post`) now apply; every request was checked as a GET.
- **Build:** two small patches fix the Chromium 158 build (FFmpeg duplicate sources, a Rust compiler flag).
- **Build:** `rebase_report.py` no longer reports a patch that changes an upstream overlay file as rejected.
- **QA tools:** `profile_check.py` no longer reports lost tabs for a profile that does not continue where it left off.
- **Docs:** links broken by the house style cleanup work again.

### Removed

- **UI:** Thorium's hidden `chrome://eggs` and `chrome://robot` pages are gone; `chrome://authors` stays.
- **Install:** the installer no longer ships Thorium-named files or content shell entries.
- **Build:** Android-only patches are not carried over to the Chromium 158 series.
- **Repository:** the unused copy of the upstream Thorium M138 tree and the Sponsor button are gone; credits stay.

### Security

- **Ad blocking:** pages the lists name as harmful (malware, phishing) or as ad sites are not opened, as in uBlock Origin; the page shown instead has no scripts and escapes every address.
- **Ad blocking:** a list update is recorded before it is read, so a bad list cannot close the browser at every start.
- **Ad blocking:** only uBlock Origin's own lists may use trusted scriptlets; report-sending `$csp` rules are refused.
- **Ad blocking:** added lists and own rules get no trust, are HTTPS only, and a bad one cannot crash every start.
- **Ad blocking:** the saved engine keeps the rules of trusted lists apart, so no other rule can pass as one.
- **Privacy:** docs name no machine details and use `C:\thoron-build` in examples; `check_docs --private` enforces it.
- **Privacy:** `.gitignore` excludes browser-profile file types (passwords, cookies, sessions, history, keys).
- **Security:** flags that weaken security start with a warning on `chrome://flags`; the unsupported-flag bar is back.
- **Security:** `chrome://authors` uses Chromium's default WebUI security policy and makes no network requests.
- **Security:** extra command-line flags are read only from Thoron's own `thoron-flags.conf`, never from Thorium's file.
- **Security:** every upstream change is audited before merging; `audit_diff` is hardened against crafted diffs.
- **Security:** `crx_id` verifies CRX3 RSA signatures; `compare_release` catches an install with injected executables.
- **Security:** `binary_policy.py` fails on any prebuilt binary without an allowlisted SHA-256, licence and source.
- **Repository:** proprietary and unverifiable binaries are removed (Widevine CDM, Flash Player, prebuilt tools).
- **Repository:** an upstream private signing key for the hangout_services package is removed.
- **Repository:** inappropriate upstream images are purged from git history; an `adult_content` check guards additions.
- **Docs:** `check_docs` detects more user path forms, scans `.py`, `.svg` and `.html` files and checks more link forms.
