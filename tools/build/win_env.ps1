# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
# Thoron Windows build environment. Dot-source it in a PowerShell window:
#     . .\tools\build\win_env.ps1            (build root defaults to J:\thoron-build)
# It changes only this shell's environment. Nothing machine-wide, and the user's global git config is
# never modified: a build-only git config includes it (so hooks still apply) and overrides only
# the settings a Chromium checkout needs.
param([string]$BuildRoot = $(if ($env:THORON_BUILD_ROOT) { $env:THORON_BUILD_ROOT } else { 'J:\thoron-build' }))

$env:THORON_BUILD_ROOT = $BuildRoot
foreach ($sub in 'tmp', 'vpython') { New-Item -ItemType Directory -Force -Path (Join-Path $BuildRoot $sub) | Out-Null }
$env:TEMP = Join-Path $BuildRoot 'tmp'          # keep temporary build files off C:
$env:TMP = $env:TEMP
$env:VPYTHON_VIRTUALENV_ROOT = Join-Path $BuildRoot 'vpython'
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = '0'            # use the locally installed Visual Studio
$env:DEPOT_TOOLS_UPDATE = '0'                   # pinned: update depot_tools on purpose (git pull), never silently

$depot = Join-Path $BuildRoot 'depot_tools'
if (-not (($env:PATH -split ';') -contains $depot)) { $env:PATH = "$depot;$env:PATH" }

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vs = & $vswhere -version '[18.0,19.0)' -products * -property installationPath | Select-Object -First 1
    if ($vs) { $env:vs2026_install = $vs }
}

$gitConfig = Join-Path $BuildRoot 'gitconfig'
# The user's own global config, found the way git finds it (so their hooks always apply).
$xdg = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME '.config' }
$userConfig = if ($env:GIT_CONFIG_GLOBAL -and ($env:GIT_CONFIG_GLOBAL -ne $gitConfig)) { $env:GIT_CONFIG_GLOBAL }
              elseif (Test-Path (Join-Path $HOME '.gitconfig')) { Join-Path $HOME '.gitconfig' }
              elseif (Test-Path (Join-Path $xdg 'git\config')) { Join-Path $xdg 'git\config' }
              else { Join-Path $HOME '.gitconfig' }
$content = @"
[include]
	path = "$($userConfig -replace '\\', '/')"
[core]
	autocrlf = false
	filemode = false
	longpaths = true
	preloadindex = true
	fscache = true
"@
# UTF-8 without a BOM: a non-ASCII home path must not turn into '?', or git would skip the include.
[IO.File]::WriteAllText($gitConfig, ($content -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))
$env:GIT_CONFIG_GLOBAL = $gitConfig

Write-Host ("Thoron build environment: root={0}  vs2026={1}  depot_tools first on PATH" -f $BuildRoot, $(if ($env:vs2026_install) { $env:vs2026_install } else { '(not found yet)' }))
