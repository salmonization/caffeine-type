"""Draw the hand-tuned Inkscreen glyphs next to their Unifont originals.

Each cell shows Unifont, Inkscreen and Inkscreen Bold on one baseline,
labelled with the code point. Labels are set in Inkscreen itself.

Usage:
    python3 tools/mkcompare.py [OUT.png]   (default build/inkscreen-vs-unifont.png)
"""

import sys
from pathlib import Path

import mkinkscreen as m

SCALE = 3
ZOOM = 2  # glyphs drawn twice the label size
GAP = 4
CELL_W, CELL_H = 88, 62  # label-size pixels
TOP_ROW = 13  # Unifont's tallest row; cells span rows 13 .. -4
PER_LINE = 8
GRAY = 170


def main(argv):
    out = Path(argv[0]) if argv else m.ROOT / "build/inkscreen-vs-unifont.png"
    over, over_bold = m.read_overrides(m.OVERRIDES)
    cps = sorted(set(over) | set(over_bold))
    uni = m.read_bdf(m.UNIFONT, set(cps))
    reg = m.read_bdf(m.ROOT / "fonts/inkscreen14.bdf", set(range(0x20, 0x100)))
    bold = m.read_bdf(m.ROOT / "fonts/inkscreen14b.bdf", set(cps))

    head = 40
    lines = (len(cps) + PER_LINE - 1) // PER_LINE
    w, h = PER_LINE * CELL_W + 16, head + lines * CELL_H + 8
    px = bytearray([255]) * (w * SCALE * h * SCALE)

    def put(x, y, v):
        for dy in range(SCALE):
            row = (y * SCALE + dy) * w * SCALE
            px[row + x * SCALE : row + (x + 1) * SCALE] = bytes([v]) * SCALE

    def glyph(rows, x0, baseline, width, v=0, zoom=1):
        # rows are 16 bits wide with bit 15 = x 0
        for y, bits in rows.items():
            for x in range(width):
                if bits & (0x8000 >> x):
                    for dy in range(zoom):
                        for dx in range(zoom):
                            put(x0 + x * zoom + dx, baseline - (y + 1) * zoom + 1 + dy, v)

    def text(s, x0, baseline, v=0):
        for i, ch in enumerate(s):
            glyph(reg.get(ord(ch), {}), x0 + i * 8, baseline, 8, v)

    text("Unifont 18.0.01 and Inkscreen 14: hand-tuned glyphs", 8, 16)
    text("each cell: Unifont | Inkscreen | Inkscreen Bold", 8, 32, 110)
    for n, cp in enumerate(cps):
        cx = 8 + n % PER_LINE * CELL_W
        cy = head + n // PER_LINE * CELL_H
        baseline = cy + (TOP_ROW + 1) * ZOOM - 1
        span = (8 + 8 + 9) * ZOOM + 2 * GAP
        x = cx + (CELL_W - span) // 2
        for gx in range(x - 2, x + span + 2):
            put(gx, baseline + 1, GRAY)  # under the baseline row
        for rows, dx, width in (
            (uni, 0, 8),
            (reg, 8 * ZOOM + GAP, 8),
            (bold, 16 * ZOOM + 2 * GAP, 9),
        ):
            glyph(rows[cp], x + dx, baseline, width, zoom=ZOOM)
        label = f"U+{cp:04X} {chr(cp)}"
        text(label, cx + (CELL_W - 8 * len(label)) // 2, cy + CELL_H - 6, 110)
    m.write_png(out, px, w * SCALE, h * SCALE)
    print(f"{out}: {len(cps)} glyphs")


if __name__ == "__main__":
    main(sys.argv[1:])
