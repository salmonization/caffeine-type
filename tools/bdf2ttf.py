"""Convert BDF bitmap fonts to pixel-outline TrueType fonts.

Each lit pixel becomes a square of PIXEL_UNITS font units and
unitsPerEm is PIXEL_SIZE * PIXEL_UNITS, so setting the font size to
the BDF's PIXEL_SIZE (or an integer multiple) renders exactly one
source pixel per screen pixel.

Non-Unicode BDFs (Big5, JIS X 0208/0201, GB2312) are remapped to
Unicode. Join files with "+" to merge them into one font, e.g.
jiskan16.bdf+8x16rk.bdf; the first file supplies the name and
metrics and later files only fill code points still missing.

Usage:
    uv run --with fonttools --with skia-pathops python -I bdf2ttf.py OUT_DIR FILE.bdf[+FILE.bdf]...
"""

import re
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.removeOverlaps import removeOverlaps

PIXEL_UNITS = 100


def parse_bdf(path):
    """Return (properties, glyphs); glyphs are dicts with pixel sets."""
    props, glyphs = {}, []
    lines = iter(Path(path).read_text(encoding="latin-1").splitlines())
    for line in lines:
        key, _, val = line.partition(" ")
        if key == "STARTCHAR":
            g = {"pixels": []}
            for line in lines:
                key, _, val = line.partition(" ")
                if key == "ENCODING":
                    g["enc"] = int(val.split()[0])
                elif key == "DWIDTH":
                    g["adv"] = int(val.split()[0])
                elif key == "BBX":
                    w, h, xoff, yoff = map(int, val.split())
                elif key == "BITMAP":
                    for row in range(h):
                        bits = int(next(lines), 16)
                        width = (w + 7) // 8 * 8
                        y = yoff + h - 1 - row
                        for col in range(w):
                            if bits >> (width - 1 - col) & 1:
                                g["pixels"].append((xoff + col, y))
                elif key == "ENDCHAR":
                    break
            glyphs.append(g)
        elif key in ("FONTBOUNDINGBOX",):
            props[key] = list(map(int, val.split()))
        elif val:
            props[key] = val.strip('"') if val.startswith('"') else val
    # some old fonts (taipei24) only carry these inside the XLFD name
    xlfd = props.get("FONT", "").split("-")
    if len(xlfd) == 15:
        for key, i in (("FAMILY_NAME", 2), ("WEIGHT_NAME", 3), ("PIXEL_SIZE", 7)):
            props.setdefault(key, xlfd[i])
        props.setdefault("CHARSET_REGISTRY", xlfd[13])
    return props, glyphs


def to_unicode(enc, registry):
    """Map a BDF ENCODING in the given charset to a code point or None."""
    registry = registry.upper()
    if registry.startswith(("ISO10646", "ISO8859-1")):
        return enc
    if registry.startswith("JISX0201"):
        # JIS-Roman differs from ASCII only at yen sign and overline
        if 0x20 <= enc < 0x80:
            return {0x5C: 0xA5, 0x7E: 0x203E}.get(enc, enc)
        return 0xFF61 + enc - 0xA1 if 0xA1 <= enc <= 0xDF else None
    hi, lo = enc >> 8, enc & 0xFF
    if registry.startswith("BIG5"):
        # cp950 lacks most ETen extensions (kana, Cyrillic at C6A1-C8FE),
        # big5hkscs has them
        candidates = [(bytes([hi, lo]), "cp950"), (bytes([hi, lo]), "big5hkscs")]
    elif registry.startswith("JISX0208"):
        candidates = [(bytes([hi | 0x80, lo | 0x80]), "euc_jp")]
    elif registry.startswith("GB2312"):
        candidates = [(bytes([hi | 0x80, lo | 0x80]), "gb2312")]
    else:
        sys.exit(f"unsupported charset {registry}")
    for raw, codec in candidates:
        try:
            s = raw.decode(codec)
        except UnicodeDecodeError:
            continue
        if len(s) == 1:
            return ord(s)
    return None


def draw(pixels):
    # Merge each row into horizontal runs to keep the outline small;
    # removeOverlaps later unions the vertically abutting runs so no
    # hairline seams appear when the font is scaled non-integrally.
    pen = TTGlyphPen(None)
    rows = {}
    for x, y in pixels:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x == prev + 1:
                prev = x
                continue
            x0, x1 = start * PIXEL_UNITS, (prev + 1) * PIXEL_UNITS
            y0, y1 = y * PIXEL_UNITS, (y + 1) * PIXEL_UNITS
            # clockwise contour, as TrueType expects for filled shapes
            pen.moveTo((x0, y0))
            pen.lineTo((x0, y1))
            pen.lineTo((x1, y1))
            pen.lineTo((x1, y0))
            pen.closePath()
            if x is not None:
                start = prev = x
    return pen.glyph()


def convert(spec, out_dir):
    bdf, *fallbacks = spec.split("+")
    props, glyphs = parse_bdf(bdf)
    px = int(props["PIXEL_SIZE"])
    ascent = int(props["FONT_ASCENT"]) * PIXEL_UNITS
    descent = int(props["FONT_DESCENT"]) * PIXEL_UNITS
    weight = "Bold" if props.get("WEIGHT_NAME", "").lower() == "bold" else "Regular"
    registry = props.get("CHARSET_REGISTRY", "ISO10646")
    if registry.upper().startswith("ISO10646"):
        family = f"{props.get('FAMILY_NAME', Path(bdf).stem)} {px}"
    else:
        # CJK X11 fonts are all named "Fixed"; the file stem (taipei16,
        # jiskan16, k14) is the name people know them by
        family = Path(bdf).stem.capitalize()
    ps_name = f"{family}-{weight}".replace(" ", "")

    default = int(props.get("DEFAULT_CHAR", -1))
    notdef = next((g for g in glyphs if g.get("enc") == default), None)
    by_cp, unmapped = {}, 0
    for path in [bdf, *fallbacks]:
        if path != bdf:
            fprops, glyphs = parse_bdf(path)
            registry = fprops.get("CHARSET_REGISTRY", "ISO10646")
        for g in glyphs:
            # unencoded glyphs (ENCODING -1) are unreachable, drop them
            if g.get("enc", -1) < 0:
                continue
            cp = to_unicode(g["enc"], registry)
            if cp is None:
                unmapped += path == bdf
            elif cp not in by_cp:
                by_cp[cp] = g
    order, cmap, outlines, metrics = [".notdef"], {}, {}, {}

    def add(name, g):
        outlines[name] = draw(g["pixels"])
        xmin = min((x for x, _ in g["pixels"]), default=0)
        metrics[name] = (g["adv"] * PIXEL_UNITS, xmin * PIXEL_UNITS)

    add(".notdef", notdef or {"pixels": [], "adv": props["FONTBOUNDINGBOX"][0]})
    for cp, g in sorted(by_cp.items()):
        if cp == 0:
            continue
        name = f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}"
        order.append(name)
        cmap[cp] = name
        add(name, g)

    fb = FontBuilder(px * PIXEL_UNITS, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)
    _, bh, _, by = props["FONTBOUNDINGBOX"]
    fb.setupOS2(
        sTypoAscender=ascent,
        sTypoDescender=-descent,
        sTypoLineGap=0,
        # win metrics must cover the tallest glyph or Windows clips it
        usWinAscent=max(ascent, (bh + by) * PIXEL_UNITS),
        usWinDescent=max(descent, -by * PIXEL_UNITS),
        usWeightClass=700 if weight == "Bold" else 400,
        fsSelection=0x20 if weight == "Bold" else 0x40,
    )
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": weight,
            "psName": ps_name,
            "copyright": props.get("COPYRIGHT", ""),
            "version": f"Version {props.get('FONT_VERSION', '1.000')}",
            "manufacturer": props.get("FOUNDRY", ""),
            "licenseDescription": props.get("NOTICE", ""),
            "licenseInfoURL": " ".join(re.findall(r"https?://\S+", props.get("NOTICE", ""))),
        }
    )
    # merged half-width + full-width fonts are not monospaced even
    # though each source BDF claims SPACING C
    fb.setupPost(isFixedPitch=len({adv for adv, _ in metrics.values()}) == 1)
    fb.font["head"].macStyle = 1 if weight == "Bold" else 0
    removeOverlaps(fb.font)

    out = Path(out_dir) / f"{Path(bdf).stem}.ttf"
    fb.save(out)
    note = f", {unmapped} unmapped" if unmapped else ""
    print(f"{out}: {family} {weight}, {len(cmap)} chars, use font-size {px}px{note}")


if __name__ == "__main__":
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in sys.argv[2:]:
        convert(f, out_dir)
