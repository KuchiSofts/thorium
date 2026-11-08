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
| Linux x64 AVX2 | 156.0.8078.28 | *pending (ROADMAP **P1.5**)* | | | | |

Other steps of the Windows build, measured the same night:

| Step | Time |
|---|---|
| Chromium source sync (`--no-history`) | 8 min (27 GB checkout) |
| `gclient runhooks` | 2 min |
| Upstream overlay and 149 patches | 1 min |
| `gn gen` | 18 s |

## What the first build taught us

- **The CPU is the limit.** During compilation the CPU stayed at 100% while the build drive was
  almost idle; Defender's own process used about 2% of the CPU. A faster disk would not help much;
  more cores would.
- **Memory caps the parallelism.** With 32 parallel jobs, the heaviest compile steps plus about
  17 GB held by other WSL workloads exhausted the 63 GB of RAM, and the build was stopped at 96% of
  compilation. On this machine, while other WSL services run, build with `-j 12`. A stopped build
  loses nothing: running the same command again continues where it stopped.
- **The final link is short.** Linking `chrome.dll` with ThinLTO took only a few minutes.
- **Development is much faster.** Release builds are only needed for releases. Day-to-day work uses
  development builds without ThinLTO and PGO, which rebuild only changed files.

## Plan

This is a draft until the Linux build is measured (ROADMAP **P1.5**).

- **Order per release:** Windows x64 AVX2 first (most users), then Linux x64 AVX2, then the SSE4
  variants, then ARM64.
- **Estimate:** at about 2.5 to 3 hours per variant, four x64 variants take 10 to 12 hours on one
  machine, so they fit in one night of unattended builds. That is far inside the 7-day target; the
  real risk to G2 is rebasing patches onto a new Chromium, not compile time.
- **To measure next:** a Windows Dev Drive for the build folder, where Defender keeps scanning but
  without blocking each file access.
- **Second machine:** not needed for the current matrix; reconsider if ARM64 builds or more
  variants push a release past one night.
