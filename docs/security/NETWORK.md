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
| `chromewebstore.googleapis.com` | 24 | uBlock Origin installed from the Chrome Web Store by Thorium's default apps | replace with the bundled, pinned copy (ROADMAP **P2.16**) |
| `clients2.google.com`, `clients2.googleusercontent.com` | 18, 12 | The same Web Store install, and extension update checks | as above |
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

## Re-measuring

```powershell
py -3 -I tools/qa/netlog_hosts.py --browser <out dir>\thoron.exe --work <scratch folder> --seconds 90 `
    --label "Thoron <version>"
```
