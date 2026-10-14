"""Check converted TTFs against their BDFs, pixel for pixel.

Each TTF outline is sampled at every pixel centre with fontTools, so
the check needs no rasterizer. Pillow is not used: its text placement
lifts glyphs that reach the top rows by one pixel, although FreeType
itself places them correctly.

Usage:
    uv run --with fonttools --with skia-pathops python -I tools/test_bdf2ttf.py
"""

import sys
import tempfile
from pathlib import Path

from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).parent))
from bdf2ttf import PIXEL_UNITS, convert, parse_bdf, to_unicode

ROOT = Path(__file__).resolve().parent.parent


def outline_pixels(glyphset, name, bbox):
    """Pixels whose centre lies inside the glyph outline."""
    w, h, x0, y0 = bbox
    got = set()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            pen = PointInsidePen(glyphset, ((x + 0.5) * PIXEL_UNITS, (y + 0.5) * PIXEL_UNITS))
            glyphset[name].draw(pen)
            if pen.getResult():
                got.add((x, y))
    return got


def check(bdf, ttf):
    props, glyphs = parse_bdf(bdf)
    registry = props.get("CHARSET_REGISTRY", "ISO10646")
    font = TTFont(ttf)
    cmap, glyphset = font.getBestCmap(), font.getGlyphSet()
    bbox = props["FONTBOUNDINGBOX"]
    for g in glyphs:
        cp = to_unicode(g.get("enc", -1), registry) if g.get("enc", -1) >= 0 else None
        if not cp:
            continue
        got = outline_pixels(glyphset, cmap[cp], bbox)
        assert got == set(g["pixels"]), f"{bdf.name} U+{cp:04X}: pixels differ"


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as out:
        for bdf in sorted((ROOT / "fonts").glob("*.bdf")):
            convert(str(bdf), out)
            check(bdf, Path(out) / f"{bdf.stem}.ttf")
            print("ok", bdf.name)
