# Building Thoron on Windows 11

This guide reproduces the Windows x64 build from a clean Windows 11 machine. It is written while the
first reproducible build is being made (ROADMAP **P1.1**, **P1.3**, **P1.4**). Steps marked
*Pending* are added once they have been verified end to end.

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

*Pending (ROADMAP **P1.3**).*

## 7. Build

*Pending (ROADMAP **P1.4**).*

## Tool versions of the reference build

| Tool | Version |
|---|---|
| Chromium | 156.0.8078.28 |
| Visual Studio Community 2026 | 18.11.12328.437 (MSVC 14.51.36231) |
| Windows SDK | 10.0.28000.2526 |
| Debugging Tools for Windows (`cdb.exe`) | 10.0.28000.2526 |
| depot_tools | `289a37bda` (2026-11-06) |
| GN | 2578 (`510ec7992c30`) |
| Python | 3.12.8 |
| Git for Windows | 2.51.1 |

Every build also writes `BUILDINFO.json` next to its output with the exact versions it used
(ROADMAP **P1.6**).
