# Thoron brand assets

## The logo: "Vortex"

A ring of three turning blades (magenta, violet, blue) around a deep indigo core, with a white band
between them. It sits in the family of the round emblems of Chromium-based browsers, a coloured ring
around a core, and is drawn its own way: the blades have curved edges, so the ring seems to turn, and
the colours are Thoron's. It replaces "Radiant Core" (2026-11-07), whose idea it keeps: a core with
three arcs around it. Redrawn on 2026-11-11 at the owner's request for a mark closer to that family,
"unique, modern but classic, professional". The three candidates of that study are in
[`concepts/2026-11-11/`](concepts/2026-11-11/); the earlier logo and its concepts are in
[`concepts/`](concepts/).

| File | Use |
|---|---|
| `thoron-logo.svg` | Primary colour logo |
| `thoron-logo-mono.svg` | Single-colour mark on a transparent background (three blades with gaps and the core), for monochrome or symbolic icons; recolour as needed |
| `png/thoron_<size>.png`, `thoron.ico` | Generated raster sizes (16-512 px) and the Windows multi-size icon: regenerate, never edit by hand |
| `png/thoron_wordmark.png`, `png/thoron_wordmark_white.png` | The mark plus the name "thoron" (342 x 64), dark and white text, where Chromium shows a product wordmark: regenerate, never edit by hand |

Colours: magenta `#F2559E` to `#D8307D`, violet `#915AF0` to `#7034D5`, blue `#5573F7` to `#304FDC`
(each blade a soft gradient), core `#2E1A87`, band `#FFFFFF`.

**Design rules:**
- The mark has no text (the wordmark adds the name next to it).
- It must stay legible at 16 px.
- The white band between ring and core is at least 1.5 px at 32 px.
- No shape of another browser's logo is reused: Chrome's and Chromium's ring is cut by straight lines
  that touch the inner circle; Thoron's blades have curved edges.
- It works on light and dark backgrounds.

## Regenerating the raster icons

```shell
py -3 -I tools/branding/export_icons.py --svg branding/thoron/thoron-logo.svg --out branding/thoron
py -3 -I tools/branding/export_icons.py --svg branding/thoron/thoron-logo.svg --out branding/thoron --sizes 252 504 70 150
py -3 -I tools/branding/wordmark.py --svg branding/thoron/thoron-logo.svg --out branding/thoron/png
```

## Licence

The Thoron logo artwork is © 2026 KuchiSofts, licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
The logo is original artwork and is not derived from the Thorium, Chromium or Chrome logos. Thorium's own logos remain the
work of Alex313031; see [`CREDITS.md`](../../CREDITS.md) and [`NOTICE`](../../NOTICE).
