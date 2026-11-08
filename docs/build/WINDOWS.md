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

## 7. Build

The release configuration is upstream's `other\AVX2\win_AVX2_args.gn` with one change:
`bundle_widevine_cdm = false`, so Google's proprietary Widevine module is never bundled. Widevine
itself stays enabled, and the browser downloads it from Google when a site needs it.

```powershell
cd $env:THORON_BUILD_ROOT\chromium\src
$outDir = 'out\thoron-m156-avx2'
New-Item -ItemType Directory -Force $outDir | Out-Null
(Get-Content $env:THORON_BUILD_ROOT\upstream-M156\other\AVX2\win_AVX2_args.gn) `
    -replace '^\s*bundle_widevine_cdm\s*=\s*true\s*$', 'bundle_widevine_cdm = false' |
    Set-Content -Encoding Ascii "$outDir\args.gn"
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

The outputs keep upstream's names for now: `thorium.exe`, `chrome.dll` and the installer
`thorium_AVX2_mini_installer.exe`.

**Installer files.** Upstream's setup copies `thor_ver` (the variant name the Thorium updater reads)
and the Thorium icons into a build folder named `out\thorium`. When you build in another folder,
copy them before building `mini_installer`, or the installer fails with "unspecified error, code 7"
and rolls back:

```powershell
foreach ($f in 'thor_ver', 'thorium.ico', 'thorium.svg', 'thorium_shell.ico') {
    Copy-Item "out\thorium\$f" "$outDir\$f"
}
```

The prebuilt `pak_mingw*.exe` tools in `out\thorium` are deliberately not copied: they are
unverified binaries (ROADMAP **L.6**) and the browser does not need them.

**Upgrading an existing Thorium.** Before installing over an existing Thorium, back up the whole
`%LOCALAPPDATA%\Thorium` folder and check the new version on an offline copy of the profile with
`tools/qa/profile_check.py` (ROADMAP **Q.7**). A profile used by a newer version cannot be opened by
an older one; going back means restoring the backup. The installer first asks "Do you want to
install Thorium?".

## 8. Check the build

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
py -3 -I tools\build\smoke.py --browser <out dir>\thorium.exe --work $env:THORON_BUILD_ROOT\smoke\win `
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
