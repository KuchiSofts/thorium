# Native ad blocking in Thoron (design, for the owner's approval)

Status: approved by the owner on 2026-11-09 ("do as you recommend"), with the recommendations in section 11.
Extends the main design, section 10 ("Phase 2"), which already named this option. Roadmap: P5.2 (decided),
steps P5.13-P5.18.

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
- Replacing uBlock Origin. uBlock Origin stays for what it does best: hiding page elements
  (cosmetic filtering), scriptlets, the element picker and its own settings.
- Our own filter lists. We use the community lists and credit them.

**Anti-goals (would make this a failure even if it works)**
- Breaking sites people use every day more than uBlock Origin does today.
- Any telemetry, "acceptable ads" programme or paid allow-listing.
- Losing anyone's uBlock Origin settings or custom filters.
- Weakening the sandbox or security releases (security releases always ship first, design G2).

## 3. The hybrid

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

## 5. Where it plugs in

- **Engine host:** one engine per browser (not per profile), built from the compiled lists, shared
  read-only, so 10 profiles do not cost 10 engines.
- **Request check:** a `URLLoaderThrottle` (or the network service's request hook) asks the engine
  for each subresource request: URL, top-level site, resource type, third-party flag. Blocked
  requests are cancelled with `ERR_BLOCKED_BY_CLIENT`, as extensions do today.
- **Redirect resources** (`$redirect=noop.js` and similar) come from a small bundled set of neutral
  stand-ins, the same idea uBlock Origin uses.
- **CNAME uncloaking:** use Chromium's DNS results to also match the real host behind a tracker's
  CNAME (extensions cannot do this on Chromium).
- **Per-site switch:** a content setting ("Ads and trackers: blocked / allowed on this site"), in
  the page info bubble and in Settings; stored in the profile like other site settings.

## 6. Filter lists and updates

- **Default lists:** EasyList, EasyPrivacy, uBlock filters, uBlock privacy, Peter Lowe's list and a
  malware domain list. Each has its own licence (EasyList: CC BY-SA 3.0 or GPL-3.0; uBlock filters:
  GPL-3.0); all are credited in `CREDITS.md` and `chrome://credits`.
- **Updates:** downloaded from their published URLs like uBlock Origin does today, at most every 4
  days, over HTTPS only. A compiled copy of known-good lists ships with each release, so a fresh
  install blocks from the first page with no download at all.
- **Validation:** a downloaded list is compiled in a background step; if it fails to parse, is empty
  or shrinks by more than half, the previous compiled engine stays (no "everything allowed" state).
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

## 10. Steps (roadmap P5.13-P5.18)

1. **P5.13 Spike (throwaway):** link `adblock-rust` into a 158 build, block with a hard-coded EasyList,
   measure. Decides go or no-go.
2. **P5.14 Engine:** vendored crates (licence-checked, credited), C++ bridge, request
   throttle, `ERR_BLOCKED_BY_CLIENT`, redirect resources, tests.
3. **P5.15 Lists:** bundled compiled lists in each release, safe background updates, validation.
4. **P5.16 UI:** per-site switch in page info and Settings; a blocked-count badge (local only).
5. **P5.17 Proof:** the measurements of section 9; fuzzing; on by default only when all targets pass.
6. **P5.18 Later:** CNAME uncloaking; native cosmetic filtering if it proves better than uBlock's.

## 11. Decisions (approved 2026-11-09)

1. Approve the hybrid (native network blocking, uBlock Origin kept for cosmetics and its own rules).
2. Approve `adblock-rust` (MPL-2.0) as the engine.
3. Approve the default lists in section 6.
4. Native blocking on by default for everyone once section 9's targets pass (with the per-site switch
   to turn it off).

## 12. Credits

`adblock-rust` is by Brave Software and contributors (MPL-2.0). The filter lists are by their
maintainers (EasyList authors, Raymond Hill and the uBlock Origin contributors, Peter Lowe, the
malware list authors). uBlock Origin is by Raymond Hill and contributors (GPL-3.0). All are credited in
`CREDITS.md`, `NOTICE` and `chrome://credits`.
