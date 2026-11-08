# Release build configuration (ROADMAP P2.17)

A Thoron release `args.gn` is upstream Thorium's args file for the platform
(`other/AVX2/win_AVX2_args.gn` on Windows, `other/AVX2/AVX2_args.gn` on Linux) with Thoron's
deliberate choices applied by [`tools/build/release_args.py`](../../tools/build/release_args.py).
The tool writes each reason as a `# Thoron:` comment on the line it sets, and `check` refuses an
args file that differs from these choices or carries Google API keys:

```powershell
py -3 -I tools/build/release_args.py compose --upstream <upstream>\other\AVX2\win_AVX2_args.gn `
    --platform win --source "gz83 <commit> other/AVX2/win_AVX2_args.gn" --out out\<dir>\args.gn
py -3 -I tools/build/release_args.py check --args out\<dir>\args.gn --platform win
```

Reviewed on 2026-11-09 against Chromium 158.0.8127.30 with the upstream Thorium 156.0.8078.80
args, using the values GN resolves for the release output folder (`gn args <out> --list=<name>`).

## Set by Thoron

| Argument | Upstream | Thoron | Why |
|---|---|---|---|
| `enable_rlz` | `true` (Windows) | `false` | RLZ is Google's promotion-tracking library (install and first-search pings with a brand code). Chromium turns it on only for Google Chrome; no Thorium patch needs it. |
| `enable_cdm_storage_id` | `true` (Windows) | `false` | Gives DRM modules a per-device storage ID. It needs a private key that only Google Chrome has; with the empty key upstream uses, the ID is always empty, so the setting only made the browser read the machine ID. Chromium turns it off for non-Google builds. |
| `bundle_widevine_cdm` | `true` | `false` | Google's proprietary Widevine module may not be redistributed. Chromium downloads it from Google's component updater when a site needs DRM (ROADMAP **P2.6**). |
| `use_official_google_api_keys` | not set | `false` | Never build with Google's own API keys. Thoron ships no Google API keys, so keyed Google services (sync, Google sign-in, Google's geolocation and translation APIs) are off. |

## Kept from upstream, now checked

| Argument | Value | Why |
|---|---|---|
| `enable_widevine` | `true` | DRM video sites keep working; the module is only fetched on demand. |
| `enable_reporting` | `false` | Web pages cannot make the browser send Reporting API or Network Error Logging reports, a channel sites can use to observe users' networks. |
| `enable_hangout_services_extension` | `false` | No hidden component extension that gives Google Meet pages extra system information. |
| `disable_fieldtrial_testing_config` | `true` | No Google field-trial configuration is compiled in; features keep their coded defaults. |
| `google_api_key`, `google_default_client_id`, `google_default_client_secret` | not set | `check` refuses any non-empty value. |

## Chromium defaults reviewed and kept

These add no hidden contact in a Thoron build, or contact a server only when the user uses the
feature. Every endpoint will be listed in `docs/security/NETWORK.md` (ROADMAP **S.10**).

| Argument | Value | Note |
|---|---|---|
| `is_chrome_branded` | `false` | No Google Chrome-only code or services. |
| `build_with_internal_optimization_guide`, `enable_ml_internal` | `false` | Google's internal on-device models are not built in. |
| `enable_updater` | `false` | Google's updater is not built; Thoron has its own (ROADMAP **P3**). |
| `enable_service_discovery`, `enable_mdns` | `true` | Local network only: finding printers and Cast devices. |
| `safe_browsing_mode` | `1` | The Safe Browsing code is built, but without a Google API key it cannot query Google. Choosing a working Safe Browsing setup is ROADMAP **S.14**. |
| `enable_lens_desktop`, `enable_compose`, `enable_on_device_translation`, `enable_screen_ai_service` | `true` | Only when the user starts the feature; models or components come from Google's component updater. Reviewed again with S.10. |
| `enable_background_mode`, `enable_supervised_users`, `enable_remoting`, `enable_print_preview`, `enable_vr`, `enable_openxr` | `true` | No network contact of their own. |
| `enable_bound_session_credentials`, `enable_device_bound_sessions` | `true` | Security features: sign-in cookies bound to the device. |
