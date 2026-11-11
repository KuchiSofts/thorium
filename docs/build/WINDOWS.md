# Building Thoron on Windows 11

This guide reproduces the Windows x64 AVX2 build from a clean Windows 11 machine. Every step was
verified on the reference machine while making the first build (ROADMAP **P1.1**, **P1.3**,
**P1.4**). Following it on a second, fresh machine is ROADMAP **P1.9**.

Run every command from a PowerShell window in the root of a Thoron checkout unless a step says
otherwise.

## What you need

- Windows 11 x64 and administrator rights for the one-time installs.
- A local NTFS drive with at least 250 GB free. The build folder must not be inside a cloud-synced
  folder (Google Drive, OneDrive, Dropbox and so on), and its path must not contain spaces. The
  examples use `J:\thoron-build`; set `THORON_BUILD_ROOT` to use another folder.
- 32 GB of RAM at least; 64 GB is recommended.
- Git for Windows and Python 3 with the `py` launcher.
- Visual Studio 2026 (version 18.x) Community or higher, with:
  - the **Desktop development with C++** workload and its recommended components
    (`Microsoft.VisualStudio.Workload.NativeDesktop`);
  - **C++ ATL and MFC** (`Microsoft.VisualStudio.Component.VC.ATLMFC`).
- Windows SDK 10.0.28000 or newer, including **Debugging Tools for Windows** 10.0.26100.3323 or
  newer. The standalone SDK installer includes them.

Download installers only from Microsoft, and check every installer's signature before you run it:

```powershell
Get-AuthenticodeSignature .\vs_community.exe | Format-List Status, SignerCertificate
```

`Status` must be `Valid`, and the signer must be Microsoft Corporation.

## 1. Install Visual Studio and the Windows SDK

Each installer shows one administrator prompt.

```powershell
.\winsdksetup.exe /features + /quiet /norestart /ceip off
.\vs_community.exe --add Microsoft.VisualStudio.Workload.NativeDesktop `
    --add Microsoft.VisualStudio.Component.VC.ATLMFC --includeRecommended --passive --norestart --wait
```

To keep the system drive free, add `--installPath <folder>` to the Visual Studio command. An existing
Visual Studio 2022 can stay installed. Exit code 3010 means the install succeeded and Windows asks
for a restart; restart before the first build.

Check the result:

```powershell
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -version "[18.0,19.0)" -property installationVersion
Test-Path "${env:ProgramFiles(x86)}\Windows Kits\10\Include\10.0.28000.0"
(Get-Item "${env:ProgramFiles(x86)}\Windows Kits\10\Debuggers\x64\cdb.exe").VersionInfo.ProductVersion
```

The first command must print a version starting with `18.`, the second `True`, and the third
10.0.26100.3323 or newer.

## 2. Microsoft Defender

Keep real-time protection on. The build needs no antivirus exclusion.

One Attack Surface Reduction (ASR) rule can block the build: "Block executable files from running
unless they meet a prevalence, age, or trusted list criterion"
(`c1db55ab-c21a-4637-bb3f-a12568109d35`). depot_tools downloads tools that are new and unsigned, and
the build creates its own, so this rule stops them. The symptom is
`Failed to bootstrap or update CIPD client ... Access is denied`, with event 1121 in the
*Microsoft-Windows-Windows Defender/Operational* log.

Check the rule's mode (1 means block):

```powershell
$p = Get-MpPreference
0..(@($p.AttackSurfaceReductionRules_Ids).Count - 1) |
    Where-Object { $p.AttackSurfaceReductionRules_Ids[$_] -eq 'c1db55ab-c21a-4637-bb3f-a12568109d35' } |
    ForEach-Object { $p.AttackSurfaceReductionRules_Actions[$_] }
```

If it prints `1`, exclude only the build folder, and only from this one rule. Run this in an
administrator PowerShell:

```powershell
Add-MpPreference -AttackSurfaceReductionRules_RuleSpecificExclusions_Id c1db55ab-c21a-4637-bb3f-a12568109d35 `
    -AttackSurfaceReductionRules_RuleSpecificExclusions J:\thoron-build
```

Every other ASR rule, and antivirus scanning, stay active, including inside the build folder. Do not
switch the rule to audit mode or turn it off.

## 3. depot_tools and the build environment

`tools/build/win_env.ps1` prepares the current PowerShell window only; it changes nothing
machine-wide. It:

- sets `THORON_BUILD_ROOT` (default `J:\thoron-build`);
- moves `TEMP` and `TMP` into the build folder, to keep build files off the system drive;
- puts depot_tools first on `PATH`;
- uses the installed Visual Studio (`DEPOT_TOOLS_WIN_TOOLCHAIN=0`, `vs2026_install`);
- pins depot_tools (`DEPOT_TOOLS_UPDATE=0`); update it on purpose with `git pull` in its folder;
- writes a build-only git config that includes your own (so your hooks still run) and adds the
  settings a Chromium checkout needs: `core.autocrlf=false`, `core.filemode=false`,
  `core.longpaths=true`, `core.preloadindex=true`, `core.fscache=true`.

```powershell
. .\tools\build\win_env.ps1
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git $env:THORON_BUILD_ROOT\depot_tools
gclient --version
```

The first `gclient` run downloads its own tools (CIPD client, Python, Git) and should print the
`gclient` help text with exit code 0.

## 4. Preflight

```powershell
py -3 -I tools\build\pipeline.py preflight --root $env:THORON_BUILD_ROOT --need-gb 250
```

Expected: `preflight: OK`. It checks free space, cloud-synced paths and drives, and spaces in the
path.

## 5. Chromium source

Create `<build root>\chromium\.gclient` pinned to the Chromium release:

```python
solutions = [
  {
    "name": "src",
    "url": "https://chromium.googlesource.com/chromium/src.git@refs/tags/156.0.8078.28",
    "managed": False,
    "custom_deps": {},
    "custom_vars": {"checkout_pgo_profiles": True},
  },
]
target_os = ["win"]
```

Then, in the same `win_env` window:

```powershell
cd $env:THORON_BUILD_ROOT\chromium
gclient sync --nohooks --no-history -D
gclient runhooks
Get-Content src\chrome\VERSION
```

`--no-history` fetches only the pinned revision of each repository, without git history, which
makes the download much smaller. `checkout_pgo_profiles` downloads Chromium's profile-guided
optimisation data, which the release build uses. `chrome\VERSION` must read `156.0.8078.28`.
On the reference machine the sync took 8 minutes, the hooks 2 minutes, and the tree is 27 GB.

Check that the toolchain works on unmodified Chromium:

```powershell
cd src
gn gen out\stock-check --args="is_debug=false is_component_build=false"
Remove-Item -Recurse -Force out\stock-check
```

Expected: `Done. Made ... targets`.

## 6. Upstream Thorium overlay and patches

Phase P1 first reproduces upstream Thorium M156: tag `M156.0.8078.28` of
[gz83/thorium](https://github.com/gz83/thorium), commit `de9a1bc6`. Check it out into its own folder
as a local worktree of your Thoron clone; nothing from it is ever pushed. Run these in the `win_env`
window, so the patches keep their LF line endings:

```powershell
git fetch --no-tags https://github.com/gz83/thorium.git refs/tags/M156.0.8078.28
git worktree add --detach $env:THORON_BUILD_ROOT\upstream-M156 FETCH_HEAD
git -C $env:THORON_BUILD_ROOT\upstream-M156 rev-parse HEAD
py -3 -I tools\build\pipeline.py apply --tree $env:THORON_BUILD_ROOT\upstream-M156 `
    --src $env:THORON_BUILD_ROOT\chromium\src --profile avx2 --log $env:THORON_BUILD_ROOT\logs\apply-M156-win.log
```

The commit must start with `de9a1bc6`. Expected: `upstream overlay and patch series applied: 0 rejects`,
in about a minute. With the `avx2` profile, 149 of the 152 patches apply; the other 3 are only for
the `sse2` and `raspi` profiles. The wrapper stops on any rejected hunk and keeps the full log.

The upstream overlay includes Google's proprietary Widevine binaries, which upstream's setup copies
into the local checkout. Thoron never bundles or redistributes them (ROADMAP **P2.6**).

## 7. Thoron identity

Turn the upstream Thorium tree into Thoron. The tool changes only what makes the browser its own
product (name, icons, program and installer file names, install and profile folder, registry, app
ID, ProgIDs, COM class IDs) and stops without changing anything if an expected spot is missing.
Running it again changes nothing.

```powershell
py -3 -I tools\build\thoron_identity.py --src $env:THORON_BUILD_ROOT\chromium\src --dry-run
py -3 -I tools\build\thoron_identity.py --src $env:THORON_BUILD_ROOT\chromium\src
```

Expected on M156: about 610 files (575 string and translation files, 24 icons, the install modes,
`BRANDING` and the 12 build and installer files that name the program file). The COM interface IDs
are still upstream's (ROADMAP **P2.19**), so install Thoron per user only.

## 8. Build

The release configuration is upstream's `other\AVX2\win_AVX2_args.gn` with Thoron's privacy
choices applied by `tools/build/release_args.py` (no RLZ tracking library, no bundled Widevine,
no Google API keys; every choice and its reason is in [`RELEASE_ARGS.md`](RELEASE_ARGS.md)).
Widevine itself stays enabled, and the browser downloads it from Google when a site needs it.

```powershell
cd $env:THORON_BUILD_ROOT\chromium\src
$outDir = 'out\thoron-m156-avx2'
New-Item -ItemType Directory -Force $outDir | Out-Null
$repo = 'H:\path\to\thoron'   # this repository
py -3 -I "$repo\tools\build\release_args.py" compose --platform win `
    --upstream $env:THORON_BUILD_ROOT\upstream-M156\other\AVX2\win_AVX2_args.gn `
    --source "gz83 <commit> other/AVX2/win_AVX2_args.gn" --out "$outDir\args.gn"
py -3 -I "$repo\tools\build\release_args.py" check --platform win --args "$outDir\args.gn"
gn gen $outDir
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
autoninja -j 12 -C $outDir chrome mini_installer
```

- **Priority:** the build inherits the window's below-normal priority, so the PC stays usable.
- **Parallel jobs:** `-j 12` suits a 64 GB machine that also runs other heavy workloads such as WSL.
  Without `-j`, the build uses one job per CPU thread, which ran out of memory on the reference
  machine. If a build stops for any reason, run the same command again; it continues where it
  stopped.
- **Time:** about 2 hours 35 minutes on the reference machine, with a 12 GB output folder
  ([`BUILD_BUDGET.md`](BUILD_BUDGET.md)).

The outputs are `thoron.exe`, `chrome.dll` and the installer `thoron_AVX2_mini_installer.exe`.
The installer installs no Thorium-named file: the Thorium updater's `thor_ver` marker, the Thorium
icons and the content shell entries are left out, so nothing needs to be copied into the build
folder first. The prebuilt `pak_mingw*.exe` tools that upstream's setup copies into `out\thorium`
are not used either: they are unverified binaries (ROADMAP **L.6**) and the browser does not need
them.

**Installing Thoron next to Thorium.** `thoron_AVX2_mini_installer.exe --silent` installs Thoron
per user into `%LOCALAPPDATA%\Thoron` without asking, with its own folder, program file, registry
key, `App Paths` entry and ProgIDs, so Thorium is left exactly as it was and either one can be
uninstalled without affecting the other. To bring your Thorium profile over, close both browsers
and copy it with a verified copy:

```powershell
py -3 -I tools\migrate\import_profile.py --from "$env:LOCALAPPDATA\Thorium\User Data" --to "$env:LOCALAPPDATA\Thoron\User Data"
```

Then use Thoron and keep Thorium closed as a backup: two copies of a profile used online at the
same time can make sites sign one of them out, and both sync as the same device.

**Moving over an install made before the rename.** Thoron builds from before ROADMAP **P2.20**
installed `thorium.exe` and took over Thorium's `App Paths` entry. After installing a newer build
over such an install (with Thoron closed and backed up), run this once:

```powershell
py -3 -I tools\migrate\exe_rename.py plan
py -3 -I tools\migrate\exe_rename.py apply --backup-dir "$env:USERPROFILE\ThoriumBackups\<date>_exe-rename"
```

The installer itself already updates Thoron's own shortcuts and registry entries. `plan` only shows
what is left to change. `apply` retargets any other shortcuts (desktop, Start menu, taskbar
pins, keeping their arguments), updates Thoron's own registry values, gives `App Paths\thorium.exe`
back to Thorium, and moves the old `thorium.exe` and the other Thorium-named leftovers into the
backup folder. It never touches `User Data` or Thorium. `exe_rename.py restore --backup-dir <same
folder>` undoes it.

**Upgrading an existing Thorium.** A profile used by a newer version cannot be opened by an older
one, so going back means restoring a backup. Never skip these steps (ROADMAP **Q.7**):

1. Close the browser completely (no `thorium.exe` or `thoron.exe` left in Task Manager).
2. Back up the whole `%LOCALAPPDATA%\Thorium` folder (program and `User Data`) and verify the copy.
3. Rehearse the update on a copy of the profile:

   ```powershell
   py -3 -I tools\qa\profile_rehearsal.py --browser <out dir>\thoron.exe `
       --user-data "$env:LOCALAPPDATA\Thorium\User Data" --work <private local folder> `
       --before-out <private local folder>\before.json
   ```

   The tool copies `User Data` to a new folder under the work folder, snapshots the copy
   (`tools\qa\profile_check.py`: counts only, nothing is decrypted), opens the copy with the new
   build **fully offline**, so it can neither sync nor make websites rotate your login cookies (which
   could sign out the real browser), lets it run for a minute, closes it the normal way, snapshots
   again and compares. A window with your tabs opens and closes by itself: do not use it. The last
   line must say that the new build kept everything. The copy is deleted whatever happened, and your
   real `User Data` is only read. A build that does not close when asked does not count as a pass.
4. Only then install over the real Thorium. The installer first asks "Do you want to install
   Thorium?".
5. When you have used the new version and closed it again, compare the real profile with the
   snapshot from before:
   `py -3 -I tools\qa\profile_check.py snapshot "$env:LOCALAPPDATA\Thorium\User Data" --out after.json`,
   then `py -3 -I tools\qa\profile_check.py compare before.json after.json` must report 1:1.

The tool refuses to start while the browser of that profile runs, or when the work folder is inside
the profile, inside a git repository or in a folder whose name looks cloud-synced. Tabs and tab
groups are compared only when the browser is set to continue where you left off; with `--headless`
(no window) they are not compared, and the tool says so. To look at the copy yourself instead, copy
`User Data` by hand, take the two snapshots with `profile_check.py`, and open the copy with:

```powershell
& <out dir>\thoron.exe --user-data-dir="<copy>\User Data" --no-first-run --no-default-browser-check `
    --disable-sync --disable-background-networking --disable-component-update `
    --proxy-server=http://127.0.0.1:9 --proxy-bypass-list="<-loopback>" `
    --host-resolver-rules="MAP * ~NOTFOUND" --force-webrtc-ip-handling-policy=disable_non_proxied_udp
```

Keep backups, profile copies and snapshots only on a local drive that is not cloud-synced, never in
a cloud folder or in this repository, and delete the profile copy when you are done: it contains
your cookies and saved passwords.

## 9. Check the build

Write the build record. It holds no personal paths; check it before sharing it.

```powershell
py -3 -I tools\build\pipeline.py buildinfo --root $env:THORON_BUILD_ROOT --src $env:THORON_BUILD_ROOT\chromium\src `
    --repo . --upstream-ref "gz83 M156.0.8078.28 de9a1bc6" --variant win-x64-avx2 `
    --args <out dir>\args.gn --toolchain toolchain.json --started <epoch> --finished <epoch> `
    --out <out dir>\BUILDINFO.json
```

`toolchain.json` lists the tool versions from the table below.

Then run the smoke test. It starts the browser with a fresh, throwaway profile, always with the
sandbox on, and checks JavaScript, WebGL, H.264, HEVC, AV1 and JPEG XL, and that nothing crashed:

```powershell
py -3 -I tools\build\smoke.py --browser <out dir>\thoron.exe --work $env:THORON_BUILD_ROOT\smoke\win `
    --jxl-sample $env:THORON_BUILD_ROOT\chromium\src\third_party\blink\web_tests\external\wpt\jpegxl\resources\3x3_srgb_lossless.jxl
```

Expected: `SMOKE: PASSED`.

## Tool versions of the reference build

| Tool | Version |
|---|---|
| Chromium | 156.0.8078.28 |
| Visual Studio Community 2026 | 18.11.12328.437 (MSVC 14.51.36231) |
| Windows SDK | 10.0.28000.2526 |
| Debugging Tools for Windows (`cdb.exe`) | 10.0.28000.2526 |
| depot_tools | `289a37bda` (2026-11-06) |
| GN | 2578 (`510ec7992c30`) |
| Siso (build runner) | 1.6.3 |
| Clang (Chromium's) | 24.0.0git (`86922d51225d`) |
| Rust (Chromium's) | 1.100.0-nightly (`1edd55dcf`, 2026-09-09) |
| Python | 3.12.8 |
| Git for Windows | 2.51.1 |

Every build also writes `BUILDINFO.json` next to its output with the exact versions it used
(ROADMAP **P1.6**).
