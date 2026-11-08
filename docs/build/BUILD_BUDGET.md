# Build-time budget

How long each release build takes on the reference machine, measured against the security-release
targets in [`ROADMAP.md`](../../ROADMAP.md#release-policy) (G2): a release within **7 days** of a Chrome
fix for an in-the-wild exploit, and within **14 days** of a new Chrome major version. Every release
variant is a separate full build (ROADMAP **P1.10**).

## Reference machine

- 16-core / 32-thread desktop CPU (AMD Ryzen 9 7950X), 64 GB RAM (63 GB usable).
- Build drive: SATA SSD, NTFS, not cloud-synced. Windows 11, Microsoft Defender real-time
  protection on.

## Measured builds

| Variant | Chromium | Configuration | Parallel jobs | Build time | Output size | Date |
|---|---|---|---|---|---|---|
| Windows x64 AVX2 | 156.0.8078.28 | release (official, ThinLTO, PGO); upstream `win_AVX2_args.gn` without bundled Widevine | 32, then 12 | 2 h 35 min (9,304 s) | 12.4 GB | 2026-11-07 |
| Linux x64 AVX2 | 156.0.8078.28 | release (official, ThinLTO, PGO); upstream `AVX2_args.gn` without bundled Widevine; WSL2 Ubuntu 24.04 | 16, then 10 | 2 h 37 min (about 9,440 s) | 9.6 GB | 2026-11-08 |

Other steps, measured on the same machine:

| Step | Windows | Linux (WSL2) |
|---|---|---|
| Chromium source sync (`--no-history`) | 8 min (27 GB) | 11 min (31 GB) |
| Build dependencies, hooks and sysroots | 2 min | 7 min |
| Upstream overlay and 149 patches | 1 min | 1 min |
| `gn gen` | 18 s | 6 s |

## What the first build taught us

- **The CPU is the limit.** During compilation the CPU stayed at 100% while the build drive was
  almost idle; Defender's own process used about 2% of the CPU. A faster disk would not help much;
  more cores would.
- **Memory caps the parallelism.** With 32 parallel jobs, the heaviest compile steps plus about
  17 GB held by other WSL workloads exhausted the 63 GB of RAM, and the build was stopped at 96% of
  compilation. On this machine, while other WSL services run, build with `-j 12`. A stopped build
  loses nothing: running the same command again continues where it stopped.
- **WSL memory must be shared carefully.** The Linux build runs in the WSL virtual machine, which
  also holds other WSL services. With a 44 GB WSL limit and 16 jobs, Windows itself ran low on
  memory because WSL kept its file cache. What worked: a 36 GB limit, 32 GB of swap on the build
  drive, `autoMemoryReclaim=dropCache` (WSL returns its cache to Windows) and 10 jobs, all set
  only for the build and restored afterwards (`tools/build/wslconfig.py`).
- **The upstream build needs the network once.** It downloads the bundled uBlock Origin package
  from GitHub (pinned by SHA-256). When GitHub answered HTTP 504, the build stopped; a copy with
  the pinned hash, placed in the output folder, let it continue. Thoron will bundle a local,
  verified copy instead (ROADMAP **P2.16**).
- **The final link is short.** Linking `chrome.dll` with ThinLTO took only a few minutes.
- **Development is much faster.** Release builds are only needed for releases. Day-to-day work uses
  development builds without ThinLTO and PGO, which rebuild only changed files.

## Plan

Based on both measured builds (Windows and Linux AVX2, about 2.5 hours each).

- **Order per release:** Windows x64 AVX2 first (most users), then Linux x64 AVX2, then the SSE4
  variants, then ARM64.
- **Estimate:** at about 2.5 hours per variant (measured for both OSes), four x64 variants take 10 to 12 hours on one
  machine, so they fit in one night of unattended builds. That is far inside the 7-day target; the
  real risk to G2 is rebasing patches onto a new Chromium, not compile time.
- **To measure next:** a Windows Dev Drive for the build folder, where Defender keeps scanning but
  without blocking each file access.
- **Second machine:** not needed for the current matrix; reconsider if ARM64 builds or more
  variants push a release past one night.
