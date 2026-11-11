# Network contacts (ROADMAP S.10)

Every host a fresh Thoron profile contacts on its own, and why. Measured with
[`tools/qa/netlog_hosts.py`](../../tools/qa/netlog_hosts.py): headless, throwaway profile, one local
page on 127.0.0.1, no user action, Chromium's network log on. Hosts the user reaches by browsing are
not listed.

## Thoron 156 (first measurement, 2026-11-09)

Build: Thoron 156.0.8078.28, Windows x64 AVX2, upstream build settings. 90 seconds.

| Host | Log entries | What contacts it | Thoron's plan |
|---|---|---|---|
| `optimizationguide-pa.googleapis.com` | 83 | Chromium's optimization guide: downloads on-device models (shopping and education classifiers, permission predictions, language detection, phishing detection), using the Google API key the upstream key patch compiles in (ROADMAP **L.8**) | turn off (ROADMAP **S.15**) |
| `update.googleapis.com` | 47 | Component updater: security data (certificate revocations, safety lists), Widevine on demand | keep: it delivers security data |
| `edgedl.me.gvt1.com` | 7 | Component updater downloads | keep, as above |
| `chromewebstore.googleapis.com` | 24 | Extensions that other programs installed on the test PC had registered for Google Chrome in the Windows registry; every Chromium-based browser reads that key. They arrive **disabled** until the user approves them. uBlock Origin itself comes from the bundled copy, not the Web Store | decide whether Thoron should skip these until the user asks (ROADMAP **P2.16**) |
| `clients2.google.com`, `clients2.googleusercontent.com` | 18, 12 | Downloads and update checks for those registry-registered extensions | as above |
| `www.google.com` | 20 | A Google search feature fetched in the background (`/async/folae`) | turn off what is not needed (ROADMAP **S.15**) |
| `accounts.google.com` | 12 | Google sign-in cookie check at start-up (`ListAccounts`) | turn off (ROADMAP **S.15**) |
| `cdn.jsdelivr.net`, `ublockorigin.pages.dev`, `malware-filter.gitlab.io`, `pgl.yoyo.org`, `publicsuffix.org` | 42, 25, 12, 12, 12 | uBlock Origin downloading its filter lists | keep: this is the ad and malware blocking the user wants |

## Thoron 158 (first build, 2026-11-09)

Build: Thoron 158.0.8127.30, Windows x64 AVX2, the reviewed build settings (`docs/build/RELEASE_ARGS.md`).
90 seconds. The same hosts as 156, for the same reasons: `optimizationguide-pa.googleapis.com` (78),
`update.googleapis.com` (37), `chromewebstore.googleapis.com` (22), `www.google.com` (20),
`clients2.google.com` (18), `accounts.google.com` (12), `clients2.googleusercontent.com` (12),
`edgedl.me.gvt1.com` (7), and uBlock Origin's filter lists (`ublockorigin.pages.dev`, `cdn.jsdelivr.net`,
`curbengh.github.io`, `pgl.yoyo.org`, `publicsuffix.org`). The Google contacts go away with ROADMAP
**S.15**, **P2.16** and **L.8**; this list is measured again before the first release.

## Native ad blocking list updates (ROADMAP P5.15, off by default)

When the `ThoronNativeAdblock` feature is on, the browser checks its filter lists at most every 4 days
(the first check 2 minutes after start, then an hourly look at whether one is due). It fetches the
same files uBlock Origin uses, from the same hosts, each with one fallback:

| List | Host (fallback) |
|---|---|
| EasyList, EasyPrivacy | `ublockorigin.github.io` (`ublockorigin.pages.dev`) |
| uBlock filters, privacy, badware, quick fixes, unbreak | `ublockorigin.github.io` (`ublockorigin.pages.dev`) |
| URLhaus malware list | `malware-filter.gitlab.io` (`curbengh.github.io`) |

Each request is a plain HTTPS GET through the browser's own network context: no profile, no cookies
or other credentials, not stored in the HTTP cache, no identifiers. A redirect away from HTTPS is
refused. What happens to a downloaded list is in the native ad-blocking design, section 6.

## Re-measuring

```powershell
py -3 -I tools/qa/netlog_hosts.py --browser <out dir>\thoron.exe --work <scratch folder> --seconds 90 `
    --label "Thoron <version>"
```
