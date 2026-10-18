"""Draw the Inksans CJK preview (docs/inksans-preview.svg) from the
built OTCs: each sample line in the regional face it belongs to, in
Regular and Bold. Glyphs are SVG paths, so the image needs no font.

No shaping: advances only, no kerning or contextual forms, which the
sample text does not need.

Plain outline fills look a weight lighter than the same font set as
text: text rasterizers darken small sizes (macOS font smoothing), path
fills do not. Measured in Chromium on macOS at 16 px, a stroke of
0.19 px around each glyph brings the SVG's ink to that of real text,
for Regular (0.168 vs 0.167) and Bold (0.248 vs 0.248) alike.

Usage (after tools/mkinksans.py):
    uv run --with fonttools python -I tools/mkpreview.py
"""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTCollection

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/inksans-preview.svg"
REGIONS = {"JP": 0, "KR": 1, "SC": 2, "TC": 3, "HK": 4}  # face index in the OTC
SAMPLE = [
    ("SC", "We shall meet in the place where there is no darkness."),
    ("JP", "まつすぐな道でさみしい。"),
    ("SC", "我们终将迷失在大雾里，互相呼唤，在不同的地点，成为无用的路标。"),
    ("TC", "我們終將迷失在大霧裡，互相呼喚，在不同的地點，成為無用的路標。"),
]
# the specimen is large; the sample lines are at text size, where the
# weights read as they do in use (at 28 px Regular looked too light)
SPECIMEN, SPECIMEN_SIZE = ("SC", "永 Aa 字体 かな"), 28
SIZE, LINE = 16, 26  # px per em, line pitch
GAP = 18  # between blocks
MARGIN = 24
INK = "#1a1a1a"
STROKE_PX = 0.19  # see the module docstring


def main():
    defs, uses = {}, []
    faces = {s: TTCollection(ROOT / f"build/InksansCJK-{s}.ttc").fonts for s in ("Regular", "Bold")}

    def line(style, region, text, size, x, y):
        """Lay one line from (x, y) in px; returns the end x in px."""
        font = faces[style][REGIONS[region]]
        gs, cmap = font.getGlyphSet(), font.getBestCmap()
        hmtx, upem = font["hmtx"], font["head"].unitsPerEm
        for ch in text:
            name = cmap[ord(ch)]
            key = f"{style[0]}{region}-{name}"
            if key not in defs:
                pen = SVGPathPen(gs)
                # font units, y up -> SVG, y down
                gs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
                defs[key] = pen.getCommands()
            if defs[key]:
                uses.append((key, x, y, size / upem))
            x += hmtx[name][0] * size / upem
        return x

    y = MARGIN + 0.88 * SPECIMEN_SIZE  # baseline one ascent below the margin
    x = line("Regular", *SPECIMEN, SPECIMEN_SIZE, MARGIN, y)
    width = line("Bold", *SPECIMEN, SPECIMEN_SIZE, x + SPECIMEN_SIZE, y)
    y += 0.12 * SPECIMEN_SIZE + GAP
    for style in ("Regular", "Bold"):
        for region, text in SAMPLE:
            y += LINE
            width = max(width, line(style, region, text, SIZE, MARGIN, y))
        y += GAP
    width += MARGIN

    height = y - GAP + 0.6 * LINE + MARGIN
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
    for scale in sorted({u[3] for u in uses}):
        out.append(
            f'<g fill="{INK}" stroke="{INK}" stroke-linejoin="round" '
            f'stroke-width="{STROKE_PX / scale:.1f}">'
        )
        for key, x, y, sc in uses:
            if sc == scale:
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
