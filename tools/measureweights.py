"""Measure Hiragino Sans W0-W9 against Noto Sans CJK's weight axis,
the numbers behind mkinksans.WEIGHTS. Prints a Markdown table.

Three measures:

  - the thickness of 一 through its middle (a vertical cross-section),
    per 1000 units of em
  - the thickness of 丨 through its middle (a horizontal one)
  - the mean ink of a dozen common characters, in % of the em square

Cross-sections, not bounding boxes: the flared ends of the strokes
make a box much thicker than the stroke. Hiragino has more stroke
contrast than Noto at some weights, so the measures can disagree;
mkinksans.WEIGHTS settles between them.

Hiragino ships with macOS, so this runs only there. Usage:
    uv run --with fonttools --with skia-pathops python -I tools/measureweights.py
"""

import sys
from pathlib import Path

import pathops
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

sys.path.insert(0, str(Path(__file__).parent))
import mkinksans

HIRAGINO = "/System/Library/Fonts/ヒラギノ角ゴシック W{}.ttc"
INK = "永国東語書道愛識鬱あのカ"


def glyph_path(font, ch):
    gs = font.getGlyphSet()
    path = pathops.Path()
    gs[font.getBestCmap()[ord(ch)]].draw(path.getPen(glyphSet=gs))
    path.simplify()
    return path


def thickness(font, ch, vertical_cut):
    """Stroke thickness of ch through the middle of its bounds."""
    path = glyph_path(font, ch)
    x0, y0, x1, y1 = path.bounds
    cut = pathops.Path()
    pen = cut.getPen()
    if vertical_cut:
        m = (x0 + x1) / 2
        box = [(m - 1, y0 - 10), (m + 1, y0 - 10), (m + 1, y1 + 10), (m - 1, y1 + 10)]
    else:
        m = (y0 + y1) / 2
        box = [(x0 - 10, m - 1), (x1 + 10, m - 1), (x1 + 10, m + 1), (x0 - 10, m + 1)]
    pen.moveTo(box[0])
    for pt in box[1:]:
        pen.lineTo(pt)
    pen.closePath()
    b = pathops.op(path, cut, pathops.PathOp.INTERSECTION).bounds
    size = b[3] - b[1] if vertical_cut else b[2] - b[0]
    return 1000 * size / font["head"].unitsPerEm


def measure(font):
    """(一, 丨, ink %)."""
    ink = sum(abs(glyph_path(font, c).area) for c in INK) / len(INK)
    return (
        thickness(font, "一", True),
        thickness(font, "丨", False),
        100 * ink / font["head"].unitsPerEm ** 2,
    )


def main():
    noto = TTFont(mkinksans.NOTO, fontNumber=0)
    opts = subset.Options()
    opts.layout_features = []
    s = subset.Subsetter(opts)
    s.populate(text=INK + "一丨")
    s.subset(noto)
    noto_at = {
        w: measure(instancer.instantiateVariableFont(noto, {"wght": w})) for w in range(100, 901, 5)
    }

    def nearest(i, value):
        """Noto wght closest on measure i; '-' past either end of the axis."""
        lo, hi = noto_at[100][i], noto_at[900][i]
        if not lo * 0.97 <= value <= hi * 1.03:
            return "-"
        return min(noto_at, key=lambda w: abs(noto_at[w][i] - value))

    print("| Hiragino | 一 | 丨 | ink % | Noto by 一 | by 丨 | by ink | Inksans |")
    print("|---|---|---|---|---|---|---|---|")
    for n in range(10):
        m = measure(TTFont(HIRAGINO.format(n), fontNumber=0))
        by = [nearest(i, x) for i, x in enumerate(m)]
        ours = mkinksans.WEIGHTS.get(f"W{n}", ("-",))[0]
        print(
            f"| W{n} | {m[0]:.0f} | {m[1]:.0f} | {m[2]:.1f} | {by[0]} | {by[1]} | {by[2]} | {ours} |"
        )
    for w in (100, 400, 700, 900):
        m = noto_at[w]
        print(f"| Noto {w} | {m[0]:.0f} | {m[1]:.0f} | {m[2]:.1f} | | | | |")


if __name__ == "__main__":
    main()
