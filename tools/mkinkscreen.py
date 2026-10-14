"""Build the Inkscreen 14 bitmap fonts (regular and bold) from GNU Unifont.

Inkscreen keeps Unifont's 8x16 cell but redraws the Latin glyphs to a
14-row design like SunOS screen.r.14: ink between row 10 above and
row -3 below the baseline, x-height 7, descenders 3. The 16-row cell
(ascent 12, descent 4) keeps 16px CJK fonts on the same line grid.

Automatic rules, then hand overrides from tools/inkscreen-overrides.txt:
  - lowercase: merge the two most similar adjacent rows inside the
    x-height (8 -> 7 rows); identical stem rows merge losslessly
  - g j p q y: repeat one stem row below the baseline (2 -> 3 rows)
  - anything still above row 10 moves down, then is clipped
  - accented letters: our own base letter plus Unifont's mark, one
    blank row between; a base that leaves no room for its mark below
    row 11 loses its most similar adjacent rows (capitals: 10 -> 9)
  - µ and þ: spliced from our u, b and p; soft hyphen copies '-'
  - bold: thicken one pixel to the right (9 px wide); accented and
    spliced bold glyphs build on the bold bases, so a bold edit to a
    base letter carries over

Inkscreen is a modified Unifont and stays under the SIL OFL 1.1.

Usage:
    python3 tools/mkinkscreen.py [--chart OUT.png --ref screen.r.14.bdf [--refb screen.b.14.bdf]]
"""

import functools
import gzip
import struct
import sys
import unicodedata
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIFONT = ROOT / "fonts/src/unifont-18.0.01.bdf.gz"
OVERRIDES = ROOT / "tools/inkscreen-overrides.txt"
TOP, BOTTOM = 11, -3  # ink limits, rows above/below the baseline
BODY_TOP = 10  # everything but accents stays below row 11
ASCENT, DESCENT = 12, 4  # 16-row cell
BOLD_W = 9  # regular is 8
# Unifont draws this as a dashed box with a label
SAME_AS = {0xA0: 0x20}
# soft hyphen shows as a hyphen when a line breaks there; tracks our '-'
COPIES = {0xAD: ord("-")}
# rows above `at` from the first letter, the rest from the second
SPLICES = {0xB5: (ord("u"), ord("p"), -1), 0xFE: (ord("b"), ord("p"), 6)}
CODEPOINTS = [*range(0x20, 0x7F), *range(0xA0, 0x100)]
VERSION = "1.000"
COPYRIGHT = (
    "Copyright (C) 2026 Caffeine Type Foundry. Based on GNU Unifont, "
    "Copyright (C) 1998-2026 Roman Czyborra, Paul Hardy, et al."
)
NOTICE = (
    "This Font Software is licensed under the SIL Open Font License, "
    "Version 1.1. https://openfontlicense.org"
)


def read_bdf(path, want, yshift=0):
    """Return {cp: {y: row}}, rows 16 bits wide with bit 15 = x 0."""
    opener = gzip.open if str(path).endswith(".gz") else open
    glyphs, cp, bbx = {}, None, None
    with opener(path, "rt", encoding="latin-1") as f:
        lines = iter(f)
        for line in lines:
            key = line.split()
            if not key:
                continue
            if key[0] == "ENCODING":
                cp = int(key[1])
            elif key[0] == "BBX":
                bbx = tuple(map(int, key[1:5]))
            elif key[0] == "BITMAP" and cp in want:
                w, h, x0, y0 = bbx
                rows = {}
                for r in range(h):
                    v = int(next(lines).strip(), 16)
                    v = v << (16 - (w + 7) // 8 * 8)
                    rows[y0 + h - 1 - r + yshift] = (v >> x0 if x0 >= 0 else v << -x0) & 0xFFFF
                glyphs[cp] = rows
    return glyphs


def ink(rows):
    ys = [y for y, v in rows.items() if v]
    return (max(ys), min(ys)) if ys else (0, 0)


def squeeze(rows, lo, hi):
    """Merge the two most similar adjacent rows among lo..hi."""

    def dist(r):
        return (rows.get(r, 0) ^ rows.get(r + 1, 0)).bit_count()

    best = min(range(lo, hi), key=lambda r: (dist(r), r))
    out = {}
    for y, v in rows.items():
        if y < best:
            out[y] = v
        elif y == best:
            out[y] = v | rows.get(best + 1, 0)
        elif y > best + 1:
            out[y - 1] = v
    return out


def squeeze_xheight(rows):
    return squeeze(rows, 1, 6)


def extend_descender(rows):
    # prefer repeating a stem row so curves and hooks keep their shape
    for r in (-1, 0, -2, 1):
        if rows.get(r) and rows.get(r) == rows.get(r + 1):
            break
    else:
        r = -1
    out = {y - 1 if y <= r else y: v for y, v in rows.items()}
    out[r] = rows.get(r, 0)
    return out


def fit(rows, cp, report):
    top, bottom = ink(rows)
    if top > BODY_TOP:
        shift = min(top - BODY_TOP, bottom - BOTTOM)
        rows = {y - shift: v for y, v in rows.items()}
        if ink(rows)[0] > BODY_TOP:
            report.append(f"U+{cp:04X} {chr(cp)!r}: clipped above row {BODY_TOP}")
    return {y: rows.get(y, 0) for y in range(BOTTOM, TOP + 1)}


def split_accent(cp):
    """(base cp, mark is below the baseline) for a precomposed letter."""
    d = unicodedata.decomposition(chr(cp)).split()
    if len(d) != 2 or d[0].startswith("<"):
        return None
    return int(d[0], 16), d[1] == "0327"  # cedilla


def top_mark(rows):
    """The topmost run of inked rows, if a blank row parts it from the rest."""
    ys = sorted((y for y, v in rows.items() if v), reverse=True)
    run = [ys[0]]
    while len(run) < len(ys) and ys[len(run)] == run[-1] - 1:
        run.append(ys[len(run)])
    return {y: rows[y] for y in run} if len(run) < len(ys) else {}


def compose(base, src, below, cp, report):
    """Our base glyph plus the mark from Unifont's precomposed glyph."""
    if below:
        return {y: base.get(y, 0) | (src.get(y, 0) if y < 0 else 0) for y in base}
    if 0xEC <= cp <= 0xEF:  # i loses its dot
        base = {y: v if y < 7 else 0 for y, v in base.items()}
    mark = top_mark(src)
    mtop, mbottom = ink(mark)
    height = mtop - mbottom + 1
    while ink(base)[0] + 1 + height > TOP:
        base = squeeze(base, 1, ink(base)[0])
        base[TOP] = base.get(TOP, 0)
        report.append(f"U+{cp:04X} {chr(cp)!r}: base squeezed to {ink(base)[0] + 1} rows")
    shift = ink(base)[0] + 2 - mbottom
    out = dict(base)
    for y, v in mark.items():
        out[y + shift] = out.get(y + shift, 0) | v
    return {y: out.get(y, 0) for y in range(BOTTOM, TOP + 1)}


def is_derived(cp):
    return cp in SPLICES or cp in COPIES or split_accent(cp) is not None


def derive(cp, bases, report, bold=False):
    """An accented or spliced glyph from the final base glyphs."""
    if cp in COPIES:
        return dict(bases[COPIES[cp]])
    if cp in SPLICES:
        upper, lower, at = SPLICES[cp]
        return {y: (bases[upper] if y > at else bases[lower]).get(y, 0) for y in bases[lower]}
    base, below = split_accent(cp)
    mark = unifont_latin()[cp]
    return compose(bases[base], embolden(mark) if bold else mark, below, cp, report)


def embolden(rows):
    """8-px regular -> 9-px bold (bit 8 = x 0), thickened one pixel right.

    Bold is one pixel wider than regular, like SunOS screen.b.14, so the
    extra stroke width never eats the gap between glyphs.
    """
    return {y: v << 1 | v for y, v in rows.items()}


def check(regular, bold):
    """Glyphs that may touch the previous glyph: x 0 is the gap column."""
    out = []
    for name, glyphs, top_bit in (("regular", regular, 0x80), ("bold", bold, 0x100)):
        hits = "".join(
            chr(cp) for cp, g in sorted(glyphs.items()) if any(v & top_bit for v in g.values())
        )
        if hits:
            out.append(f"{name} glyphs inking column 0 (may touch the previous glyph): {hits}")
    return out


def read_overrides(path):
    """Blocks of 'U+XXXX [bold]' followed by 15 rows of '.'/'#', top first.

    Comments start with ';' because pixel rows may start with '#'.
    Blocks of 14 rows predate row 11 and start at row 10.
    """
    regular, bold = {}, {}
    if not path.exists():
        return regular, bold
    lines = [
        l.rstrip()
        for l in path.read_text(encoding="utf-8").splitlines()
        if l.strip() and l[0] != ";"
    ]
    i = 0
    while i < len(lines):
        head = lines[i].split()
        cp = int(head[0].removeprefix("U+"), 16)
        n = i + 1
        while n < len(lines) and not lines[n].startswith("U+"):
            n += 1
        art = lines[i + 1 : n]
        is_bold = "bold" in head[1:]
        # bold blocks drawn before bold went 9 wide are 8 wide; pad right
        widths = (8, BOLD_W) if is_bold else (8,)
        top = BOTTOM + len(art) - 1
        if top not in (TOP, TOP - 1) or any(len(a) not in widths for a in art):
            sys.exit(f"{path}: bad glyph block for {head[0]}")
        rows = {
            top - n: int(a.replace("#", "1").replace(".", "0"), 2)
            << (BOLD_W - len(a) if is_bold else 0)
            for n, a in enumerate(art)
        }
        rows.setdefault(TOP, 0)
        (bold if is_bold else regular)[cp] = rows
        i += 1 + len(art)
    return regular, bold


def write_overrides(path, regular, bold):
    out = [
        "; Hand edits to Inkscreen, applied over tools/mkinkscreen.py's automatic glyphs.",
        "; Each block: 'U+XXXX' (or 'U+XXXX bold'), then 15 rows of 8 (bold 9) pixels,",
        "; row 11 above the baseline first, row -3 below it last.",
    ]
    for tag, glyphs, w in (("", regular, 8), (" bold", bold, BOLD_W)):
        for cp, rows in sorted(glyphs.items()):
            out.append(f"\nU+{cp:04X}{tag} ; {chr(cp)!r}")
            out += [
                format(rows.get(y, 0), f"0{w}b").replace("0", ".").replace("1", "#")
                for y in range(TOP, BOTTOM - 1, -1)
            ]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


@functools.cache
def unifont_latin():
    src = read_bdf(UNIFONT, set(CODEPOINTS))
    return {cp: {y: v >> 8 for y, v in g.items()} for cp, g in src.items()}  # 8 wide


def auto_regular(report, over=None):
    """Automatic glyphs; derived glyphs build on the overridden bases."""
    src = unifont_latin()
    over = over or {}
    auto = {}
    for cp in CODEPOINTS:
        if is_derived(cp):
            continue
        rows = src[SAME_AS.get(cp, cp)]
        if any(v & 0x80 for v in rows.values()) and not any(v & 1 for v in rows.values()):
            rows = {y: v >> 1 for y, v in rows.items()}  # free the gap column
        if unicodedata.category(chr(cp)) == "Ll":
            rows = squeeze_xheight(rows)
            if ink(rows)[1] < 0:
                rows = extend_descender(rows)
        auto[cp] = fit(rows, cp, report)
    bases = {cp: over.get(cp) or auto[cp] for cp in auto}
    for cp in CODEPOINTS:
        if is_derived(cp):
            auto[cp] = derive(cp, bases, report)
    return auto


def auto_bold(regular, over_bold):
    """Bold without its own override: emboldened regular, or for derived
    glyphs the same derivation over the bold bases."""
    bases = {cp: over_bold.get(cp) or embolden(regular[cp]) for cp in CODEPOINTS}
    return {
        cp: derive(cp, bases, [], bold=True) if is_derived(cp) else bases[cp] for cp in CODEPOINTS
    }


def build():
    report = []
    over, over_bold = read_overrides(OVERRIDES)
    auto = auto_regular(report, over)
    regular = {cp: over.get(cp) or auto[cp] for cp in CODEPOINTS}
    # bold derives from the final regular, so a regular edit carries over
    autob = auto_bold(regular, over_bold)
    bold = {cp: over_bold.get(cp) or autob[cp] for cp in CODEPOINTS}
    return regular, bold, report + check(regular, bold)


def write_bdf(path, glyphs, weight, width):
    xlfd = f"-Caffeine-Inkscreen-{weight}-R-Normal--16-160-75-75-C-{width * 10}-ISO10646-1"
    nbytes = (width + 7) // 8
    out = [
        "STARTFONT 2.1",
        f"FONT {xlfd}",
        "SIZE 16 75 75",
        f"FONTBOUNDINGBOX {width} 16 0 {-DESCENT}",
        "STARTPROPERTIES 14",
        'FOUNDRY "Caffeine"',
        'FAMILY_NAME "Inkscreen"',
        f'WEIGHT_NAME "{weight}"',
        "PIXEL_SIZE 16",
        f"FONT_ASCENT {ASCENT}",
        f"FONT_DESCENT {DESCENT}",
        'SPACING "C"',
        f"AVERAGE_WIDTH {width * 10}",
        'CHARSET_REGISTRY "ISO10646"',
        'CHARSET_ENCODING "1"',
        "DEFAULT_CHAR 32",
        f'COPYRIGHT "{COPYRIGHT}"',
        f'NOTICE "{NOTICE}"',
        f'FONT_VERSION "{VERSION}"',
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
    ]
    for cp, rows in sorted(glyphs.items()):
        out += [
            f"STARTCHAR U+{cp:04X}",
            f"ENCODING {cp}",
            f"SWIDTH {width * 1000 // 16} 0",
            f"DWIDTH {width} 0",
            f"BBX {width} 16 0 {-DESCENT}",
            "BITMAP",
        ]
        out += [
            f"{rows.get(y, 0) << (nbytes * 8 - width):0{nbytes * 2}X}"
            for y in range(ASCENT - 1, -DESCENT - 1, -1)
        ]
        out.append("ENDCHAR")
    out.append("ENDFONT")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_png(path, px, w, h):
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))

    raw = b"".join(b"\0" + bytes(px[y * w : (y + 1) * w]) for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def chart(path, bands):
    """Rows of 16 glyphs; per row one band per font, top to bottom."""
    scale, cw, ch, top = 4, 11, 19, 13  # cell rows y = 13 .. -5
    per, cps = 16, [cp for cp in CODEPOINTS if cp not in (0x20, 0xA0)]
    lines = (len(cps) + per - 1) // per
    w = per * cw * scale
    h = lines * (len(bands) * ch + 4) * scale
    px = bytearray([255]) * (w * h)

    def put(x, y, v):
        for dy in range(scale):
            row = (y * scale + dy) * w
            px[row + x * scale : row + x * scale + scale] = bytes([v]) * scale

    for n, cp in enumerate(cps):
        lx, ly = n % per, n // per
        for b, glyphs in enumerate(bands):
            oy = ly * (len(bands) * ch + 4) + b * ch
            rows = glyphs.get(cp, {})
            for yy in range(ch):
                y = top - yy
                for x in range(cw - 1):
                    on = rows.get(y, 0) & (0x8000 >> x)
                    guide = y in (0, BODY_TOP + 1, BOTTOM - 1)  # baseline, ink limits
                    put(lx * cw + x, oy + yy, 0 if on else 200 if guide else 255)
        for x in range(per * cw):
            put(x, ly * (len(bands) * ch + 4) + len(bands) * ch + 1, 120)
    write_png(path, px, w, h)


def read_ref(path):
    # screen.r.14 from vfont2bdf sits one row low; lift it onto the baseline
    return read_bdf(path, set(CODEPOINTS), yshift=1)


def rebuild(chart_out=None, refs=()):
    """Write both fonts (and the chart); returns the report lines."""
    regular, bold, report = build()
    write_bdf(ROOT / "fonts/inkscreen14.bdf", regular, "Medium", 8)
    write_bdf(ROOT / "fonts/inkscreen14b.bdf", bold, "Bold", BOLD_W)
    if chart_out:
        # chart rows are 16 bits with bit 15 = x 0
        wide = [
            {cp: {y: v << shift for y, v in g.items()} for cp, g in f.items()}
            for f, shift in ((regular, 8), (bold, 16 - BOLD_W))
        ]
        chart(chart_out, [read_bdf(UNIFONT, set(CODEPOINTS)), *wide, *map(read_ref, refs)])
    return report


def main(argv):
    def arg(flag):
        return argv[argv.index(flag) + 1] if flag in argv else None

    chart_out = arg("--chart")
    refs = [p for p in (arg("--ref"), arg("--refb")) if p]
    for r in rebuild(chart_out and Path(chart_out), refs):
        print("  " + r)
    print(f"fonts/inkscreen14.bdf, fonts/inkscreen14b.bdf: {len(CODEPOINTS)} glyphs")
    if chart_out:
        print(f"{chart_out}: bands = unifont, inkscreen, inkscreen bold, refs")


if __name__ == "__main__":
    main(sys.argv[1:])
