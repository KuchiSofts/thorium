# Audit toolkit

Security checks that run **before every upstream merge and before every release**. These tools only
read; they never execute anything from the code or archives they inspect. They use the Python standard
library only.

| Tool | Answers | Example |
|---|---|---|
| `audit_diff.py` | What does a revision **add** compared with a base revision? It reports binaries, network endpoints, suspicious code patterns, and changes to security features. | `py -3 -I tools/audit/audit_diff.py . main gz83/M158 --section all` |
| `crx_id.py` | Is a bundled extension genuine? Its declared ID must equal the ID derived from its signing key. | `py -3 -I tools/audit/crx_id.py uBlock0_1.75.0.chromium.crx` |
| `compare_release.py` | Is an installed or extracted copy byte-identical to the published release ZIP? | `py -3 -I tools/audit/compare_release.py Thorium_AVX2_x.zip "%LOCALAPPDATA%\Thorium\Application"` |

## `audit_diff.py` categories

| Category | Looks for | `--strict` fails on it |
|---|---|---|
| `remote_exec` | download-and-run (`curl … \| sh`, `Invoke-WebRequest`, `DownloadString`, `certutil -urlcache`) | yes |
| `encoded_payload` | base64 / `-EncodedCommand` blobs, very long encoded strings | no (review) |
| `dynamic_code` | `eval(`, `new Function(`, `shell=True`, `os.system(` | yes |
| `persistence` | Run keys, scheduled tasks, cron, systemd enable, sudoers | yes |
| `security_disabled` | `--no-sandbox`, `disable-web-security`, certificate bypasses, remote debugging | yes |
| `credentials` | API keys, private keys, hard-coded passwords and tokens | no (review) |
| `mining_telemetry` | crypto-miners and third-party analytics endpoints | yes |
| `self_update` | update and download URLs, Omaha | no (review) |

Non-image binaries that were added or modified also fail `--strict`.

A `--strict` failure is not automatically malicious. For example, upstream legitimately updates
Google's Widevine binaries. It means **a human must review each finding** before the merge or release
proceeds. Record the outcome in the pull request or release notes.

## Tests

```shell
py -3 -I -m unittest discover -s tools -t . -p "test_*.py" -v
```
