"""Build the web fonts for type.caffeine.ink into site/fonts/.

Inksans CJK is 22 MB per weight, so each regional face is cut into
slices with CSS unicode-range; the browser fetches only the slices the
text uses. Three kinds, declared in this order:

  - rare: everything else, 2000 code points per slice, each covering
    one contiguous range
  - common: the frequent ideographs and Hangul (GB 2312 level 1, Big5
    frequent, JIS level 1, KS X 1001 Hangul), one slice whose range is
    their whole span
  - base: Latin, symbols, kana and CJK punctuation

Where ranges overlap, the browser tries the face declared last first
and falls back to earlier ones when the glyph is missing. So ordinary
text costs two downloads (base, common), a rare character one more,
and every range stays a single span: the stylesheet stays small.

Slices stay TTF: WOFF2 needs the brotli module, and Cloudflare
compresses font/ttf on the wire anyway. Paths carry the version, so
the files can be cached forever.

Usage (after tools/mkinksans.py):
    uv run --with fonttools --with skia-pathops python -I tools/mksite.py
"""

import os
import shutil
import sys
from multiprocessing import Pool
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).parent))
import bdf2ttf
import mkinksans
import mkinkscreen

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "fonts"
STYLES = {"Regular": 400, "Bold": 700}
RARE_SLICE = 2000

# lead bytes of the frequent rows in each legacy double-byte charset
COMMON_ROWS = {
    "gb2312": (0xB0, 0xD7),  # level 1 hanzi
    "big5": (0xA4, 0xC6),  # frequent hanzi
    "shift_jis": (0x88, 0x98),  # JIS level 1 kanji
    "euc_kr": (0xB0, 0xC8),  # the 2350 common Hangul syllables
}


def is_base(cp):
    return cp < 0x2E80 or 0x3000 <= cp <= 0x30FF or 0xFF00 <= cp <= 0xFFEF


def is_common(cp):
    ch = chr(cp)
    for enc, (lo, hi) in COMMON_ROWS.items():
        try:
            b = ch.encode(enc)
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and lo <= b[0] <= hi:
            return True
    return False


def slices(cps):
    """[(code points, unicode-range)] in declaration order (see above)."""
    base = sorted(cp for cp in cps if is_base(cp))
    common = sorted(cp for cp in cps if not is_base(cp) and is_common(cp))
    rare = sorted(cp for cp in cps if not is_base(cp) and not is_common(cp))
    out = [rare[i : i + RARE_SLICE] for i in range(0, len(rare), RARE_SLICE)]
    out = [(c, span(c)) for c in out]
    out.append((common, span(common)))
    out.append((base, "U+0-2E7F, U+3000-30FF, U+FF00-FFEF"))
    return out


def span(cps):
    return f"U+{cps[0]:X}-{cps[-1]:X}"


def cut(job):
    ttc, index, cps, path = job
    font = TTFont(ttc, fontNumber=index, lazy=True)
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.notdef_outline = True
    opts.name_IDs = [0, 1, 2, 13, 14]  # keep the copyright and license
    s = subset.Subsetter(opts)
    s.populate(unicodes=cps)
    s.subset(font)
    font.save(path)
    return path.stat().st_size


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    sans_dir = OUT / f"inksans-{mkinksans.VERSION}"
    screen_dir = OUT / f"inkscreen-{mkinkscreen.VERSION}"
    sans_dir.mkdir(parents=True)
    screen_dir.mkdir(parents=True)

    css, jobs = [], []
    for style, weight in STYLES.items():
        ttc = mkinksans.OUT / f"InksansCJK-{style}.ttc"
        for index, region in enumerate(mkinksans.REGIONS):
            cmap = TTFont(ttc, fontNumber=index, lazy=True).getBestCmap()
            for k, (cps, ranges) in enumerate(slices(set(cmap))):
                name = f"{style}-{region}-{k:02d}.ttf"
                jobs.append((ttc, index, cps, sans_dir / name))
                css.append(
                    f'@font-face {{ font-family: "Inksans CJK {region}"; '
                    f"font-weight: {weight}; font-display: swap; "
                    f'src: url("{sans_dir.name}/{name}") format("truetype"); '
                    f"unicode-range: {ranges}; }}"
                )
    with Pool(os.cpu_count()) as pool:
        sizes = pool.map(cut, jobs)
    print(
        f"{sans_dir}: {len(jobs)} slices, {sum(sizes) // 1048576} MB, largest {max(sizes) // 1024} KB"
    )

    for bdf, weight in (("inkscreen14.bdf", 400), ("inkscreen14b.bdf", 700)):
        bdf2ttf.convert(str(ROOT / "fonts" / bdf), screen_dir)
        name = Path(bdf).with_suffix(".ttf").name
        css.append(
            f'@font-face {{ font-family: "Inkscreen"; font-weight: {weight}; '
            f'src: url("{screen_dir.name}/{name}") format("truetype"); }}'
        )

    (OUT / "fonts.css").write_text("\n".join(css) + "\n")
    (OUT / "versions.js").write_text(
        f'window.VERSIONS = {{ inksans: "{mkinksans.VERSION}", '
        f'inkscreen: "{mkinkscreen.VERSION}" }};\n'
    )
    print(f"{OUT / 'fonts.css'}: {len(css)} rules")


if __name__ == "__main__":
    main()
