"""Checks for the built Inksans CJK OTCs (run tools/mkinksans.py first).

Usage:
    uv run --with fonttools --with skia-pathops python -I tools/test_mkinksans.py
"""

import struct
import sys
from pathlib import Path

from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTCollection, TTFont
from fontTools.varLib import instancer
from pathops import Path as SkPath
from pathops import simplify

sys.path.insert(0, str(Path(__file__).parent))
import mkinksans as m

PER_REGION = ("GPOS", "GSUB", "OS/2", "cmap", "head", "name")


def table_offsets(path):
    """{tag: set of offsets} across the faces of a collection."""
    b = path.read_bytes()
    n = struct.unpack(">I", b[8:12])[0]
    seen = {}
    for o in struct.unpack(f">{n}I", b[12 : 12 + 4 * n]):
        for i in range(struct.unpack(">H", b[o + 4 : o + 6])[0]):
            tag, _, off, _ = struct.unpack(">4sIII", b[o + 12 + 16 * i : o + 28 + 16 * i])
            seen.setdefault(tag.decode(), set()).add(off)
    return seen


def area(font, ch, location=None):
    """Ink of one glyph, contours merged (the source overlaps them)."""
    gs = font.getGlyphSet(location=location)
    path, pen = SkPath(), AreaPen(gs)
    gs[font.getBestCmap()[ord(ch)]].draw(path.getPen())
    simplify(path).draw(pen)
    return abs(pen.value)


def overlaps(font, ch):
    """True if merging the glyph's contours changes its ink."""
    gs = font.getGlyphSet()
    glyph = gs[font.getBestCmap()[ord(ch)]]
    path, raw = SkPath(), AreaPen(gs)
    glyph.draw(path.getPen())
    glyph.draw(raw)
    merged = AreaPen(gs)
    simplify(path).draw(merged)
    return abs(abs(raw.value) - abs(merged.value)) > 1


def kern_everywhere(font, glyph):
    """Every language system of latn/grek/cyrl has a kern lookup that
    covers glyph."""
    table = font["GPOS"].table
    feats = table.FeatureList.FeatureRecord
    lookups = table.LookupList.Lookup

    def covers(i):
        for st in lookups[i].SubTable:
            st = getattr(st, "ExtSubTable", st)
            if glyph in getattr(getattr(st, "Coverage", None), "glyphs", ()):
                return True
        return False

    for rec in table.ScriptList.ScriptRecord:
        if rec.ScriptTag not in ("latn", "grek", "cyrl"):
            continue
        systems = [("dflt", rec.Script.DefaultLangSys)]
        systems += [(r.LangSysTag, r.LangSys) for r in rec.Script.LangSysRecord]
        for tag, ls in systems:
            ok = any(
                feats[i].FeatureTag == "kern" and any(map(covers, feats[i].Feature.LookupListIndex))
                for i in ls.FeatureIndex
            )
            assert ok, (rec.ScriptTag, tag)


def main():
    src = TTFont(m.NOTO, fontNumber=0, lazy=True)
    inter = m.load_inter()
    k = 1000 / inter["head"].unitsPerEm
    for style, (wght, inter_wght) in m.WEIGHTS.items():
        path = m.OUT / f"InksansCJK-{style}.ttc"
        faces = TTCollection(path).fonts
        assert len(faces) == len(m.REGIONS)

        # outlines and metrics stored once, regional tables per face
        offsets = table_offsets(path)
        for tag, offs in offsets.items():
            # regions may still share a per-region table (Noto has two OS/2)
            assert len(offs) <= len(m.REGIONS) if tag in PER_REGION else len(offs) == 1, (
                style,
                tag,
            )
        assert len(offsets["cmap"]) == len(m.REGIONS)

        for region, f in zip(m.REGIONS, faces):
            names = {r.nameID: r.toUnicode() for r in f["name"].names}
            family = f"Inksans CJK {region}"
            assert (names[1], names[2]) == (f"{family} {style}", "Regular")
            assert (names[16], names[17]) == (family, style)
            for nid, s in names.items():
                # source names only in the copyright and designer credits
                assert nid in (0, 9) or not {"Noto", "Source", "Inter"} & set(s.split()), (nid, s)
            assert f["OS/2"].usWeightClass == m.WEIGHT_CLASS[style]

        # strokes that cross must not leave overlapping contours
        for f in faces:
            hits = [ch for ch in "AKMWX永国骨東書あ한" if overlaps(f, ch)]
            assert not hits, (style, hits)

        # regional glyphs: 骨 differs between Japanese and Simplified Chinese
        jp, sc = faces[0].getBestCmap(), faces[2].getBestCmap()
        assert jp[ord("骨")] != sc[ord("骨")]

        # Latin from Inter (its advances), CJK punctuation still Noto's
        # (full-width curly quotes in Chinese, narrow in Japanese)
        loc = {"wght": inter_wght, "opsz": m.INTER_OPSZ}
        static = instancer.instantiateVariableFont(m.load_inter(), loc)
        icmap = static.getBestCmap()
        for ch in "nAΩЖ":
            want = static["hmtx"][icmap[ord(ch)]][0] * k
            assert abs(faces[0]["hmtx"][jp[ord(ch)]][0] - want) <= 1, ch
        assert faces[2]["hmtx"][sc[ord("“")]][0] == 1000
        assert faces[0]["hmtx"][jp[ord("“")]][0] < 1000
        kern_everywhere(faces[0], jp[ord("A")])

        # instanced at the intended weight; rounding the instanced
        # outlines to integers moves the ink by a few weight units. At
        # the end of the axis the upper bound would clamp to the weight
        # itself, so it gets 1% of slack instead.
        def bracket(font, ch, loc, w, k=1):
            lo, hi = (area(font, ch, loc | {"wght": min(w + d, 900)}) * k * k for d in (-10, 10))
            return lo, hi * (1.01 if w + 10 > 900 else 1)

        lo, hi = bracket(src, "永", {}, wght)
        assert lo < area(faces[0], "永") < hi, style
        lo, hi = bracket(inter, "n", {"opsz": m.INTER_OPSZ}, inter_wght, k)
        assert lo < area(faces[0], "n") < hi, style
        print("ok", path.name)


if __name__ == "__main__":
    main()
