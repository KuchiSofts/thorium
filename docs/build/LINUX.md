# Building Thoron on Linux (Ubuntu 24.04, in WSL2 or native)

This guide reproduces the Linux x64 AVX2 build. Every step was verified on the reference machine in a
dedicated Ubuntu 24.04 WSL2 distro (ROADMAP **P1.2**, **P1.5**). On a native Ubuntu 24.04 machine,
skip the WSL parts.

## What you need

- Ubuntu 24.04 LTS (x64), at least 200 GB free on its disk, 32 GB of RAM at least (the release
  build used 16 parallel jobs within 44 GB).
- Git and Python 3 (both come with Ubuntu).

## 1. A dedicated WSL distro (Windows only)

Keep the build away from any distro you already use:

```powershell
wsl --install -d Ubuntu-24.04 --location J:\thoron-build\wsl\Ubuntu-24.04 --no-launch
wsl -d Ubuntu-24.04 -u root -- useradd -m -s /bin/bash thoron
```

In the distro's `/etc/wsl.conf`, make `thoron` the default user and keep the Windows `PATH` out of
Linux, which would otherwise confuse the build:

```ini
[user]
default=thoron

[interop]
appendWindowsPath=false
```

The `thoron` user has no password and no `sudo`; the one step that needs root is run with
`wsl -d Ubuntu-24.04 -u root`.

WSL limits its memory (24 GB on the reference machine). For the build, raise it only while
building, with a byte-exact backup of `.wslconfig`, then restore it:

```powershell
py -3 -I tools\build\wslconfig.py raise          # prints the backup file name
wsl --shutdown                                   # stops every WSL distro briefly
# ... build ...
py -3 -I tools\build\wslconfig.py restore <backup file>
wsl --shutdown
```

## 2. depot_tools and the Chromium source

As `thoron`, in `~/thoron-build`:

```bash
export DEPOT_TOOLS_UPDATE=0 PATH="$HOME/thoron-build/depot_tools:$PATH"
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git ~/thoron-build/depot_tools
~/thoron-build/depot_tools/ensure_bootstrap
mkdir -p ~/thoron-build/chromium && cd ~/thoron-build/chromium
```

Create `.gclient` exactly as for Windows ([`WINDOWS.md`](WINDOWS.md#5-chromium-source)), but with
`target_os = ["linux"]`, then:

```bash
gclient sync --nohooks --no-history -D
```

The sync took 11 minutes on the reference machine (31 GB). Then install Chromium's build
dependencies as root, and run the hooks and the arm64 sysroot as `thoron`:

```bash
sudo ./src/build/install-build-deps.sh --no-prompt --no-chromeos-fonts      # as root in WSL: no sudo
gclient runhooks
src/build/linux/sysroot_scripts/install-sysroot.py --arch=arm64
```

Check that the toolchain works on unmodified Chromium, for both architectures:

```bash
cd src
gn gen out/stock-check-x64 --args='is_debug=false is_component_build=false target_cpu="x64"'
gn gen out/stock-check-arm64 --args='is_debug=false is_component_build=false target_cpu="arm64"'
```

## 3. Upstream overlay and patches

Copy the upstream M156 tree and this repository into the Linux file system with `git archive`
(no history), and apply it with the same pipeline as on Windows:

```bash
python3 -I tools/build/pipeline.py apply --tree ~/thoron-build/upstream-M156 \
    --src ~/thoron-build/chromium/src --profile avx2 --log ~/thoron-build/logs/apply-M156-linux.log
```

Expected: 0 rejects, 149 of 152 patches. Some upstream files are stored with Windows line endings;
that is how upstream ships them, so do not convert them.

## 4. Build

The release configuration is upstream's `other/AVX2/AVX2_args.gn` with `bundle_widevine_cdm = false`
(Widevine is downloaded from Google at runtime instead of being bundled):

```bash
python3 -I tools/build/pipeline.py preflight --root ~/thoron-build --need-gb 200 --require-wsl-memory-gb 40
autoninja -j 16 -C out/thoron-m156-avx2 chrome
```

*Build time and size: being measured (ROADMAP **P1.10**).*

## 5. Check the build

Run the smoke test with a fresh profile. On Linux it proves the sandbox from `/proc`: every renderer
must run under a seccomp-BPF filter and in its own PID namespace.

```bash
python3 -I tools/build/smoke.py --browser out/thoron-m156-avx2/thorium --work ~/thoron-build/smoke/linux \
    --jxl-sample third_party/blink/web_tests/external/wpt/jpegxl/resources/3x3_srgb_lossless.jxl
```

Never start a test build with `--no-sandbox`.
