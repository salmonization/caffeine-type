"""Draw the Inksans CJK preview (docs/inksans-preview.svg) from the
built OTCs: one specimen line in each weight, W1 to W8, in two columns.
Glyphs are SVG paths, so the image needs no font.

No shaping: advances only, no kerning or contextual forms, which the
specimen does not need.

Plain outline fills look a weight lighter than the same font set as
text: text rasterizers darken small sizes (macOS font smoothing), path
fills do not. Measured in Chromium on macOS at 16 px, a stroke of
0.19 px around each glyph brings the SVG's ink to that of real text,
at Noto wght 340 (0.168 vs 0.167) and 590 (0.248 vs 0.248) alike.

Usage (after tools/mkinksans.py):
    uv run --with fonttools python -I tools/mkpreview.py
"""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTCollection

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/inksans-preview.svg"
STYLES = [f"W{n}" for n in range(1, 9)]
REGIONS = {"JP": 0, "KR": 1, "SC": 2, "TC": 3, "HK": 4}  # face index in the OTC
SPECIMEN = ("SC", "永 Aa 字体 かな")
SIZE, LABEL_SIZE = 28, 13  # px per em
ROWS, ROW = 4, 44  # rows per column, row pitch
LABEL_W = 34  # label column
COLUMN_GAP = 40
MARGIN = 24
INK, LABEL_INK = "#1a1a1a", "#888"
STROKE_PX = 0.19  # see the module docstring


def main():
    defs, uses = {}, []
    faces = {s: TTCollection(ROOT / f"build/InksansCJK-{s}.ttc").fonts for s in STYLES}

    def line(style, region, text, size, x, y, ink=INK):
        """Lay one line from (x, y) in px; returns the end x in px."""
        font = faces[style][REGIONS[region]]
        gs, cmap = font.getGlyphSet(), font.getBestCmap()
        hmtx, upem = font["hmtx"], font["head"].unitsPerEm
        for ch in text:
            name = cmap[ord(ch)]
            key = f"{style}{region}-{name}"
            if key not in defs:
                pen = SVGPathPen(gs)
                # font units, y up -> SVG, y down
                gs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
                defs[key] = pen.getCommands()
            if defs[key]:
                uses.append((key, x, y, size / upem, ink))
            x += hmtx[name][0] * size / upem
        return x

    x, width = MARGIN, 0
    for i, style in enumerate(STYLES):
        if i and i % ROWS == 0:
            x = width + COLUMN_GAP
        y = MARGIN + 0.88 * SIZE + (i % ROWS) * ROW  # baseline one ascent below the margin
        line("W3", "SC", style, LABEL_SIZE, x, y, LABEL_INK)
        width = max(width, line(style, *SPECIMEN, SIZE, x + LABEL_W, y))
    width += MARGIN
    height = MARGIN + 0.88 * SIZE + (ROWS - 1) * ROW + 0.12 * SIZE + MARGIN
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}">'
    )
    out = [
        svg,
        '<rect width="100%" height="100%" fill="#fff"/>',
        "<defs>",
    ]
    ids = {k: f"g{i}" for i, k in enumerate(defs)}
    out += [f'<path id="{ids[k]}" d="{d}"/>' for k, d in defs.items() if d]
    out.append("</defs>")
    # the stroke is in glyph units, so each size gets its own width
    for scale, ink in sorted({u[3:] for u in uses}):
        out.append(
            f'<g fill="{ink}" stroke="{ink}" stroke-linejoin="round" '
            f'stroke-width="{STROKE_PX / scale:.1f}">'
        )
        for key, x, y, sc, k in uses:
            if (sc, k) == (scale, ink):
                out.append(
                    f'<use xlink:href="#{ids[key]}" '
                    f'transform="translate({x:.2f} {y:.2f}) scale({sc:.5f})"/>'
                )
        out.append("</g>")
    out.append("</svg>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(out) + "\n")
    print(f"{OUT}: {len(defs)} glyphs, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
