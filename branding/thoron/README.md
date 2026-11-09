# Thoron brand assets

## The logo: "Radiant Core"

A bright core (the element) with three swirling rings of gas around it: **Thoron**, the radiant gas
born from thorium. It was chosen by the project owner on 2026-11-07 from three original concepts
(kept in [`concepts/`](concepts/) for history; preview in `concepts/preview.png`).

| File | Use |
|---|---|
| `thoron-logo.svg` | Primary colour logo (violet `#7B2FF7` → magenta `#F72F8E` gradient disc, white mark) |
| `thoron-logo-mono.svg` | Single-colour mark on a transparent background, for monochrome or symbolic icons; recolour as needed |
| `png/thoron_<size>.png`, `thoron.ico` | Generated raster sizes (16-512 px) and the Windows multi-size icon: regenerate, never edit by hand |
| `png/thoron_wordmark.png`, `png/thoron_wordmark_white.png` | The mark plus the name "thoron" (342 x 64), dark and white text, where Chromium shows a product wordmark: regenerate, never edit by hand |

**Design rules:**
- The mark has no text (the wordmark adds the name next to it).
- It must stay legible at 16 px.
- Ring strokes are at least 1.5 px at 32 px.
- It works on light and dark backgrounds.

## Regenerating the raster icons

```shell
py -3 -I tools/branding/export_icons.py --svg branding/thoron/thoron-logo.svg --out branding/thoron
py -3 -I tools/branding/export_icons.py --svg branding/thoron/thoron-logo.svg --out branding/thoron --sizes 252 504
py -3 -I tools/branding/wordmark.py --svg branding/thoron/thoron-logo.svg --out branding/thoron/png
```

## Licence

The Thoron logo artwork is © 2026 KuchiSofts, licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
The logo is original artwork and is not derived from the Thorium logo. Thorium's own logos remain the
work of Alex313031; see [`CREDITS.md`](../../CREDITS.md) and [`NOTICE`](../../NOTICE).
