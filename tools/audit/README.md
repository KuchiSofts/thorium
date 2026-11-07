# Audit toolkit

Security checks that run **before every upstream merge and before every release**. These tools only
read; they never execute anything from the code or archives they inspect. They use the Python standard
library only.

| Tool | Answers | Example |
|---|---|---|
| `audit_diff.py` | What does upstream **add**? It reports binaries (including executables disguised as images), submodule and `.gitmodules` changes, network endpoints, suspicious code patterns, and changes to security features. | `py -3 -I tools/audit/audit_diff.py . "$(git merge-base HEAD gz83/M158)" gz83/M158 --strict` |
| `crx_id.py` | Is a bundled extension genuine? It verifies the CRX3 **RSA signature** and checks that the signing key matches the expected extension ID. | `py -3 -I tools/audit/crx_id.py uBlock0_1.75.0.chromium.crx --expect fkgkibajhfbepljeaefdnfnegdcjomkh` |
| `binary_policy.py` | Does the repository carry only what it may? It fails on any prebuilt executable, library, package or archive (found by content, so renamed files are caught) that has no allowlist entry with its SHA-256, licence and source, and always on proprietary blobs such as the Widevine CDM. | `py -3 -I tools/audit/binary_policy.py` |
| `compare_release.py` | Is an installed or extracted copy byte-identical to the published release ZIP? It warns about any extra executable, which could be DLL side-loading. | `py -3 -I tools/audit/compare_release.py Thorium_AVX2_x.zip "%LOCALAPPDATA%\Thorium\Application" --strict` |

## `audit_diff.py`

### Built for hostile input

`audit_diff.py` is designed so a crafted change cannot hide from it:
- **File list:** taken from `git diff --raw -z`.
- **File contents:** read by blob ID. They never go through file names, and never through the
  user's diff or `textconv` settings.
- **Added lines in modified files:** taken from a blob-to-blob diff, parsed by the line counts each
  hunk header declares.
- **Line splitting:** text is split on `\n` only, so form feeds and Unicode line separators cannot
  hide code.
- **Translation files:** `.xtb` files are skipped as non-executable noise.

### Categories

| Category | Looks for | `--strict` fails on it |
|---|---|---|
| `remote_exec` | download-and-run: `curl … \| sh` (also with `sudo`), `bash <(curl …)`, `iex`/`irm`/`iwr`, `.DownloadString(`, `certutil -urlcache`, `bitsadmin`, `mshta` | yes |
| `dynamic_code` | `eval(`, `new Function(`, `shell=True`, `os.system(`, `powershell -EncodedCommand …` | yes |
| `persistence` | Run/RunOnce keys, scheduled tasks, cron, `systemctl [--user] enable`, shell rc files, autostart, sudoers | yes |
| `security_disabled` | `--no-sandbox`, `disable-web-security`, certificate bypasses, remote debugging | yes |
| `mining_telemetry` | crypto-miners and third-party analytics endpoints | yes |
| `adult_content` | adult or NSFW terms and sites in added text **and in file names** (term list stored ROT13-encoded) | yes |
| `encoded_payload` | base64 decoding and very long encoded strings | no (review) |
| `credentials` | API keys, private keys, hard-coded passwords and tokens | no (review) |
| `self_update` | update and download URLs, Omaha | no (review) |

`--strict` also fails on:
- any added, modified or type-changed **non-image binary**;
- any **submodule** change;
- any **`.gitmodules`** change.

### Network endpoints

Endpoints on hosts where anyone can publish files are reported together with the owner or bucket:
- `raw.githubusercontent.com/<owner>`, `github.com/<owner>`;
- `storage.googleapis.com/<bucket>`;
- Google Docs, Drive and Sites.

Known upstream owners are not reported.

A `--strict` failure is not automatically malicious. For example, upstream updates Google's
Widevine binaries, which `binary_policy.py` keeps out of this repository entirely. It means **a human must review each finding** before the merge or release
proceeds. Record the outcome in the pull request or release notes.

## Tests

```shell
py -3 -I -m unittest discover -s tools -t . -p "test_*.py" -v
```

The tests include regression cases for every evasion found in review: header-like content lines,
quoted file names, Unicode line separators, `diff.noprefix`, submodules, symlink-to-binary type
changes, disguised images, and forged CRX signatures.
