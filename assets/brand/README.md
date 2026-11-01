# Smoke-Shack brand assets

These original vector assets use only simple geometry and outlined glyphs. The SVGs are the editable masters; the PNGs are exports for places that do not accept SVG.

## Files

- `smoke-shack-icon.svg`: master text-free circular badge (`1024 × 1024` viewBox).
- `smoke-shack-icon-512.png`: high-resolution general-purpose icon.
- `smoke-shack-icon-256.png`: medium-resolution general-purpose icon.
- `smoke-shack-icon-128.png`: reserved for the future Home Assistant app icon.
- `smoke-shack-header.svg`: master repository/social header (`1280 × 640` viewBox). Its lettering is converted to paths.
- `smoke-shack-header-1280x640.png`: GitHub social preview image.

## Palette

| Name | Hex |
| --- | --- |
| Green | `#1f2b25` |
| Cream | `#f3e2c6` |
| Red | `#c0392b` |

No other colors are used.

The badge rings run from a cream outer circle through green and red rings to a
green centre (radii 480, 448, 430, and 404 respectively in the 1024-unit
viewBox).

## Typeface and license

The header uses **Bitter** (ExtraBold for “SMOKE-SHACK” and Medium for the subtitle), designed by Sol Matas and the Bitter project contributors. Bitter is licensed under the [SIL Open Font License 1.1](https://openfontlicense.org/). The final SVG contains outlined paths only and does not embed or require the font.

## PNG production

The PNGs were rendered directly from the SVG masters with CairoSVG 2.9.0:

```sh
cairosvg smoke-shack-icon.svg -o smoke-shack-icon-512.png -s 0.5
cairosvg smoke-shack-icon.svg -o smoke-shack-icon-256.png -s 0.25
cairosvg smoke-shack-icon.svg -o smoke-shack-icon-128.png -s 0.125
cairosvg smoke-shack-header.svg -o smoke-shack-header-1280x640.png
```

For a small-size legibility check, render the icon at 64 pixels with `-s 0.0625` and inspect it without committing that temporary export.
