# adblock-rust benchmark (ROADMAP P5.13)

Measures `adblock-rust` with the filter lists Thoron's bundled uBlock Origin ships: time to build the
engine from the list text and to load a saved engine, the engine's memory (a counting allocator, so it
is exact), and the time to check each request of a recorded request log. Offline.

```shell
git clone https://github.com/brave/adblock-rust   # next to the thoron repository, then audit it
cargo build --release --manifest-path tools/qa/adblock_bench/Cargo.toml
target/release/thoron-adblock-bench <adblock-rust>/data/requests.json 250000 <uBO assets>/thirdparties/easylist/easylist.txt ...
```

Use Chromium's own toolchain (`third_party/rust-toolchain/bin`), so the numbers match what the browser
would build. Results are recorded in `docs/design/2026-11-09-native-adblock-design.md`, section 4.2.
