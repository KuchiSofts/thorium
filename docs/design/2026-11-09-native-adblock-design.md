# Native ad blocking in Thoron (design, for the owner's approval)

Status: approved by the owner on 2026-11-09 ("do as you recommend"), with the recommendations in section 11.
Changed by the owner on 2026-11-11: the native blocker replaces uBlock Origin instead of working next to it
(section 12, which overrides sections 2 and 3 where they differ).
Extends the main design, section 10 ("Phase 2"), which already named this option. Roadmap: P5.2 (decided),
steps P5.13-P5.29.

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
end with `ERR_BLOCKED_BY_CLIENT`. It is off unless the `ThoronNativeAdblock` feature is on (since
2026-11-11 `chrome://flags` has a switch for it, section 4.7). The lists
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

Switch on `chrome://flags` (step 4, 2026-11-11). Until native blocking is on by default, the feature
could only be turned on with `--enable-features=ThoronNativeAdblock` on the command line, which nobody does
with the browser they use every day. `chrome://flags` now has an entry, "Built-in ad blocking"
(`#thoron-native-adblock`), that sets the same feature: Default (off for now), Enabled, Disabled. Its text
says what it is and that with uBlock Origin on as well both do the same work, so one of them should be
turned off. It is an ordinary entry of `about_flags.cc`, kept in the profile like every other flag, so it
survives restarts and updates; nothing new is stored and no new code path exists. The entry stays when
native blocking becomes the default (it is then the way to turn it off as a whole).

Checked in the 158.0.8127.3000 build on throwaway profiles: the entry is on the page with its three
choices and shows Default; with Enabled the browser starts with `--enable-features=ThoronNativeAdblock`
between its flag switches, with Disabled with `--disable-features=ThoronNativeAdblock`, and with neither
the feature is off.

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
- Which lists are on, the lists a person added and their own rules are kept for the whole browser, next
  to the lists, and edited on `chrome://adblock` (section 12.13).

## 8. Security

- Filter parsing runs in Rust; lists are untrusted input and are size-limited (for example 20 MB per
  list) before parsing.
- No new process gets more privilege; the engine runs where the request decision is made, without
  new IPC that a renderer could abuse to query browsing history of other sites.
- Fuzz the list parser and the request matcher (Chromium's fuzzing setup) before it ships on by
  default. First part done 2026-11-11 with a mutation fuzzer of Thoron's own (9.3); the run with
  Chromium's coverage-guided setup is still to do.

## 9. Proof that it is better (measured, not claimed)

Before it is turned on by default, with `tools/qa/bench.py` and new ad-heavy local test pages (copies
of typical news and recipe page structures with ad and tracker requests, served on 127.0.0.1):

| Measure | Target |
|---|---|
| Ads and trackers blocked on the test pages | at least as many as uBlock Origin alone |
| Page load time on the test pages | faster than uBlock Origin alone (until 2026-11-11: at least 10 % faster; section 11, decision 6) |
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

### 9.3 Fuzzing the list reading (P5.17, 2026-11-11)

The browser downloads filter lists and reads them in its own process. The engine is Rust, and in
Chromium a Rust panic ends the process, so a list that makes the reading panic would close the browser.
The lists come from a few hosts over HTTPS and are checked first (4.6), but the reading itself has to
survive any text.

- `fuzz_lists` is a build-machine tool in `components/thoron_adblock/` (not shipped). It takes real
  lines of the bundled lists, changes about four in ten (cuts, repeats, splices of other lines, filter
  operators, quotes, brackets, control characters and non-ASCII characters put in), and builds an engine
  from each small list the way the browser does. Then it asks everything the browser asks: what to do
  with requests of every type (WebSocket among them), the clean address, the policy for a document,
  what a document needs, generic hide rules, and saving and loading the engine. It runs the very code
  the browser runs: for that the engine's glue moved out of the bridge file into `engine_core.rs` and
  `cosmetics.rs`, which the bridge now only wraps.
- It also checks what the answers must always keep: a style sheet has one rule per line and nothing
  that leaves its rule; a rule for the page-side runner is valid JSON without a raw `<`; a cleaned
  address is the original with fewer parameters; a policy is plain text and asks for no reports; a
  stand-in comes only with a block; an engine saved and loaded decides as before.
- Result: two runs (2 and 8 minutes, two seeds), 832,376 lists and 26.6 million decisions: no abort,
  no rule broken, no decision that differs after saving and loading. Before that, the two parsers that
  are Thoron's own (procedural selectors, the `$removeparam` forms) took 18 million changed inputs on
  their own without an abort.
- What this is not: it changes text blindly, it does not watch which code a change reaches, so a
  deeply hidden case can escape it. Chromium's own setup does watch (coverage-guided, with memory
  checks). A target for it is the remaining part of this gate. The C++ side is not covered by either:
  it refuses a list that is not valid text before the engine sees it (4.6).
- After an abort the list that caused it is in `fuzz_lists_last.txt`; `fuzz_lists --replay` runs it again.

## 10. Steps (roadmap P5.13-P5.29)

1. **P5.13 Spike (throwaway):** link `adblock-rust` into a 158 build, block with a hard-coded EasyList,
   measure. Decides go or no-go.
2. **P5.14 Engine:** vendored crates (licence-checked, credited), C++ bridge, request
   throttle, `ERR_BLOCKED_BY_CLIENT`, redirect resources, tests.
3. **P5.15 Lists:** bundled compiled lists in each release, safe background updates, validation.
4. **P5.16 UI:** per-site switch in page info and Settings; a blocked-count badge (local only).
5. **P5.17 Proof:** the measurements of section 9; fuzzing; on by default only when all targets pass.
6. **P5.18 Later:** CNAME uncloaking.
7. **P5.19-P5.29:** the native blocker takes over the rest of uBlock Origin's work (section 12.8).

## 11. Decisions (approved 2026-11-09)

1. Approve the hybrid (native network blocking, uBlock Origin kept for cosmetics and its own rules).
2. Approve `adblock-rust` (MPL-2.0) as the engine.
3. Approve the default lists in section 6.
4. Native blocking on by default for everyone once section 9's targets pass (with the per-site switch
   to turn it off).

Decided 2026-11-11. Three questions were open for the owner. The owner left them to the engineering
judgment: whatever makes the browser faster, better and smarter.

5. New profiles get no built-in uBlock Origin once native blocking is on by default. Two blockers doing
   the same work cost memory and time and block nothing more (9.1). Existing profiles keep uBlock Origin
   and everything in it; nothing is removed, and it stays one click away for anyone who wants it.
6. The bar for turning native blocking on is not a number picked in advance. The 10 % load-time target
   was a guess made before anything was measured. The bar is: not worse than uBlock Origin on any
   measured axis (blocking, load time, CPU, memory, stand-ins), measured in turns. That is met: 6.1 %
   faster, 15 % less CPU, 38 to 76 MB less memory, the same blocking (9.1). What still holds it back is
   correctness, not speed: no flag on the real-site run that is not explained (none is open), WebSocket
   connections blocked (done, 12.12), and the list parser fuzzed (first part done, 9.3; the run with
   Chromium's coverage-guided setup is left). It stays off by default until those are done.
7. Scriptlets and stand-ins update with each Thoron build until signed updates exist (P5.23). They are
   code that runs inside every page; fetching them from anyone at run time without a signature would
   be the less safe choice, however fresh.

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
| WebSocket connections | the browser is asked before each connection of a frame | done (P5.29, section 12.12) |
| `$urlskip`: a navigation to a redirector goes straight to the destination | a module of the engine and the navigation interceptor (12.14) | done (P5.26, first part) |
| `$permissions`: the lists switch browser features off for a document | a module of the engine and the document throttle (12.15) | done (P5.26, second part) |
| `$header`: a request ends when the server's answer gives it away; the request's real method | a module of the engine, the request watcher and the document throttle (12.16) | done (P5.26, third part) |
| `$uritransform`: a request goes to the address a trusted rule makes of its own | a module of the engine, the navigation interceptor and the request proxy (12.17) | done (P5.26) |
| `:shadow()`: hide rules look inside shadow trees, open or closed | the procedural runner (12.18) | done (P5.26) |
| `$replace`, HTML filtering | rewrite a response's body, which uBlock Origin can do only in Firefox | left out (P5.26) |
| Preloads announced by early hints | a throttle on the browser's own requests (12.19) | done (P5.28) |
| List updates | 4.6 | done |
| Scriptlet and resource updates | 12.4 | P5.23 |
| Per-site switch, blocked count | 4.7 | done |
| Lists on and off, added lists, own rules | a settings page, `chrome://adblock` (12.13) | done (P5.30) |
| Element picker | 12.6 | later |

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
  key, checked before use, with the shipped copy as the fallback. Until then they update with each
  build, which is the decided way (section 11, decision 7).
- A filter that names a scriptlet the installed resources do not have is ignored, as in uBlock Origin.

### 12.5 uBlock Origin itself

- Existing profiles: nothing is removed or changed. A profile that has uBlock Origin keeps it, with its
  settings and custom filters.
- New profiles: once native blocking is on by default, the built-in uBlock Origin is no longer installed
  into new profiles (decided 2026-11-11: section 11, decision 5). Until the default changes, nothing
  changes.
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

Added with P5.29 (WebSockets):
- A blocked WebSocket is dropped before anything is sent. Every other connection is opened as the
  browser opens it when nobody steps in, or handed to an extension that asked to see it, as before.
  The decision uses the address the frame has committed and the page it is in.

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
- **P5.29** WebSocket connections (done, 12.12).
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
  on both loads; every earlier run had 3,782 for both. It could not be loaded again at once: minutes
  later the site answered both blockers with an empty page (its protection against automated visits
  refused this machine). **Closed the same evening:** on the next run of the 99 sites, on a build that
  still has this step, the site let the machine in again and gave both blockers 3,782 characters with
  nine requests blocked each (`docs/perf/2026-11-11-native-adblock-breakage-p529.md`). The flag was the
  site tightening its protection, not this step.

### 12.12 WebSocket connections (P5.29, 2026-11-11)

A WebSocket connection is not a request for a file, so the request proxy never sees it. Ad and tracking
scripts use that: what they may not fetch, they send through a socket to the same host. uBlock Origin
blocks such connections; the native blocker did not.

- Chromium asks the browser layer before a frame opens a WebSocket, if the browser layer wants to be
  asked. While native blocking is on, it does. The address is put to the engine as a request of the
  type `websocket`, with the frame's committed address as the document that asks and the per-site
  switch read for the page the frame is in.
- Blocked: the connection is not opened; the page sees it fail, as it sees a blocked request fail, and
  the page's count of blocked requests goes up. Not blocked: the connection is opened as the browser
  opens it when nobody steps in, or handed to an extension that asked to see WebSockets, as before.
- Not covered: a WebSocket opened by a shared worker or a service worker (Chromium has no frame to ask
  about), and WebTransport, which the lists have no type for.
- One side effect, the same as with any extension that watches requests: extra headers set in DevTools
  for testing are not added to a WebSocket's handshake while native blocking is on.

Checked (2026-11-11):
- `tools/qa/adblock_worker_check.py` (which now also opens sockets; its server answers a real WebSocket
  handshake): with blocking on, a WebSocket to an ad host is not opened and the server never hears of
  it, while a WebSocket to the site itself opens; with blocking off, or ads allowed on the site, both
  open.
- The redirect, syntax, cosmetic, per-site switch and list update checks pass on the same build; 154
  patches apply.
- Real sites (`docs/perf/2026-11-11-native-adblock-breakage-p529.md`): 96 of the 99 could be compared;
  only the two known flags (vk.com, applovin.com). No site shows less than 94 % of the text it shows
  with uBlock Origin.

### 12.13 The settings page (P5.30, 2026-11-12)

The owner asked that people can add and edit, as they can in uBlock Origin. `chrome://adblock` is the
blocker's settings page:

- **Filter lists:** the eight built-in lists with their names, rule counts and a checkbox each. A list that
  is switched off is neither used nor downloaded. "Update now" looks for newer lists at once.
- **Add a list:** by its address. The list is downloaded the way every list is (HTTPS only, redirects
  included, no cookies, no cache, 20 MB at most) and passes the checks of an updated list before it is
  used; a web page or a list with a rule that allows every request is refused, with the reason in plain
  words. Up to 30 lists.
- **My filters:** the person's own rules in the syntax of the lists, up to 1 MB.
- **On, off and allowed sites** stay where they are: the page links to the "Ads and trackers" site setting.

Where it is kept. For the whole browser, like the lists themselves, in the store folder next to them
(`settings.json`, `my-filters.txt`, a stored copy of each added list), never in a profile. What is
chosen here stays on the PC; an added list is fetched from the address the person gave, at most every 4
days.

How it is built in. The engine is built from the lists the settings name: the built-in ones that are on,
then the added lists, then the person's rules, each under its own id. Every change builds the engine anew
on the background sequence, saves it, and puts it to use at once, without a restart. A saved engine is
only loaded for the settings it was built for (a fingerprint in the state file); after an update of the
browser the engine is built again from the shipped lists, the stored added lists and the person's rules.

Trust. As for every list, the id decides, never the content: only ids that start with `ublock-` may use
the trusted scriptlets. An added list gets the id `custom-` plus a hash of its address, worked out by the
browser every time, and the person's rules get `my-filters`; nothing in a file can give either the id of
a trusted list. A list or rules that hold a list marker line are refused. A `$csp` rule can only add to a
page's policy, never loosen it (section 12.9).

No crash at every start. Reading a list runs the parser inside the browser, and text a person supplies is
the least predictable there is. Before the lists of changed settings are read, the state file records
which settings are being read. If the browser stops while reading them, the next start finds the record,
does not read them again, uses the engine saved before, and the page says that the last change is not in
use. The next change is read normally.

The page itself. Plain HTML and one module script, kept next to the engine and compiled into it, served
by a data source with Chromium's default policy for such pages: script only from the page itself and from
the browser's own resources, and no markup made from text (the page is built with DOM calls). Its
messages are checked for shape and size before anything is done. The page exists only while the
`ThoronNativeAdblock` feature is on.

Checked with `tools/qa/adblock_settings_check.py`, offline, in 14 steps that work the page like a person:
own rules block; a rule that allows everything is refused and the box keeps the text; an added list
blocks, shows its title, and its rule that asks for trust is not carried out; a web page and an address
that is not secure are refused; a list switched off stops blocking and blocks again when switched on, with
its updated copy; every choice survives a restart and an update of the browser; a removed list stops
blocking; after an interruption the settings are not read again and the page says so. Two engine tests
cover the trust of added lists and own rules and that the page holds no inline script.

Still to do: a link to the page from Settings (today: the flag's text and the address bar), translations,
and the element picker (12.6).

### 12.14 `$urlskip` (P5.26, 2026-11-12)

Many links do not lead to a page but to a tracker that notes the click and then sends the browser on. The
lists know these redirectors and where the real address is written inside theirs:
`||out.example/go^$doc,urlskip=?url` says that the destination is the value of the parameter `url`. With
the rule, a navigation to the redirector goes straight to the destination, and the redirector is never
contacted. The bundled lists hold 241 such lines, all in uBlock Origin's own lists.

How it is built:

- adblock-rust does not know the option, so the rules are kept in a module of the engine (`urlskip.rs`).
  An engine of their own, with the rules as filters for documents, says which rule matches a navigation;
  it is built without fusing rules, so that it can name the one that matched.
- The steps after `urlskip=` are carried out one after the other: `?name` (a parameter's value), `&2` (the
  name of the second parameter), `#` (what follows the `#`), `/re/` (the first group of a regular
  expression), `+https`, `-base64`, `-safebase64`, `-uricomponent`. `-blocked` lets a rule apply to a
  redirector the lists block. A rule whose steps or options are not understood in full is not used.
- Only rules of trusted lists count, as for the trusted scriptlets: a list a person added, or a rule of
  their own, cannot send a navigation somewhere else.
- It applies to navigations of the main frame made with GET, in the navigation interceptor (12.10), before
  the address is cleaned. A frame and a form sent with POST go to the redirector as they are. The guard
  against going in circles is the one of the address cleaning.
- What the steps find is only a suggestion. The browser follows it only when it is a valid http or https
  address without a user name, and not the address it came from. The new address is then a navigation like
  any other: it is checked, cleaned, and may be skipped again.
- With ads allowed on the redirector's site (the per-site switch), nothing is skipped.
- The rules are saved with the engine (the saved layout is now 2; an engine saved in layout 1 is refused
  and the shipped one is used).
- The regular expressions use the `regex` crate, which matches in linear time. It is now a direct
  dependency in Chromium's crate lists, so that the engine's own code may use it.

Coverage: 240 of the 241 lines. The one left out is a rule for a podcast's audio files (`$media`), which
is not a navigation.

Checked: 15 engine tests (every step, the parsing of rules with options before and after the steps, trust
by list id, saving, `-blocked`), and `tools/qa/adblock_urlskip_check.py`, offline, with two real rules of
the lists: one that reads the destination from a parameter and one that also decodes it from base64. With
native blocking on, the destination is reached and the redirector is never asked; a form sent with POST and
a frame go to the redirector; with native blocking off nothing is skipped.

Security review. The destination is one the redirector itself would send the browser to, so the rule
opens no door the link did not already have; it is limited to http and https, never carries a user name,
is at most 8,192 characters long after at most 8 steps, and comes only from rules of trusted lists.

### 12.15 `$permissions` (P5.26, 2026-11-12)

A site can say which browser features its pages may use, with the `Permissions-Policy` header. uBlock
Origin's lists use the same header against features that were built for ad targeting, or that help to tell
one browser from another: `*$permissions=browsing-topics=(),from=~localhost|...` switches the ad topics off
on every site that is not on the PC itself. The bundled lists hold 10 such rules (ad topics, ad auctions
and interest groups, attribution reporting, private aggregation, private state tokens, idle detection, the
keyboard map, compute pressure) and one exception, all in uBlock Origin's own lists.

How it is built:

- adblock-rust does not know the option. It knows `$csp`, which works the same way: the values of all the
  rules that match a document are collected, without those an exception takes away. So the rules are
  rewritten as `$csp` rules for an engine of their own (`permissions.rs`), which is asked once per document.
- Only a value that switches a feature off (`name=()`) is taken. A rule that would give a feature to a
  page or a frame (`camera=*`, `(self)`, an origin) is left out whole, and what the engine returns is
  checked once more: the header Thoron adds can take a feature away and never give one.
- Only rules of trusted lists count, as for `$urlskip`: a list a person added, or a rule of their own,
  cannot change what a page may use.
- The throttle that adds the `$csp` policy to a document's response (12.9) adds this header too, for a
  page and for a frame. When the site sends a policy of its own for the same feature, the one of the lists
  counts.
- With ads allowed on the site (the per-site switch), nothing is added.
- The saved engine is now in layout 3: the lines that only trusted lists may bring (`$urlskip`,
  `$permissions`) are in a section of their own, apart from the `$removeparam` lines, which come from every
  list. A line of a list without trust can so never be read as one of them, also not after saving. An
  engine saved in an older layout is refused and the shipped one is used.

Coverage: all 11 lines.

Checked: 5 engine tests (the rewriting, what is left out, the policy of a page and of a frame, exceptions,
trust by list id, saving, and a `$removeparam` rule of an untrusted list that names the other options too),
and two new cases in `tools/qa/adblock_syntax_check.py`, offline, with the real rules: a page whose own
header keeps every feature for the site, and a page on the site of the exception. With native blocking on,
every feature the rules name that this build has is off for the first page (6 of the 10; the other four,
for ad auctions, interest groups, attribution reporting and private aggregation, are not in a plain http
page of this build), and on the second only the excepted one stays. With native blocking off, and with ads
allowed on the site, all of them are allowed.

Security review. The header only narrows what a page may do, comes only from trusted lists, holds only
`name=()` entries with names of lower-case letters, digits and `-`, and is at most 2,048 characters long.

### 12.16 `$header` and the request method (P5.26, 2026-11-12)

Some ad servers change their names and addresses all the time, but their answers give them away: a
header that only their software sends (`popads-node`, `x-77-pop`), a value of a common header (`via`,
`etag`, `link`) or a redirect to a known address. uBlock Origin's lists catch them with `$header`:
`://www.*.css|$script,xhr,3p,to=com,header=popads-node` ends a script request from another site to a
`.com` host when the answer carries that header. The bundled lists hold 52 such lines.

How it is built:

- adblock-rust does not know the option, so the rules are kept in a module of the engine (`header.rs`).
  It works in two steps. When a request starts, a small engine of its own says which rules could apply
  (address, who asks, type, method). adblock-rust names only one matching rule per question, except for
  `$csp` rules, of which it names all, so each rule is given to it as a `$csp` rule whose value is the
  rule's number. What those rules ask of the answer goes with the request as a few lines of text; for
  nearly every request there are none.
- When the answer arrives, its headers are tested against those lines. A redirect is an answer too. This
  happens in the watcher that already sits on every request a page, a worker or a service worker makes
  (12.10), before the page sees any of the answer, and for frames in the throttle on the frame's
  navigation (12.9). A page's own request is never ended.
- The value is read exactly as uBlock Origin reads it: `name` (the header is there), `name:text` (the
  value holds the text, in any case; `*` and `?` are wildcards), `name:/re/` and `name:/re/i` (a regular
  expression), and `~` for the opposite. Only the first header of a name counts. A rule's options are
  found and split as uBlock Origin does it: the last `$` that an option follows, and a comma ends an
  option only when another option follows, so a value may hold commas (`header=via:/, 1\.1 google$/`).
- `to=` is checked by the module: adblock-rust reads the option and then leaves the whole rule out.
  `strict1p` and `strict3p` (the very host of the document, or not), request types and `important` are
  checked there too.
- An exception rule of the lists for the request (`@@||site.example^`) spares it, except from a rule
  marked `important`; an exception with `header=` counts only when the answer is as it says.
- A rule can only end a request, like any blocking rule, so every list may bring such rules.
- Requests of a type no rule is for (images, style sheets, fonts) are passed over at once. Measured with
  the bundled lists on 400 kinds of requests: 5.9 microseconds a request against 4.5 without the rules,
  and 30 of the 400 wait for their answer.
- The rules are saved with the engine, in the section of rules every list may bring (layout 4).

The request's real method now reaches the engine too. Before, every request was checked as a `GET`, so
the lists' 58 rules with `method=` (a tracker that only receives `POST`, probes sent with `HEAD`) were
never or wrongly applied.

Coverage: 50 of the 52 lines. Left out: one rule that tests a header the browser sends
(`requestheader=Cookie`; the cookies are added where this code does not see them), and one line that is
an address with `&header=` in it, not a rule of this kind.

Checked: 17 engine tests (the value syntax, the opposite, regular expressions and wildcards, splitting
the options, `to=`, `strict1p`, exceptions and `important`, types passed over, saving, the method), and
`tools/qa/adblock_header_check.py`, offline, with four real rules of the lists: a header by name, a header
by value, a redirect to a known address, and a frame. Each has an answer with the header and one without:
with native blocking on, only the first is stopped; with blocking off, and with ads allowed on the site,
both load. `tools/qa/adblock_syntax_check.py` has a case for `method=` with a real rule: a `POST` to the
tracker is stopped and a `GET` to the same address is not.

Security review. Nothing new is sent anywhere; an answer can only end its own request. The values are
read as bytes, the regular expressions use the `regex` crate (linear time, a size limit of 1 MB to
prepare), at most 16 rules go with one request, and a value is at most 1,024 characters.

### 12.17 `$uritransform` (P5.26, 2026-11-12)

A rule of uBlock Origin's own lists can make another address of a request's own, with a regular expression and
a replacement: `||shop.example/dp/*/ref=$doc,uritransform=/\/ref=[^\/?#]+//` takes the tracking part out of a
product page's address, `$uritransform=/adblock%3Dtrue/adblock%3Dfalse/` answers an anti-blocker's check. The
bundled lists hold 16 such lines.

- adblock-rust does not know the option, so the rules are kept in a module of the engine (`uritransform.rs`). A
  small engine of their own says which rules match a request (each rule as a `$csp` rule whose value is its
  number, as for `$header`, 12.16); exceptions (`@@...$uritransform`, with or without a value) in a second one.
- The value is read as uBlock Origin reads it: `/pattern/replacement/flags`, "\/", "\$" and "\," unescaped,
  an empty pattern standing for the rule's own regular expression, `$1`, `$&` and `$$` in the replacement as in
  JavaScript, the flags `i` and `g`. The pattern is tried on the whole address; of the matching rules the first
  that changes it is used.
- Only rules of trusted lists count: a rule sends a request somewhere else.
- A page or a frame goes to the new address by a redirect the browser sees (the navigation interceptor, 12.10),
  before `$urlskip` and the removal of tracking parameters, as in uBlock Origin. Any other request is sent to
  the new address without the page being told, so only to another address of the same origin.
- Coverage: 16 of the 16 lines. Checked by 9 engine tests and
  `tools/qa/adblock_uritransform_check.py`, offline, with two real rules (a page whose address is rewritten, a
  script fetched from its rewritten address): with native blocking on only the new address is asked for; with
  blocking off, and with ads allowed on the site, only the old one.

### 12.18 `:shadow()` (P5.26, 2026-11-12)

Some widgets keep their content in a shadow tree, which the page's own selectors and a user style sheet do not
reach. `:shadow(selector)` looks inside: `[id^="outbrain_widget_"]:has(:shadow(a[rel*="sponsored"]))`.

- The engine passes the operator to the procedural runner (12.9); the runner looks in the element's shadow tree,
  open or closed. A closed one is reached through `thoronShadowRoot()`, which the browser gives only to the
  runner's isolated world (what `chrome.dom.openOrClosedShadowRoot` is to an extension): the page's world never
  sees it.
- uBlock Origin finds elements in a shadow tree but its hiding style does not reach them. Thoron's runner gives
  an element it marks inside a shadow tree the declarations of its mark in its own style while it is marked,
  and gives the old style back when the mark goes.
- Coverage: both lines of the bundled lists. Checked by two engine tests, a rule of the runner battery (an element
  in an open shadow tree is hidden) and a case of `tools/qa/adblock_syntax_check.py` with the real rule: a widget
  whose shadow tree holds the sponsored link is marked whether the tree is open or closed, one without it is not.

### 12.19 Preloads announced by "103 Early Hints" (P5.28, 2026-11-12)

While a server works on a page, it may send "103 Early Hints" with `Link: rel=preload` headers, and Chromium
fetches those files at once, before the page arrives and outside the request proxy. They do pass Chromium's
throttles for browser requests (`CreateURLLoaderThrottles`), so a throttle of the component
(`subresource_loader_throttle.cc`) puts each to the engine like any request of the page: one the lists block is
not made, a redirect is checked again, and an answer that gives an ad server away is ended (`$header`). It looks
only at scripts, style sheets, fonts, images, tracks and media; documents, worker scripts and downloads are left
to the pieces that handle them. No change to Chromium's navigation code was needed. Checked by
`tools/qa/adblock_earlyhints_check.py`, offline (with Chromium's switch for early hints over HTTP/1.1, as the
local server speaks it): with native blocking on the ad host is never asked and the plain host is; with
blocking off, and with ads allowed on the site, both are.

### 12.20 What was blocked on the page (P5.31, 2026-11-12)

The bubble of the shield in the address bar lists the sites the page's blocked requests were for, the most
first, with how many each (up to 8, then "and N more sites"). The counter keeps them in memory with the page, as
it keeps the count: nothing is stored or sent.

### 12.21 The shield in the toolbar and its menu (P5.31, P5.32, P5.33, 2026-11-12)

The owner asked for the blocker to work like uBlock Origin from the toolbar: "1:1 same options", a smart
menu, the count on the icon, and blocking of elements.

- **The shield** (`thoron_adblock_button.cc`) sits in the toolbar where an ad blocker's icon sits, while
  the blocker is on. Its badge shows what was blocked on the active tab's page ("12", "1k"), as uBlock
  Origin's does; it is greyed out on a site where ads are allowed and on pages that are not web pages. It
  follows the active tab and every blocked request (BlockedCount tells it).
- **The menu** (`chrome://adblock-menu.top-chrome`, a top-chrome WebUI in a bubble, like Chromium's tab
  search): the big switch for the site (the "Ads and trackers" site setting, which the blocker already
  follows; the tab reloads), the counts (this page, the sites, the total so far), the tools (Block element,
  Zapper, Logger, Settings) and the per-site switches: pop-ups and JavaScript (Chrome's own site settings),
  large media (audio or video files larger than 50 KB are ended by their answer), no hiding (no hide
  rules, no scriptlets) and remote fonts (no font is loaded). The three switches of the blocker are kept
  in `<user data>/Thoron Adblock/site-switches.json`, by host, and count for the hosts below it too; the
  total in `stats.json`, written at most every 30 seconds. Nothing leaves the computer.
- **The element picker** (`picker.js`, P5.32) runs in the isolated world of the procedural runner: the page
  cannot reach it. Hovering shows an element, a click picks it, and a panel offers rules for it, from the
  element itself to the elements around it and the address of an image or frame; the rule can be edited,
  previewed, and created (Enter or "Create"). The browser takes a rule only from a page it started a picker
  in during the last ten minutes, once per opening, only one line of at most 2,000 characters, and only a
  hide rule for that page's own site or a rule that blocks an address (`picker.cc`); it then adds it to "My
  filters", where it is in use at once. **The zapper** removes elements until the page is loaded again.
- **The dashboard** (`chrome://adblock`, P5.33) gets a top bar (Filter lists, My filters, Sites, Logger),
  the total, a **Sites** section (the sites where ads are allowed, each removable, a box to allow a site;
  the menu's switches by host, each removable) and a live **Logger**: every request blocked on the open
  tabs of the profile, the newest first, per tab, with a filter (kept in memory with each page; nothing is
  stored or sent).

Checked by `tools/qa/adblock_menu_check.py`, offline, on a test page: the menu names the site and counts
and lists the blocked ad host; each switch has its effect while on and none while off (the font is not
asked for, the large sound fails, a generic hide rule hides nothing, the ad host is asked for); the picker,
driven by mouse and Enter, puts a rule for the site into My filters and the element is hidden after a
reload; the zapper removes one element and keeps the rest.

### 12.22 More lists, and no empty boxes (P5.34, P5.35, 2026-11-12)

- **More lists.** `chrome://adblock` offers the 62 lists uBlock Origin offers besides its defaults (its
  `assets.json`): cookie notices and other annoyances, more privacy, phishing, and the lists for regions and
  languages, grouped as uBlock Origin groups them, each with a checkbox. A list switched on is added like any
  list a person adds (12.13): fetched over HTTPS without cookies, checked, in use at once, and without trust
  (the few trusted scriptlets of uBlock Origin's own optional lists are left out, as for any added list).
- **No empty boxes.** A blocked image, frame or embedded object used to leave an empty box (a broken image,
  an error page in a frame). The blocker now ends such a request with Chromium's flag for it
  (`should_collapse_initiator`, which Chromium's own ad filter uses), so the element is collapsed and the page
  closes up, as uBlock Origin's "hide placeholders of blocked elements" does. It applies to the request
  proxy, to redirects and to frames. Checked by `tools/qa/adblock_menu_check.py`: a blocked 300x250 ad image
  and ad frame take up no space.

### 12.23 Pop-ups (P5.36, 2026-11-12)

- **`$popup` rules.** adblock-rust does not read the option and leaves such rules out, so the 3,112 pop-up
  rules of the bundled lists (nearly all EasyList's) did nothing, and neither did the pop-up part of the
  8,970 `$all` rules (uBlock Origin's badware list uses `$all`, which covers pop-ups). `popup.rs` reads them:
  each becomes a `$document` rule in a small engine of its own, keeping `domain=`, `from=`, `denyallow=`,
  first or third party, `important`, `match-case` and `badfilter`. A rule with anything else (`~popup`,
  `popunder`, `redirect=`, `csp=`...) is left out, as is any rule adblock-rust would not read as written. As
  in uBlock Origin, a rule without `$popup` or `$all` never blocks a window, and `domain=` and first or third
  party are read against the page of the tab that opens it. The rules are saved with the engine (layout 6);
  an engine saved in the old layout is built again from the stored lists.
- **Where.** In `ChromeContentBrowserClient::CanCreateWindow`, before Chromium's own pop-up blocker: a window
  the rules block is never created (`window.open()` returns null, a link with a target opens nothing). A page
  can also open a blank window and send it to the ad afterwards; the first navigation of a window that has
  an opener and holds only its first blank document is checked too, and the window is closed. Each is
  counted on the page, so the shield and the logger show it. Nothing happens on a site where ads are allowed.
- **"No pop-ups".** The menu's switch was Chromium's pop-up setting, which still lets a click open a window.
  It is now the blocker's own, as in uBlock Origin: every window the site opens is stopped, also one a click
  opens. It is kept with the other switches (site-switches.json) and listed under Sites on `chrome://adblock`.
- **Checked** by `tools/qa/adblock_popup_check.py`: with blocking off the ad window opens; with it on,
  `window.open()` of the ad address returns null and the ad host is never asked, a link to it opens nothing,
  a blank window sent to it is closed, a plain window opens, the menu counts the three, and with "no pop-ups"
  on neither a window nor a link to the plain host opens; with ads allowed on the site the ad window opens.
  Seven engine tests cover the rules.

### 12.24 Strict blocking: pages the lists block are not opened (P5.37, 2026-11-12)

- **What was missing.** A page's own address was never blocked, so the lists that exist to keep people
  away from harmful pages did little: uBlock Origin's badware list (2,542 `$doc` and 1,308 `$all` rules),
  the 7,563 `$all` addresses of the malware list (URLhaus) and the phishing list of "More lists" only
  blocked what such a page loaded, not the page.
- **What happens now**, as in uBlock Origin: a page is not opened when a rule for whole pages matches it
  (`$doc`, `$document`, `$all`), or a rule that names its whole host and nothing more (`||ads.example^`,
  about 90,000 in the bundled lists), never by a rule for a part of an address (`/ads/*`). A page that says
  why is shown in its place: the address, its site, and how to open it anyway (the shield's big button
  allows the site). When the blocked
  page is a redirector that names where it sends on to (`?url=https%3A...`) and that address is not
  blocked itself, the page offers it as a link, as uBlock Origin does. A redirector a `$urlskip` rule goes
  past is not stopped: the navigation goes straight on. Redirects are checked too.
- **How.** adblock-rust already reads a page's own request the way uBlock Origin does: a rule for whole
  pages, and a rule for a whole host (also with `$important`) match it, a rule for a part of an address or
  for other sites only (`$third-party`) does not, and an exception for the host, `$badfilter` or an
  exception for the page (`@@...$document`) keeps it open (engine test). What was missing was asking it.
  A navigation throttle on the main frame of a tab (`page_block_throttle.cc`) asks before the request is
  made, so the server is never reached; the page is Chromium's error page with Thoron's own text (plain
  HTML, no scripts, every address escaped). Nothing happens on a site where ads are allowed. No new data:
  the saved engine stays as it was.
- **Checked** by `tools/qa/adblock_strict_check.py`: with blocking off every page opens; with it on, pages
  on a host rule of EasyList, a `$doc` and an `$all` host of the badware list are not opened (the server is
  never asked) and the page names the site, a plain page opens, a redirect to a blocked host ends on the
  blocked page, a blocked redirector offers where it sends on to and the link opens it; with ads allowed on
  the site its page opens. An engine test covers what blocks a page and what does not.

### 12.25 Settings, as uBlock Origin's (P5.38, 2026-11-12)

- **What.** `chrome://adblock` has a Settings section with the options of uBlock Origin's settings page:
  - *Appearance:* show the number of blocked requests on the shield (on by default).
  - *Privacy:* disable pre-fetching, disable hyperlink auditing, prevent WebRTC from leaking local IP
    addresses, block CSP reports.
  - *Default behavior:* disable cosmetic filtering, block media elements larger than 50 KB, block remote
    fonts, disable JavaScript, for every site.
  - *Filtering:* ignore generic cosmetic filters.
- **How.** The blocker's own options are kept in `<store>/options.json` (`badge`, `block-csp-reports`,
  `ignore-generic`, `default-media`, `default-cosmetic`, `default-fonts`; only known names with true or
  false are read). The pre-fetching, hyperlink-auditing and WebRTC options are the browser's own settings
  (`net.network_prediction_options`, `enable_a_ping`, `webrtc.ip_handling_policy`), which uBlock Origin
  also changes; "disable JavaScript" is the browser's default for JavaScript. They show the same in
  Chromium's settings, and the page reads back what is in force. A CSP report is a request of the kind
  "report"; with the option it is blocked like any blocked request.
- **Defaults and sites.** As in uBlock Origin, a default is the menu's switch for every site, and the
  menu changes it for one site: a site where the default is on can be kept out (stored as `-fonts` and so
  on, listed under Sites as "remote fonts allowed"). A switch is stored for a site only when it differs
  from what the site would have without it.
- **Checked** by `tools/qa/adblock_options_check.py`: the defaults read as uBlock Origin's; with every
  setting on, the CSP report is not sent, the element of a generic rule is shown, the font is not asked
  for; the menu's switch keeps one site out of the font default and chrome://adblock lists it; "disable
  JavaScript" stops the page's script; off again, every setting reads off.

### 12.26 The menu's counts, as uBlock Origin's (P5.39, 2026-11-12)

- The menu showed what was blocked on the page and how many sites. It now shows what uBlock Origin's does:
  blocked on this page with the share of the page's requests that was (12 (20%)), and the domains
  connected out of all the page asked (8 of 11: three were only ever blocked). A domain is the name a site
  registered (`example.co.uk`), or the host for an IP address.
- Every request the blocker lets through is counted with its page as well (`BlockedCount::Allowed`), in
  memory only, like the blocked ones: at most 500 domains a page, nothing stored or sent.
- Checked by `tools/qa/adblock_menu_check.py`: the share reads as a percentage, and the domains connected
  are at least one and fewer than all (the ad's domain is never reached).

### 12.27 Back up, restore, reset (P5.40, 2026-11-12)

- **What.** As in uBlock Origin's Settings: "Back up to file" saves a JSON file (`format`
  `thoron-adblock-backup`, `version` 1) with the built-in lists that are off, the lists the person added
  (their addresses), their own rules, the allowed sites (as the site settings write them), the menu's
  switches by host, and the Settings. "Restore from file" makes everything as the file has it;
  "Reset to default settings" does the same with the defaults, after the person confirms it.
- **How.** The page makes the file from what it already asks the browser for (nothing new is read), and
  the browser saves it like any download: nothing leaves the computer. A restore reads the file in the
  page (at most 4 MB, the format and version checked, every part type checked, only known setting names,
  added lists only with `https://`), then makes each change through the page's usual messages, so every
  check those messages do still applies (an added list is downloaded and checked like any; own rules at
  most 1 MB). Two messages are new: one allows a site by the pattern the site settings wrote (never every
  site at once), one sets a host's switches (only known names, at most 16).
- **Checked** by `tools/qa/adblock_backup_check.py`: settings, own rules, an allowed site, switches and a
  list switched off are all in the saved file; after a reset each is at its default; after restoring the
  file each is as it was.

## 13. Credits

The procedural operators and the rest of the filter syntax are uBlock Origin's (with forms from Adblock
Plus and AdGuard); Thoron's compiler and page-side runner for them are its own code.

`adblock-rust` is by Brave Software and contributors (MPL-2.0). The filter lists are by their
maintainers (EasyList authors, Raymond Hill and the uBlock Origin contributors, Peter Lowe, the
malware list authors). uBlock Origin is by Raymond Hill and contributors (GPL-3.0). All are credited in
`CREDITS.md`, `NOTICE` and `chrome://credits`.
