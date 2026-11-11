# The browser's source

Thoron's changes to the browser are a patch series on top of [Thorium](https://github.com/Alex313031/thorium)'s,
which is itself a patch series on top of Chromium. This folder holds Thoron's part:

| File | What it is |
|---|---|
| `UPSTREAM.json` | The upstream repository and the one commit Thoron builds on, the Chromium version, and the git tree hash of the finished build tree |
| `overlay/` | Every file Thoron adds or changes on top of that commit, byte for byte |
| `REMOVED.txt` | The upstream files Thoron leaves out |

Upstream's own files are not copied here. The build fetches them at the pinned commit.

## Check it or rebuild the tree

```shell
git clone https://github.com/gz83/thorium upstream
py -3 -I tools/build/source_tree.py verify --upstream upstream --source source
py -3 -I tools/build/source_tree.py materialize --upstream upstream --source source --out <new folder>
```

`verify` puts the overlay on the pinned commit and compares the tree hash with the one on record, so a
changed, missing or extra file is noticed. `materialize` writes the build tree that
[`docs/build/WINDOWS.md`](../docs/build/WINDOWS.md) then applies to Chromium.

## Files that are withheld

Seven files of the series are recorded in `UPSTREAM.json` by their hash only and are not published here
yet. The tree hash still verifies; `materialize` says which content is missing.

- `other/thorium-default-api-keys.patch`: it carries Google API credentials that are not Thoron's. Whether
  a release ships without them is ROADMAP **L.8**.
- Six patches whose original authors publish no licence (listed as NOT STATED in
  [`docs/legal/PATCH_LICENSES.md`](../docs/legal/PATCH_LICENSES.md)). They wait for the author's permission
  or a rewrite, ROADMAP **L.1**.

## Licences and credit

Every patch names its origin, author and licence in its header. The inventory is in
[`docs/legal/PATCH_LICENSES.md`](../docs/legal/PATCH_LICENSES.md), the credits in
[`CREDITS.md`](../CREDITS.md) and the licence texts in [`NOTICE`](../NOTICE).
