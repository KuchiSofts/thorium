# Native ad blocking in Thoron (design, for the owner's approval)

Status: approved by the owner on 2026-11-09 ("do as you recommend"), with the recommendations in section 11.
Changed by the owner on 2026-11-11: the native blocker replaces uBlock Origin instead of working next to it
(section 12, which overrides sections 2 and 3 where they differ).
Extends the main design, section 10 ("Phase 2"), which already named this option. Roadmap: P5.2 (decided),
steps P5.13-P5.28.

## 1. Why

The owner asked for ad blocking that is built into the browser, so it blocks better, faster and
smarter than an extension. Today Thoron ships the genuine uBlock Origin built in: every new profile
installs it from a signed, SHA-256-pinned copy inside the browser. That works, but an extension has
limits:

- **Speed.** Every request is handed to the extension's background page and the network waits for
  its answer.
- **Fragility.** uBlock Origin needs Manifest V2, which Chromium keeps removing; each Chromium
  version needs patches to keep it alive (design 10.1 shows how one 158 change silently broke it).
- **Removable.** A user can disable or remove it, by accident too.

## 2. Goals, non-goals, anti-goals

**Goals**
- G1. Network blocking runs natively inside the browser, before a request leaves it, for every
  profile, always on by default.
- G2. It reads the same filter lists people already trust (EasyList, EasyPrivacy, uBlock filters,
  malware lists), with the same syntax.
- G3. Faster page loads and lower CPU and memory than uBlock Origin alone, measured with
  `tools/qa/bench.py` on ad-heavy local test pages.
- G4. It keeps working on every Chromium version, with no dependency on Manifest V2.
- G5. Per-site switch ("block ads on this site": on/off) in the page info bubble, kept across updates.

**Non-goals**
- ~~Replacing uBlock Origin.~~ Withdrawn on 2026-11-11: the native blocker takes over cosmetic
  filtering and scriptlets too (section 12). What stays true: nobody's installed uBlock Origin or its
  settings are touched.
- Our own filter lists. We use the community lists and credit them.

**Anti-goals (would make this a failure even if it works)**
- Breaking sites people use every day more than uBlock Origin does today.
- Any telemetry, "acceptable ads" programme or paid allow-listing.
- Losing anyone's uBlock Origin settings or custom filters.
- Weakening the sandbox or security releases (security releases always ship first, design G2).

## 3. The hybrid (replaced by section 12 on 2026-11-11)

Kept as the record of the first plan. The measurements in 9.1 showed that both blockers together cost
more than uBlock Origin alone, and the owner chose one built-in blocker.

```
page request ──> [native engine: network filters] ──blocked──> cancelled in the browser
                         │ allowed
                         v
                 [uBlock Origin, if installed: cosmetic filters, scriptlets, its own rules]
```

- The native engine decides on network requests first. A request it blocks never reaches the
  network or the extension.
- uBlock Origin keeps running as today and handles cosmetic filtering and scriptlets. It also still
  sees requests the native engine allowed, so nothing it blocks today gets through.
- If uBlock Origin ever stops working on a new Chromium, network blocking still works (G4).

## 4. Engine choice

| | `adblock-rust` (Brave) | Chromium's `subresource_filter` |
|---|---|---|
| Language, licence | Rust, MPL-2.0 (file-level copyleft, compatible with Thoron's BSD and GPL parts) | C++, BSD-3-Clause (already in the tree) |
| Filter syntax | Full ABP and uBlock network syntax, incl. `$redirect`, `$removeparam`, `$csp`, CNAME uncloaking | A subset (no redirects, no `$removeparam`, limited options) |
| Cosmetic filters | Yes (could replace uBlock's later) | No |
| Production use | Brave, tens of millions of users | Chrome's "abusive ads" intervention |
| Work to integrate | Rust crate plus a small C++ bridge; a few crates to vendor (licence-checked) | Smaller, but the syntax gaps block many uBlock rules |

**Recommendation: `adblock-rust`.** Chromium 158 already builds Rust (`enable_rust = true`) and
already vendors most of its dependencies (`regex`, `memchr`, `aho-corasick`, `serde`, `base64`).
Rust also matters for security: filter lists are untrusted input from the network, and Rust parses
them without memory-safety bugs.

### 4.1 What Chromium 158 already has (checked 2026-11-09)

`adblock` 0.13.5 (`brave/adblock-rust` at `09d297c`, MPL-2.0, Rust edition 2024). Chromium 158's own
Rust toolchain (rustc 1.101 nightly) builds edition 2024.

| Dependency | In Chromium 158 |
|---|---|
| `regex`, `bitflags`, `itertools`, `serde`, `serde_json`, `memchr`, `base64` | vendored (`third_party/rust/chromium_crates_io`) |
| ICU4X crates `idna` relies on (`icu_normalizer`, `icu_properties`, v2) | vendored |
| `flatbuffers` | in `third_party/flatbuffers` (25.9.23; `adblock` asks for 25.12.19: check in the spike) |
| `percent-encoding`, `idna`, `seahash`, `rustc-hash`, `arrayvec`, `thiserror` 1.x | to vendor with Chromium's `gnrt` tool, each licence-checked and credited |
| `addr`/`psl`, `cssparser`, `selectors` | optional features, not needed for network blocking |

### 4.2 Spike measurements (P5.13, 2026-11-09)

`adblock` 0.13.5 built with Chromium 158's Rust toolchain, the filter lists Thoron's bundled uBlock
Origin 1.75.0 ships (EasyList, EasyPrivacy, uBlock filters, privacy, badware, quick fixes, unbreak,
URLhaus: 182,989 lines), and 242,945 recorded real page requests (`adblock-rust`'s `data/requests.json`).
Three runs, spread under 5 %, PC busy with other work. Tool: `tools/qa/adblock_bench`.

| Measure | Native engine | uBlock Origin 1.75.0 on the 158 build |
|---|---|---|
| Ready at browser start | 5 ms (load a saved engine); 95 ms to build from the list text | its own start-up |
| Memory | **9.7 MB** | **110.8 MB** private (its extension process, same lists) |
| Time to check one request | **about 5 µs** (median 3.8 µs, slowest 1 %: about 21 µs) | its own matching plus a hop from the network code to the extension process and back for every request |
| Share of the recorded requests blocked | 43.4 % | (same lists) |

**Verdict: go.** The engine is fast and small, builds with Chromium's own toolchain, and parses the
untrusted lists in Rust. What the hybrid gains first is speed (blocked requests never make the extension
round trip) and blocking that survives Manifest V2's removal. While uBlock Origin keeps running for
cosmetic filtering, its memory stays; the memory saving comes when the native engine also takes over
cosmetic filtering (P5.18). Still to do in the spike: link the engine into a Thoron 158 build and block
a real page (it becomes P5.14's first step).

### 4.3 Building it into Chromium (P5.14, 2026-11-09)

- `adblock` **0.13.3**: Chromium's crate tooling refuses versions younger than 14 days (supply-chain rule), so
  0.13.5 waits.
- Crates come from Chromium's own `gnrt` (vendor, then gen), pinned and checksummed in `Cargo.lock`;
  `tools/build/rust_crates.py` repeats it on Windows (where `gnrt` passes paths git and `gn` reject).
- **`regex` outside tests:** Chromium lists the Rust `regex` crate for tests only and uses RE2 in C++.
  `adblock` always needs it. Thoron allows it (with `aho-corasick`): memory-safe Rust with guaranteed
  linear-time matching, so a hostile list cannot cause catastrophic backtracking. Recorded in
  `gnrt_config.toml` next to the setting.
- Chromium builds C++ without exceptions, so the bridge reports a failed load as an engine whose
  `is_valid()` is false, which blocks nothing.

### 4.4 First in-browser result (P5.14, 2026-11-09)

The engine runs in a Thoron 158 build: `ChromeContentBrowserClient::WillCreateURLLoaderFactory` puts its
proxy first in front of every document, worker and service-worker subresource loader; blocked requests
end with `ERR_BLOCKED_BY_CLIENT`. It is off unless the `ThoronNativeAdblock` feature is on. The lists
(6.9 MB) are taken at build time from the pinned uBlock Origin CRX and shipped next to the browser; the
engine is built from them on a background thread at the first page load.

On the local ad test page of `tools/build/mv2_check.py --native` (offline, fresh profile, no extension),
the engine alone blocked **all 10** ad requests; none reached the server. uBlock Origin on the same page
blocks 9 of 10 (its first request goes out while it starts). Cosmetic filtering stays uBlock Origin's job.

### 4.5 Saved engine shipped with each build (P5.15 step 1, 2026-11-09)

The build now also compiles the lists into a saved engine: a small host tool (`compile_engine`) builds
the engine from the lists, serializes it, checks that the result loads again and writes
`thoron_adblock_engine.dat` (9.6 MB) next to the browser. At start the browser loads this file
instead of parsing 6.9 MB of list text (in the spike, loading a saved engine took 5 ms); if the file is
missing or does not load, it falls back to building from the lists. Both files are in the installer.

Checked: with the lists file removed, the build still blocked all 10 ad requests on the test page, so
the saved engine works alone; with both files present the result is the same; the smoke test passes;
the 154-patch series applies exactly on Chromium 158.0.8127.30. Still to do in P5.15: list updates
(download, validation, and never an "allow everything" state).

### 4.6 Safe list updates (P5.15 step 2, 2026-11-09)

The browser now keeps the lists current (only with the feature on). Two minutes after start, and then
every hour, it looks whether the last check is more than 4 days old; if so it downloads the 8 lists from
the addresses uBlock Origin uses (`docs/security/NETWORK.md`), each with one fallback host, over HTTPS
only, without cookies or other credentials, through the browser's own network context. Each download
is checked on its own and keeps the previous copy (the last accepted download, else the shipped one)
when it:

- is larger than 20 MB, is not UTF-8 text, or is a web page (for example a Wi-Fi sign-in page);
- has no rules, or fewer than half the rules of the copy it would replace;
- holds an exception that allows every request (`@@*`, `@@||^`, `@@|http` and the like, with no site
  limit): no real list has one (checked against all 18 shipped and current lists).

A new engine is built only when at least one list changed, and it must still block each of six probe
requests (well-known ad and tracker scripts) that the current engine blocks; otherwise the whole update
is refused. Accepted lists, the saved engine and a small `state.json` (version, time of the last check,
per list: where it came from, its rule count and what happened) are written atomically to
`<user data dir>/Thoron Adblock/`, the state last, and the engine is swapped in at once. At the next
start the saved engine is used when this browser version wrote it; after a browser update the shipped
engine is used until the next check. Profiles and browsing data are never touched.

Tested offline with `tools/qa/adblock_update_check.py` (a local list server, throwaway profiles, the
browser accepts a test list address only on loopback): a good update is used within about 2 seconds and
blocks a new test host; after a restart the saved engine blocks it from the first request with no
download; a shrunken list, a list with `@@*`, a web page instead of a list, and an update that drops
every rule for the probe requests are all refused and the previous engine stays. Observation for P5.17:
the current URLhaus list has about 101,000 rules against 9,300 in the shipped copy, so the engine's
memory after an update must be measured.

### 4.7 Per-site switch (P5.16 step 1, 2026-11-09)

Decision (the builder's call, inside approved goal G5): the switch is Chromium's existing per-site
"Ads" content setting, not a new one. "Allow" on a site means "show ads here", which is exactly what
turning the blocker off for a site means, and it brings for free what a new setting would have to
build: storage in the profile with the person's other site settings (so it survives restarts, browser
updates and the move from Thorium), the row on every site's page in Settings > Site settings, the
"Allowed to show ads" list, and enterprise policy. "Allow" as the default turns native blocking off
everywhere. Chromium's own abusive-ads filter reads the same setting, so the two stay consistent.

- The proxy is inserted only when the top-level site (from the factory's isolation info) is not set to
  "Allow"; the check is made once per document or worker, so it costs nothing per request, and a
  changed setting applies from the next load (page info asks for a reload).
- Page info shows the Ads row on every site while native blocking is on (upstream shows it only after
  Chromium's abusive-ads filter acted on the site).

Tested offline with `tools/qa/adblock_site_switch_check.py`, which makes the choice through the
Settings page's own handlers: with no choice all 10 ad requests are blocked; ads allowed on the test
site, or allowed by default, let all 10 through; after a normal browser exit and a new start the choice
is kept and all 10 still load.

Labels (step 2): while native blocking is on, page info and Settings call the setting "Ads and trackers"
and say what it does ("Block ads and trackers" / "Sites can show ads and use trackers", with a short
description and the two site lists named to match); with it off, upstream's "Intrusive ads" wording stays,
because then the setting only controls Chromium's abusive-ads filter. The new English strings have no
translations yet, so other languages show them in English. The check above also reads the Settings page
and fails on upstream's wording.

Blocked count (step 3): each blocked request is counted for its page (the page and all its frames) in
`blocked_count.cc`, as data attached to the page. The count lives only in memory and goes away with the
page: nothing is written to disk and nothing is sent, and no URL is kept or logged. The first blocked
request also marks the page as having blocked ads, which shows Chromium's blocked-ads icon in the address
bar (tooltip "Ads and trackers blocked"). Its bubble says how many ads and trackers were blocked on the
page and has one checkbox, "Always allow ads and trackers on this site", which sets the per-site Ads
setting and reloads the page. Upstream's "Learn more" link is hidden there while native blocking is on,
because it explains Chromium's abusive-ads filter. With the feature off the icon and bubble are
upstream's. The check above reads the page's count from the browser's verbose log
(`--vmodule=blocked_count=1`, the number only) and fails if it is lower than the number of blocked ad
requests: 10 blocked, count 10.

Seen in a desktop window (2026-11-09, throwaway profile, offline test page, read through Windows UI
Automation): the icon appears in the address bar with the label "Ads and trackers blocked"; its bubble
reads "10 ads and trackers blocked on this page", the text above, and the checkbox, with no "Learn more"
link. That look found one fault, fixed in the same step: the icon's label (also its accessible name) still
said upstream's "Ads blocked", because only the tooltip had been changed.

The page info row was read the same way: it is named "Ads and trackers" and shows its state ("Not allowed
(default)" while blocking is on). That look found a second fault, also fixed: the line under the row still
said upstream's "Site shows intrusive or misleading ads", which reads as a warning about the site when the
row is only there because Thoron's blocker is on. It now says "Thoron blocks them unless you allow them on
this site", which is true whether the row is on or off.

Changed after the first proof measurement (section 9.1): the icon no longer has upstream's expanding
label. Upstream shows it only on the rare site its abusive-ads filter acts on; with native blocking the
icon shows on most pages, and animating the label on each load took about 2-3 s of extra browser and GPU
CPU per page load in the measurement (and draws the eye for no reason). The icon, its tooltip and its
accessible name ("Ads and trackers blocked") stay; the bubble is unchanged.

Still to do: translations of the new strings. The bubble's checkbox and the page info toggle were read, not
clicked (the setting they write is the one the check above covers).

Crash record (added 2026-11-11). Reading a list runs the Rust parser inside the browser process, and in
Chromium a Rust panic ends the process. The check was only put on record after the new lists had been
read, so a list that made the parser abort would have ended the browser 2 minutes after every start, for
as long as the list host served it. Now the check is recorded first, with the result "interrupted", and
the final result replaces it; after an abort the next attempt is 4 days away and the previous engine stays
in use. `tools/qa/adblock_update_check.py` tests it by serving a valid but very long list and killing the
browser the moment the record appears: the record is there, and the next start downloads nothing, keeps
the previous engine and stays up (8 scenarios pass). Not done: a fuzz run of the parser itself (P5.17).

## 5. Where it plugs in

- **Engine host:** one engine per browser (not per profile), built from the compiled lists, shared
  read-only, so 10 profiles do not cost 10 engines.
- **Request check:** a `URLLoaderThrottle` (or the network service's request hook) asks the engine
  for each subresource request: URL, top-level site, resource type, third-party flag. Blocked
  requests are cancelled with `ERR_BLOCKED_BY_CLIENT`, as extensions do today. As built, a proxying
  URLLoaderFactory sits in front of each page's, worker's and service worker's subresource factory, and
  in front of the navigation factory of frames inside a page (only the frame's document is checked; a
  top-level navigation never is).
- **Redirect resources** (`$redirect=noop.js` and similar) come from a small bundled set of neutral
  stand-ins, the same idea uBlock Origin uses.
- **CNAME uncloaking:** use Chromium's DNS results to also match the real host behind a tracker's
  CNAME (extensions cannot do this on Chromium).
- **Per-site switch:** Chromium's own per-site "Ads" content setting (section 4.7), in the page info
  bubble and in Settings; stored in the profile like other site settings.

## 6. Filter lists and updates

- **Default lists:** EasyList, EasyPrivacy, uBlock filters, uBlock privacy, Peter Lowe's list and a
  malware domain list. Each has its own licence (EasyList: CC BY-SA 3.0 or GPL-3.0; uBlock filters:
  GPL-3.0); all are credited in `CREDITS.md` and `chrome://credits`.
- **Updates:** downloaded from their published URLs like uBlock Origin does today, at most every 4
  days, over HTTPS only. A compiled copy of known-good lists ships with each release, so a fresh
  install blocks from the first page with no download at all.
- **Validation:** a downloaded list is checked and compiled in a background step; if it is too large,
  not a list, empty, shrinks by more than half or allows every request, its previous copy stays, and a
  new engine that stops blocking known ads is refused whole (no "everything allowed" state; section 4.6).
- **Privacy:** list downloads send no identifiers or cookies, and the hosts are listed in
  `docs/security/NETWORK.md`.

## 7. Settings and people's data

- uBlock Origin's settings and custom filters are never touched; it keeps running for existing and new
  profiles.
- The native engine's state is only "on/off" and the per-site switches, stored in the profile and
  covered by the profile check and backups like everything else.
- A setting "Advanced: also use custom filter lists" can come later; not in the first version.

## 8. Security

- Filter parsing runs in Rust; lists are untrusted input and are size-limited (for example 20 MB per
  list) before parsing.
- No new process gets more privilege; the engine runs where the request decision is made, without
  new IPC that a renderer could abuse to query browsing history of other sites.
- Fuzz the list parser and the request matcher (Chromium's fuzzing setup) before it ships on by
  default.

## 9. Proof that it is better (measured, not claimed)

Before it is turned on by default, with `tools/qa/bench.py` and new ad-heavy local test pages (copies
of typical news and recipe page structures with ad and tracker requests, served on 127.0.0.1):

| Measure | Target |
|---|---|
| Ads and trackers blocked on the test pages | at least as many as uBlock Origin alone |
| Page load time on the test pages | at least 10 % faster than uBlock Origin alone |
| Browser CPU during load | lower than uBlock Origin alone |
| Memory, 1 and 20 tabs | not more than uBlock Origin alone |
| Breakage | the top-100 site list loads with no new breakage compared with uBlock Origin alone |

### 9.1 First measurement (P5.17, 2026-11-10, offline part)

`tools/qa/adblock_proof.py` loads three ad-heavy local test pages (news, recipe and blog structures: 48 ad and
tracker requests in all, some added by the ad scripts themselves as real ones do, plus third-party libraries,
fonts and images a page needs) in four configurations on fresh throwaway profiles: no blocker, uBlock Origin
1.75 alone, the native engine alone, and both. It is fully offline: the real ad and tracker host names are sent
to a local server, every other name fails, and each answer from those hosts is held back 40 ms to stand in for
the network. Before measuring, each blocker must be seen blocking and the browser must be idle; the no-blocker
run must receive every request, or the whole measurement is invalid. Results:
`docs/perf/2026-11-10-native-adblock-proof.md` (9 loads per page, 3 memory runs).

| Configuration | Through (of 48) | Load, ms | CPU, s per load | Memory 1 / 20 tabs, MB |
|---|---|---|---|---|
| no blocker | 48 | 533.9 | 0.497 | 344.4 / 809.9 |
| uBlock Origin alone | 0 | 366.6 | 0.341 | 385.1 / 840.1 |
| native alone | 0 | 345.7 | 0.317 | 356.7 / 753.7 |
| native + uBlock Origin | 0 | 434.9 | 0.383 | 395.1 / 837.4 |

- **Native alone** meets every target but one: it blocks as much as uBlock Origin (everything) with no
  needed resource blocked, uses less CPU and less memory (29 MB less with 1 tab, 86 MB less with 20), and
  loads 5.7 % faster, short of the 10 % target. Offline, both blockers stop the same requests before they
  leave the browser, so the load difference is only each blocker's own overhead; whether the 10 % shows up
  on a real connection is not measured yet.
- **Native + uBlock Origin**, the planned shipping set-up (section 3), misses load time, CPU and 1-tab memory:
  with both running, uBlock Origin still does its own network filtering (section 3: it "still sees requests
  the native engine allowed"), so its cost stays and the native engine's is added. Its load times also varied the most (worst spread 118 %). The gain the design expects
  needs uBlock Origin's network filtering turned off when the native engine is on, or uBlock Origin's role
  limited to cosmetic filtering; that is a decision for P5.17 before anything is turned on by default.
- Two faults were found and fixed by this measurement: ads in frames were not blocked (the frame's own
  document is loaded as a navigation, which the engine did not see; it now checks the documents of frames
  inside a page, never a top-level navigation, and a top-level visit to an ad host was checked to still load);
  and the expanding label of the address bar icon (section 4.7).
- Not covered yet: the top-100 breakage check, real-network load times, fuzzing, and a run on an idle PC (the
  load times here vary by up to 58 % for native alone, more than the 10 % being measured).

Second measurement (2026-11-11), with a fairer method: the pages are loaded in turn instead of one page
many times in a row, after 3 unmeasured rounds, 15 timed loads per page
(`docs/perf/2026-11-11-native-adblock-proof.md`). The first run had measured some configurations while
they were still warming up; its load time for "native + uBlock Origin" (434.9 ms) came from slow first
loads and should not be relied on. Its memory figure for that set-up stands (about 10 MB more than uBlock
Origin alone, the size of the engine).

| Configuration | Through (of 48) | Load, ms | CPU, s per load | Memory 1 / 20 tabs, MB |
|---|---|---|---|---|
| no blocker | 48 | 474.6 | 0.341 | 354.1 / 831.4 |
| uBlock Origin alone | 0 | 343.4 | 0.316 | 380.9 / 859.2 |
| native alone | 0 | 323.4 | 0.289 | 344.8 / 738.1 |

Native alone against uBlock Origin alone: the same blocking, 5.8 % faster loads (per page 4 % to 8 %), 8.5 %
less CPU, 36 MB less memory with 1 tab and 121 MB less with 20. The load-time target of 10 % is not met
on these pages, twice now with the same result. Both blockers stop the same requests here, so what is
left to gain is only each blocker's own overhead, about 7 ms per page. Whether the target is the right one
is the owner's call; a measurement on a real connection is still open. These numbers are from before the
native blocker does cosmetic filtering and scriptlets (section 12), which will add work; the measurement
is repeated when they are in.

Measured in turns (2026-11-11, evening). The tool used to measure one configuration from start to end
before the next. On a desktop that is also used for other things that is not a fair comparison: if the
machine gets busier half way, only the later configurations pay, and the same build gave the native
blocker 10.2 % in one run and 8.6 % in the next. `tools/qa/adblock_proof.py --turns N` now starts all
browsers first and takes the measured loads in N turns, one configuration after the other in each turn
(a different one first each time), counting each turn's CPU on its own. With three turns, on the build
with everything up to P5.25 (`docs/perf/2026-11-11-native-adblock-proof-turns.md`):

| | Control | uBlock Origin | Native |
|---|---|---|---|
| Ads and trackers through (of 48) | 48 | 0 | 0 |
| Load, ms | 471.9 | 348.6 | 327.5 |
| CPU, s per load | 0.339 | 0.354 | 0.300 |
| Memory, 1 / 20 tabs, MB | 352.9 / 822.6 | 393.1 / 846.2 | 354.7 / 770.3 |

The native blocker loads the test pages 6.1 % faster than uBlock Origin, with 15 % less CPU and 38 to
76 MB less memory. That agrees with the quiet morning runs (6.5 %, 15 %) and not with the 10.2 % of the
afternoon. The 10 % load target is not met. Later comparisons should use `--turns`.

### 9.2 Breakage on popular sites (P5.17, 2026-11-11)

`tools/qa/adblock_breakage.py` loads real sites: 99 of the first 100 domains of the Tranco research ranking
(list Y895G, 2026-11-10) whose home page is a real page on the same site (`tools/qa/sites/`; one is left out
because the repository's content rules do not allow its name). Each is loaded with
uBlock Origin alone, the native engine alone, and both, in throwaway profiles. A site is flagged when a
configuration does worse than uBlock Origin alone (did not load, a first-party request blocked that uBlock
Origin let through, clearly more script errors, clearly less text), and only if a second load repeats it.
Results: `docs/perf/2026-11-11-native-adblock-breakage.md`.

- 97 sites could be compared (2 did not load with uBlock Origin either). With the native engine alone all
  97 loaded; none lost text and none threw more script errors.
- 4 sites were flagged, all for first-party tracking requests: apple.com (Adobe Analytics), cnn.com (the
  Adobe Launch tag script), vk.com (a CSP report address), applovin.com (an ad script). On apple.com and
  cnn.com uBlock Origin does not let these through either: its lists answer them with a harmless stand-in
  (`redirect=1x1.gif`, `redirect-rule=noopjs`), which the native engine could not do yet and blocked
  outright. That is the first piece of section 12.
- The native engine blocked more requests in all (831 against 716), partly for the same reason: a request
  uBlock Origin answers with a stand-in does not count as blocked.
- Limits: home pages only, no sign-in, no clicking, one location, headless. It finds pages that fail to
  load, not a menu that stops working. Flags are leads to check by hand.
- After stand-ins were added (P5.19, section 12.2) the four flagged sites were loaded again: apple.com and
  cnn.com are no longer flagged. vk.com (a CSP report address) and applovin.com (an ad script) still
  differ; applovin.com also serves the two set-ups pages of different length, so it is a weak comparison.
- With scriptlets and hide rules in (P5.20, P5.21) the 99 sites were loaded again, since those are the
  changes most likely to break a page (`docs/perf/2026-11-11-native-adblock-breakage-p521.md`): 96 could be
  compared, all 96 load with the native blocker, none is flagged for lost text or script errors, and the
  only two flags are the same two tracking requests on vk.com and applovin.com. One caution when reading
  the text counts: uBlock Origin does not hide elements in a headless browser on this build (P2.18), the
  native blocker does, so a page can show a little less text with it (ibm.com: 12 % less) because ad and
  promotion blocks are hidden. Clicking through pages is still not covered.
- With procedural rules, `$removeparam` and `$csp` in (P5.22) the 99 sites were loaded once more
  (`docs/perf/2026-11-11-native-adblock-breakage-p522.md`): 97 could be compared, the only two flags are
  the same two tracking requests on vk.com and applovin.com, and no site shows less than 80 % of the text
  it shows with uBlock Origin. One site, instagram.com, did not load with the native blocker on the first
  try and did on the second, which is why it is not flagged. Loaded twice more with both blockers, it
  loaded with both once (the same text) and with neither once: the site is unsteady in this harness, with
  either blocker. launchpad.net loaded with neither that afternoon.
- One thing learned on the way: starting the browser with `--user-agent` stops uBlock Origin from blocking
  anything on this build, so the tool sets the user agent per tab instead.

## 10. Steps (roadmap P5.13-P5.28)

1. **P5.13 Spike (throwaway):** link `adblock-rust` into a 158 build, block with a hard-coded EasyList,
   measure. Decides go or no-go.
2. **P5.14 Engine:** vendored crates (licence-checked, credited), C++ bridge, request
   throttle, `ERR_BLOCKED_BY_CLIENT`, redirect resources, tests.
3. **P5.15 Lists:** bundled compiled lists in each release, safe background updates, validation.
4. **P5.16 UI:** per-site switch in page info and Settings; a blocked-count badge (local only).
5. **P5.17 Proof:** the measurements of section 9; fuzzing; on by default only when all targets pass.
6. **P5.18 Later:** CNAME uncloaking.
7. **P5.19-P5.28:** the native blocker takes over the rest of uBlock Origin's work (section 12.8).

## 11. Decisions (approved 2026-11-09)

1. Approve the hybrid (native network blocking, uBlock Origin kept for cosmetics and its own rules).
2. Approve `adblock-rust` (MPL-2.0) as the engine.
3. Approve the default lists in section 6.
4. Native blocking on by default for everyone once section 9's targets pass (with the per-site switch
   to turn it off).

## 12. Native only (the owner's decision, 2026-11-11)

Section 9.1 ended with a question: what should uBlock Origin do when the native engine is on, since both
together cost more than uBlock Origin alone? The owner's answer: skip uBlock Origin. Ad blocking is to be
built into the browser, it must still be able to update its scripts and block lists, and it should be
smart. This replaces the hybrid of section 3 and decision 1 of section 11.

### 12.1 What the native blocker takes over

| uBlock Origin does | Native piece | Step |
|---|---|---|
| Network blocking, frames included | the engine and request proxy (4.3-4.6) | done |
| Stand-ins (`$redirect`, `redirect-rule`): a blocked script or image is answered with a harmless copy, so the page does not break | resources from the pinned uBlock Origin package; the proxy answers with the stand-in | done (P5.19) |
| Scriptlets (`##+js(...)`): small scripts that defuse ad and anti-blocker code inside the page | the same resources, run at document start | done (P5.20) |
| Cosmetic filtering for one site (`example.com##.ad`) | a style sheet sent with the document | done (P5.20) |
| Generic cosmetic filtering (`##.ad-banner`) | the page reports the classes and ids it uses; the engine answers with the selectors to hide | done (P5.21) |
| Procedural cosmetic filters (`:has-text()`, `:upward()`), `$removeparam`, `$csp` | a small page-side runner; a clean address (an internal redirect for documents); a policy on the document's response | done (P5.22, section 12.9) |
| A redirected request checked again at each hop | a watcher on every request; an interceptor on every navigation | done (P5.25, section 12.10) |
| The scripts workers and service workers are started from | the request proxy sits in front of those loaders too | done (P5.27, section 12.11) |
| `$urlskip`, `$replace`, `$header`, `$uritransform`, `$permissions`, `:shadow()` | see 12.9 | P5.26 |
| List updates | 4.6 | done |
| Scriptlet and resource updates | 12.4 | P5.23 |
| Per-site switch, blocked count | 4.7 | done |
| Element picker, custom filters | 12.6 | later |

### 12.2 Resources: scriptlets and stand-ins

Source: the pinned, SHA-256-checked uBlock Origin package the build already downloads, the same one the
lists come from, so lists and scriptlets always match. A build step (`extract_resources.py`, which runs
`assemble_resources.mjs` with the build's own Node.js) unpacks the scriptlet modules and the redirect
resources and writes them as `thoron_adblock_resources.json` next to the browser. For uBlock Origin 1.75.0
that is 98 scriptlets, 53 helper functions and 47 redirect resources. The engine loads the file at start;
the saved engine does not hold resources.

Trust: uBlock Origin marks 34 of them as needing trust (they can set cookies, click elements or rewrite
responses) and lets only its own lists use them. Thoron keeps that rule: those resources carry a permission
bit, and only the lists whose id starts with `ublock-` are parsed with it. EasyList, EasyPrivacy and the
malware list cannot use them.

Stand-ins as built (P5.19, 2026-11-11): the engine's answer for a request is now "allow", "block", or
"block and answer with this stand-in". For the last one the request proxy sends the page a finished 200
response holding the stand-in (an empty script, a 1x1 image, an empty document for a frame), marked as the
network would have marked a real answer (same-site, CORS or opaque), and nothing reaches the network. A
`redirect-rule` filter only supplies its stand-in when another filter blocks the request. Checked:
- 16 engine tests, among them the stand-in rules, a list that is not allowed trusted scriptlets, and a
  saved engine that keeps its rules' trust but needs its resources given again;
- on the offline test pages (`tools/qa/adblock_proof.py`, which now tells a stand-in from a real load and
  from a block) the native engine answers the same 12 blocked scripts with stand-ins as uBlock Origin,
  with nothing let through and nothing needed blocked;
- the page's blocked count includes requests answered with a stand-in
  (`tools/qa/adblock_site_switch_check.py`: 10 stand-ins, count 10).

### 12.3 In the page

- When a document's navigation is ready to commit, the browser asks the engine what that document needs
  (its hide selectors, its scriptlets, its exceptions) and sends it to the renderer on a channel-associated
  interface, the way Chromium's own subresource filter activates a document. The renderer adds the style
  sheet and runs the script at document start, before any page script.
- Nothing is injected on a site where the person turned blocking off, on `chrome://` pages or on
  extension pages.
- Generic hiding: a small script in an isolated world collects class names and ids as the page builds
  (in batches) and asks the browser for the matching selectors.
- Scriptlets run in the page's own world, as uBlock Origin's do. They are the same code, so a site cannot
  tell Thoron's blocker from uBlock Origin by them.

As built (P5.20, 2026-11-11):
- Browser: one observer per WebContents (attached with Chromium's other universal observers, only while
  the feature is on). At `ReadyToCommitNavigation` of an http(s) document, in the page or in a frame, it
  reads the per-site switch for the page, asks the engine, and sends a style sheet and a script on the
  frame's channel-associated `DocumentAgent` interface. Nothing is sent for error pages, same-document
  navigations, other schemes, or a site where the person allowed ads.
- Renderer: a frame agent keeps what arrived for the document that commits next, and applies it when the
  embedder runs its document-start scripts: the style sheet as a user style sheet (the page's own styles
  cannot take it back), the script in the page's world. A document the browser sent nothing for gets
  nothing; what was sent for an earlier navigation never carries over.
- The script: the site's scriptlets inside one function with a shared `scriptletGlobals`, as uBlock Origin
  runs them, so their helper functions stay out of the page's global scope.
- The style sheet: one `selector{display:none!important}` rule per line. A selector that holds a brace, an
  open comment or a control character is left out, so a list can hide elements but never add other CSS
  to a page (adblock-rust is built without its optional CSS validation).
- Besides a site's own rules the engine returns the generic rules that cannot be looked up by class or
  id (uBlock Origin's "highly generic" set): 546 selectors, about 22 KB, for every document that has no
  `generichide` exception. Rules that can be looked up by class or id are P5.21.
- Checked with `tools/qa/adblock_cosmetic_check.py`, which picks a site from the bundled lists that has
  both a simple scriptlet rule and a simple hide rule and serves a page under its name from a local
  server: with blocking on, the scriptlet ran before the page's first script and the element is hidden,
  in the page and inside a frame; with blocking off, or ads allowed on that site, nothing is touched.
  17 engine tests cover the rest (trust per list, the selector check, the wrapper).
- Cost: the measurement of 9.1 was repeated with stand-ins, scriptlets and hide rules in
  (`docs/perf/2026-11-11-native-adblock-proof-p520.md`): the native blocker loads the test pages 7.6 %
  faster than uBlock Origin (306.9 against 332.3 ms; 5.8 % before), with 28 % less CPU per load and 80 to
  90 MB less memory. The added work does not show; the 10 % load target is still not met.
- Known differences from uBlock Origin: 22 of its scriptlets ask for an isolated world and run in the
  page's world here; `war:` arguments (a scriptlet answering a fetch with one of the extension's files)
  resolve to nothing; frames that never navigate (`about:blank`, `srcdoc`) get nothing. (Procedural
  filters came with P5.22: section 12.9.)

Generic hide rules as built (P5.21, 2026-11-11). The lists hold about 13,000 rules of the form
`##.ad-banner` or `###ad-top`. Sending them all to every page would cost every page; instead:
- The frame agent walks its document and collects the class names and ids it has not reported yet: when
  the DOM is ready, at load, and 1, 3, 7 and 15 seconds after load for content the page adds late. It
  sends them to the browser (at most 4,000 names per question, 40,000 per document, names up to 128
  characters) and inserts the style sheet that comes back as a user style sheet.
- The browser answers through a per-frame `DocumentHost` interface. It decides by the address the asking
  frame has committed and the page it is in, never by anything the frame says about itself: the site's
  exceptions are applied, a `generichide` exception or ads allowed on the site means no answer, and a
  question with more than 8,000 names is not answered.
- A rule stays in force once inserted, so elements that arrive later with an already reported class are
  hidden at once. What is missed: a class name that first appears more than 15 seconds after load. A
  mutation observer would catch those and is left for later, if the breakage and blocking checks ask for it.
- Checked with `tools/qa/adblock_cosmetic_check.py`: an element with a generic rule's class that is there
  from the start and one the page adds a second after load are both hidden, in the page and in a frame,
  and neither is with blocking off or ads allowed on the site.
- Cost: none that the measurement shows. With generic rules in, the test pages load in 306.8 ms (306.9
  before), 6.5 % faster than uBlock Origin (328.2 ms), with 15 % less CPU per load and 45 to 101 MB less
  memory (`docs/perf/2026-11-11-native-adblock-proof-p521.md`).

### 12.4 Updates

- Lists: as today (4.6): every 4 days, from the list hosts, each list checked, never a fallback to
  "allow everything".
- Scriptlets and resources are code that runs inside every page, so they are never fetched from a list
  host or any other third party while the browser runs. They ship with each Thoron release, built from
  the pinned package. Once the updater exists (P3) they can also arrive between releases as a small data
  update: built by Thoron's release process from a newer pinned uBlock Origin, signed with the release
  key, checked before use, with the shipped copy as the fallback.
- A filter that names a scriptlet the installed resources do not have is ignored, as in uBlock Origin.

### 12.5 uBlock Origin itself

- Existing profiles: nothing is removed or changed. A profile that has uBlock Origin keeps it, with its
  settings and custom filters.
- New profiles: once native blocking is on by default, the built-in uBlock Origin is no longer installed
  into new profiles. Open: the owner confirms this when the default changes; until then nothing changes.
- A person who runs both gets double filtering. Settings will say so, once, with a button to turn one of
  them off. Nothing is turned off silently.

### 12.6 Smart, beyond parity (in order of value)

1. CNAME uncloaking (P5.18): match the real host behind a first-party alias, which no extension can do
   on Chromium.
2. A short "what was blocked on this page" list in the bubble, kept in memory only.
3. Custom filters and an element picker in Settings.
4. A one-click "this site is broken" that turns blocking off for the site and keeps the reason on the PC.

### 12.7 Security review of the change

- Scriptlets are the sensitive part: code injected into pages. Their source is pinned by SHA-256 and
  converted at build time; nothing is fetched from third parties at run time; updates must be signed; and
  the powerful scriptlets are limited to uBlock Origin's own lists.
- A list update can choose which of the installed scriptlets runs on which site, with which arguments.
  The lists have the same power in uBlock Origin. The checks of 4.6 and the trust rule limit it, and the
  list hosts are reached over HTTPS only.
- A renderer receives only what its own document needs and cannot ask the browser about other sites. The
  one question it can ask (generic hide rules for class names and ids) is answered by the address the
  frame has committed, is bounded in size, and its answer holds only public list rules, nothing about
  the person or other pages.
- The build runs the package's scriptlet modules once with Node.js to read them. Importing them only
  registers functions, and the package is the pinned one.
- Licence: uBlock Origin's scriptlets and resources are GPL-3.0. They ship unmodified in their own data
  file, with their licence and source named in `CREDITS.md` and `NOTICE`, as the bundled uBlock Origin
  package already is. To be confirmed in the licence inventory (L.1).

Added with P5.22 (procedural rules, `$removeparam`, `$csp`):
- The procedural runner is Thoron's own code and runs in an isolated world, so a page cannot replace the
  DOM functions it uses. It gets its rules as data (JSON, with `<` escaped); nothing from a list is ever
  run as code. A list can make it slow with a costly regular expression or XPath, on the site the rule
  names, as it can in uBlock Origin; the runner limits how often it looks, not how long one look takes.
- A list cannot put the runner on every page: a procedural rule without a site is not applied (12.9).
- The marks it puts on elements are attribute names of 12 random letters, new for every document: a page
  cannot know them beforehand or recognise the blocker by them. A page can still see that an attribute
  appeared, as with uBlock Origin.
- `:style()` declarations go into a user style sheet only if they cannot leave their rule and cannot make
  the page fetch anything (`url(`, `image-set(` and the like are refused, as in uBlock Origin).
- `:remove-attr()` can take any attribute off an element of the site its rule names, a frame's `sandbox`
  included. uBlock Origin gives every list the same power; it is recorded here, not limited.
- `$removeparam` can only make a query shorter. The browser checks what the engine returns: scheme, host,
  port, path, user info and fragment must be the request's own, or the address is not used.
- `$csp` can only take permissions away from a page. adblock-rust lets a rule through whose policy tells
  the page to send reports somewhere (`report-uri`, `report-to`), which a list could use to learn what
  people load; uBlock Origin refuses such rules and so does Thoron. Only the lists' own policy text is
  parsed in the browser process (plain ASCII, at most 4,096 bytes); the site's headers stay as the network
  service parsed them.
- The throttle that does this sees every document request and holds no state beyond the request.

Added with P5.25 (redirects):
- The redirect watcher passes a request's messages on unchanged, both ways. What the renderer sends when
  it follows a redirect is still checked by the network service as coming from that renderer: the
  request's factory keeps the renderer's process id, whoever relays the message.
- The only thing the watcher changes is a redirect's target, and only to the same address with a
  shorter query (the same check as for a request's first address). The network service would refuse a
  target of another origin or one with a user name or password; such a target is left as it is.
- The navigation interceptor answers a request itself in two cases only: an internal redirect to the
  same address with a shorter query, and the refusal of a frame the lists block. A site cannot use it
  to keep a navigation going in circles: an address is cleaned once per navigation.
- Both decide with the engine on the UI thread, by the document that asked, as the request proxy does.

Added with P5.27 (worker scripts):
- The scripts workers and service workers start from are judged like any other request. Whether ads are
  allowed is read for the page of the document that starts a worker, and for a service worker's own site
  (it has no page). A service worker's script is its code for every later visit, so blocking an import
  there matters more than blocking one request: it keeps a third party's code out of the site's service
  worker.

### 12.8 Steps

- **P5.19** resources and stand-ins.
- **P5.20** scriptlets and site-specific cosmetic filtering.
- **P5.21** generic cosmetic filtering.
- **P5.22** procedural filters, `$removeparam`, `$csp`.
- **P5.23** signed resource updates (with the updater, P3).
- **P5.24** the hand-over from uBlock Origin (new profiles; the notice when both run).
- **P5.25** a redirected request is checked again at each hop (found while building P5.22; done, 12.10).
- **P5.27** the kinds of request that did not pass the request proxy at all (done, 12.11).
- **P5.28** preloads announced by early hints, which Chromium offers to nobody (12.11).
- **P5.26** the filter syntax still missing after P5.22 (section 12.9).
- **P5.18** stays CNAME uncloaking. **P5.17**'s targets now compare the native blocker alone with
  uBlock Origin alone.

### 12.9 The rest of the syntax (P5.22, 2026-11-11)

What the bundled lists use (counted, uBlock Origin 1.75.0's lists): of about 32,400 hide rules, about 800
need more than CSS (`:has-text()` 533 times, then `:has()` around an operator, `:upward()`, `:others()`,
`:xpath()`, `:matches-css()` and others); 715 rules restyle with `:style()`, about 180 remove an element,
an attribute or a class. 260 rules use `$removeparam` (244 name one parameter, 10 give a pattern, 5 give
nothing and mean every parameter, 1 names a parameter that is a path) and 6 are exceptions to it. About
90 rules use `$csp`.

Procedural hide rules.
- adblock-rust is built here without its CSS parser (it would add two more vendored crates and their
  dependencies), so it hands a rule's selector over as one string. `procedural.rs` splits it into plain
  CSS and a list of tasks, and refuses what cannot be run. A selector without an operator stays CSS
  (`:-abp-has()` becomes `:has()`). Of the lists' hide rules, all but two compile; the two use `:shadow()`.
- Operators: `has-text` (also written `-abp-contains` and `contains`), `upward`, `xpath`, `matches-css`,
  `matches-css-before`, `matches-css-after`, `matches-attr`, `matches-path`, `matches-media`,
  `min-text-length`, `others`, `watch-attr`, `has` and `not` around another procedural selector, and CSS
  that continues after an operator. Not built: `shadow` (2 rules), `matches-prop` (none).
- A procedural rule must name a site, as in uBlock Origin. adblock-rust would accept one written for
  every site (`##div:has-text(Ad)`), and it would then put the runner, and the rule's cost, on every
  page. Such rules are found once per engine (by asking it about a site no list names) and never
  applied. The bundled lists have none.
- Actions: no action hides; `:style(...)`; `:remove()`; `:remove-attr(...)`; `:remove-class(...)`. A
  `:style()` rule with a plain CSS selector is CSS in the document's style sheet and needs no runner.
- The runner (`procedural.js`, about 8 KB, Thoron's own code) is sent only to a document that has such
  rules, with the rules as data, and runs in an isolated world of its own at document start. It marks
  what a rule finds with an attribute; the document's style sheet says what a mark means (hidden, or the
  rule's style). It looks when the DOM is ready and again when the page changes, waiting ten times as
  long as the last look took (at least 50 ms, at most 5 s). An element a rule no longer describes loses
  its mark.

`$removeparam`.
- adblock-rust applies `$removeparam=name` and reports the clean address with its answer for a request.
  It drops the other forms when it reads a list. `query.rs` finds them: no value (every parameter goes),
  a pattern, and exceptions (for everything, or for one parameter). Each kind is rewritten into rules
  adblock-rust can match and kept in a small engine of its own; one first question ("does any of them
  match?") keeps the cost for ordinary requests at one extra lookup. Patterns are not run as regular
  expressions: the shapes the lists use (one word or several, with or without `^`, a group and `\b`:
  `^ad`, `^(cookie|ga_|u_)`, `web_only=`) are matched by a few lines of code, so no pattern from a list
  can make matching slow. That covers 8 of the 10 pattern rules; the other two use a lookahead and are
  not applied, nor is the one rule whose parameter name is a path. These rules are saved with the
  engine, which has a header of its own now; a saved engine of another layout is refused and built
  again from the lists.
- As in uBlock Origin, a rule without a request type applies to documents, frames and fetches.
- A document's own request (a page, or a frame in one) is cleaned before it goes out: the changed
  address becomes an internal redirect, so the address bar, the history and the page's own scripts see
  the clean address, and the server never sees the parameter. Every other request is sent out with the
  clean address without telling the page. (Built first as a loader throttle; since P5.25 a navigation
  interceptor does it, at the start and after every redirect: 12.10.)
- Not built: an exception for a pattern, and "every parameter but this one" (neither is in the lists).

`$csp`.
- A loader throttle adds the lists' policy to a document's response, for a page and for a frame: as a
  header and in the parsed form the navigation reads. For a frame, a rule's `domain=` goes by the
  document that asked for the frame, and by the page it is in when that is not known.
- A policy with `report-uri` or `report-to` is not applied (12.7).

Checked (2026-11-11, on the build with all of it):
- 47 unit tests in the engine crate: 12 for the selector compiler, 7 for the `$removeparam` forms, 10 new
  ones for the bridge (clean addresses, the dropped forms before and after saving, policies, rules for
  the runner, a saved engine of another layout).
- `tools/qa/adblock_syntax_check.py`, offline, on throwaway profiles. It runs the runner on a fixture
  page with 25 hand-written rules, one per operator and action, and again after the page changes (a
  watched attribute, a new element, text that no longer matches). Then it takes the first simple real
  rule of each kind from the bundled lists and serves a page under that rule's site name: an element
  with the rule's text is hidden and one without is not; the ancestor a rule climbs to is hidden and the
  one above it is not; an element is removed; a class and an attribute are taken off; a style is applied;
  a parameter is gone from the page's address (the server and the page both see the clean one), from a
  frame's and from a fetch, and stays on an image; a page under a rule's `worker-src 'none'` has its
  worker refused, reported against that very policy. All of it also inside frames of another site's
  page, and none of it with blocking off or with ads allowed on the site.
- The earlier checks still pass: cosmetic rules (4 of 4), the per-site switch, list updates (which now
  save and load the engine in its new layout), and all 154 patches apply.
- Cost (`docs/perf/2026-11-11-native-adblock-proof-p522.md`): with all of it in, the test pages load in
  318.0 ms with the native blocker against 339.8 ms with uBlock Origin, 6.4 % faster (6.5 % before P5.22),
  with nothing let through, the same 12 stand-ins and 27 to 90 MB less memory. CPU per load was 0.264 s
  against 0.285 s, 7 % less, where the run before P5.22 had 15 %. That says little: this run was on a
  busier machine. The control, which runs none of the blocking code, took 20 % more CPU than in the
  morning's run, and every spread was wider. The tool measures one configuration after the other, so a
  machine that gets busier half way moves the comparison; measuring them in turns, on a quiet machine,
  is added to P5.17. Breakage on the 99 real sites did not change (9.2). A first run the same day, on the build before the last three changes and with the
  Python tests running beside it, gave 5.1 % and 11 % and is not used.

Still missing from uBlock Origin's syntax (P5.26), with how often the bundled lists use each: `$urlskip`
(238 rules; skips a redirect page), `$replace` (76; rewrites a response, trusted lists only), `$header`
(39; blocks by response header), `$uritransform` (14), `$permissions` (11; like `$csp` for the
Permissions-Policy header), `:shadow()` (2), HTML filtering (`##^`). Their rules are ignored, as they are
by adblock-rust itself.

### 12.10 Redirects (P5.25, 2026-11-11)

A request the lists allow can be redirected by its server: to a host they block (a "go" link on the
site itself that leads to an ad server), or to an address with a tracking parameter (the link in an
e-mail that goes through a click counter first). uBlock Origin sees every hop of a redirect. Until this
step the native blocker judged a request's first address only.

Requests other than documents.
- Every request the proxy lets out gets a `RedirectWatcher` between its loader in the network service
  and its client in the renderer. It passes everything on, and puts the target of each redirect to the
  engine before the client hears of it. Blocked: the request ends with `ERR_BLOCKED_BY_CLIENT`, as if the
  page had asked for that address itself (no stand-in is served for a redirect's target). Parameters to
  take out: the client is told the redirect leads to the clean address, and the network service follows
  it there.
- The watchers live on one background sequence. Putting the browser's UI thread into the path of every
  response is what makes request-watching extensions slow; here only a redirect asks the UI thread,
  where the engine is.

Documents (a page, a frame in one).
- A `DocumentRequestInterceptor` looks at the request at the start of a navigation and again after
  every redirect, the way the browser's own upgrade to https does. An address with parameters to take
  out is answered with an internal redirect to the clean address, so the address bar ends up clean
  after a redirect too. A frame the lists block is refused, or answered with its stand-in.
- It replaces two earlier pieces: the loader throttle no longer cleans the first address (it only adds
  `$csp` policies), and the request proxy no longer sits in front of frame navigations.
- A site that answers the clean address by sending the browser back to the one with the parameter gets
  its way: an address is cleaned once per navigation, then loaded as it is. Without that, such a site
  would not load at all.

Checked (2026-11-11):
- `tools/qa/adblock_redirect_check.py`, offline, on throwaway profiles. A page whose requests all meet
  a redirect first: a script, an image, a fetch, a frame and a script through two redirects that lead to
  an ad host never reach it, and the script does not run; a fetch and a frame redirected to an address
  with a parameter are asked for at the clean address; a script and an image redirected within the site
  still load. A page address reached through a redirect is asked for clean, and the page itself sees
  the clean address. A site that insists on its parameter loads, after one clean try. With blocking off,
  or ads allowed on the site, every redirect is followed as it is. The check also makes sure every hop
  was really asked for, so a request blocked before its redirect cannot pass for a blocked redirect.
- The earlier checks pass on the same build: syntax (runner and all four modes), cosmetic rules, the
  per-site switch with its blocked count, list updates; 154 patches apply.
- Cost. Two runs on this build (`docs/perf/2026-11-11-native-adblock-proof-p525.md`, `...-p525-run2.md`):
  the test pages load 10.2 % and 8.6 % faster than with uBlock Origin (306.1 against 340.8 ms, 325.3
  against 355.8 ms), with 30 % and 27 % less CPU and 25 to 109 MB less memory. The builds before measured
  6.5 % and 6.4 %. The two runs differ from each other as much as the builds do, so they could not say
  whether the 10 % target is met. Measured in turns the same evening (9.1), the answer is 6.1 % faster
  with 15 % less CPU: the watcher on every request shows no cost, and the target is not met. The 10.2 %
  was the luck of the order the configurations ran in.
- Real sites (`docs/perf/2026-11-11-native-adblock-breakage-p525.md`): 97 of the 99 could be compared.
  The two known flags are unchanged (vk.com, applovin.com: one tracking request each). baidu.com is
  flagged for less text (189 against 305 characters), which looked like this change, since that site
  redirects on entry. It is not: loaded four more times with both blockers, it gave both the same page
  each time, three times the short one and once the long one. The site serves two versions of its page,
  more often the short one after many visits.

Not covered:
- A page controlled by a service worker that answers the navigation itself: its request is cleaned on
  the way out, but the address bar keeps the address as it was.
- Requests that did not pass the request proxy at all: see 12.11 (P5.27).

### 12.11 Requests outside the request proxy (P5.27, 2026-11-11)

The request proxy sat in front of what a document, a worker and a service worker load once they run.
Chromium fetches some things through loaders of their own. Each kind, and what is done about it:

| Kind of request | What it is | Now |
|---|---|---|
| The script a worker or shared worker starts from | same site as the page by the web's own rules, so only a rule for a path can match | checked (new) |
| The scripts a service worker starts from and imports | an import may come from another site: how push-advertising networks get onto a site | checked (new) |
| `<link rel="prefetch">` | a page asks the browser to fetch something ahead of time | was checked already: it goes through the document's own loader |
| Pages fetched ahead of a visit (speculation rules) | a page's own request, made early | left out on purpose: a page's own request is never blocked, and its address is cleaned when the page is visited |
| Preloads announced by early hints | what a server names before its page arrives | not reachable: Chromium offers these requests neither to the browser layer nor to extensions, so uBlock Origin does not see them either (P5.28) |
| Downloads | a file the person asked for | left out on purpose |
| DevTools' own requests | | left out on purpose |

- A redirect of a worker's script is watched like any other request's (12.10).
- On "new": that these scripts were not checked before is read from the code (the proxy returned at once
  for their loaders); the check was not run against the build before. That prefetches were covered
  already follows from the check: the prefetch is stopped although the loader for pages fetched ahead is
  still left out.
- An early-hint preload of a tracker's script gives the tracker one request per page load. The script
  itself does not run: when the page asks for it, that request is blocked.

Checked (2026-11-11):
- `tools/qa/adblock_worker_check.py`, offline, on throwaway profiles, with a page on 127.0.0.1 (a service
  worker needs a trustworthy address). A worker and a shared worker whose script has a path the lists
  block on every site (the first plain rule of that kind in the bundled lists) are not fetched and do
  not start; the site's own service worker registers, and the script it imports from an ad host is not
  fetched; a prefetch of a script on the ad host is not made; a plain worker and a module worker that
  imports another file start. With blocking off, or ads allowed on the site, all of it is fetched and
  runs.
- The earlier checks pass on the same build: redirects, syntax, cosmetic rules, the per-site switch,
  list updates; 154 patches apply. The timing measurement was not repeated: for a page without workers
  nothing changes.
- Real sites (`docs/perf/2026-11-11-native-adblock-breakage-p527.md`): 95 of the 99 could be compared;
  the two known flags are unchanged. One new flag is **open**: digicert.com showed 1,676 characters of
  text with the native blocker against 3,782 with uBlock Origin, with the same nine requests blocked,
  on both loads; every earlier run had 3,782 for both. It could not be loaded again: minutes later the
  site answered both blockers with an empty page (its protection against automated visits now refuses
  this machine). So it is not explained. It may be this step (a worker's script that is now judged), or
  the site, which was tightening its protection at that very time. It has to be loaded again, from an
  address the site has not seen so often, before native blocking is switched on.

## 13. Credits

The procedural operators and the rest of the filter syntax are uBlock Origin's (with forms from Adblock
Plus and AdGuard); Thoron's compiler and page-side runner for them are its own code.

`adblock-rust` is by Brave Software and contributors (MPL-2.0). The filter lists are by their
maintainers (EasyList authors, Raymond Hill and the uBlock Origin contributors, Peter Lowe, the
malware list authors). uBlock Origin is by Raymond Hill and contributors (GPL-3.0). All are credited in
`CREDITS.md`, `NOTICE` and `chrome://credits`.
