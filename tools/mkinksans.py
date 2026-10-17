"""Build Inksans CJK (Regular, Bold): Noto Sans CJK with Inter's Latin.

CJK comes from Noto Sans CJK at fixed weights matched to the darkness
of Hiragino Sans W3/W6 (stem width and ink coverage): wght 340 for
Regular, 590 for Bold. Latin, Greek and Cyrillic come from Inter (opsz
14), at the weight whose stems match Noto's own Latin at those
weights (345, 610). Inter needs no scaling: its cap height and
x-height at 1000 units are within 1% of Noto's Latin.

Each weight is one OTC with the five regional faces (JP, KR, SC, TC,
HK). As in Noto, the faces share one set of outlines and metrics;
only cmap, GSUB, GPOS, OS/2, head and name differ per region.

Noto Sans CJK is a renamed Source Han Sans under the SIL OFL 1.1 with
Reserved Font Name "Source", and "Noto" is a Google trademark, so
neither word may appear in our names. Inter is OFL 1.1 without a
Reserved Font Name.

Usage (a few minutes, up to 8 GB of memory):
    uv run --with fonttools --with skia-pathops python -I tools/mkinksans.py
"""

import copy
import hashlib
import io
import os
import sys
import tempfile
import urllib.request
import zipfile
from multiprocessing import Pool
from pathlib import Path

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTCollection, TTFont, newTable
from fontTools.ttLib.removeOverlaps import removeOverlaps
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build"
NOTO = ROOT / "fonts/src/noto/NotoSansCJK-VF.ttf.ttc"
NOTO_URL = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/"
    "165c01b46ea533872e002e0785ff17e44f6d97d8/Sans/Variable/OTC/NotoSansCJK-VF.ttf.ttc"
)
INTER_ZIP = ROOT / "fonts/src/inter/Inter-4.1.zip"
SOURCES = {
    NOTO: (NOTO_URL, "2abbfc7ff74a086cf2c1f5be6130528791cfd2c8b83466db5a1463aa63252ca7"),
    INTER_ZIP: (
        "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
        "9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e",
    ),
}

VERSION = "1.000"
REGIONS = ["JP", "KR", "SC", "TC", "HK"]  # face order in the source OTC
WEIGHTS = {"Regular": (340, 345), "Bold": (590, 610)}  # (Noto wght, Inter wght)
INTER_OPSZ = 14

# blocks whose code points Inter supplies where it has them
LETTERS = [
    (0x0020, 0x007E),  # Basic Latin
    (0x00A0, 0x036F),  # Latin-1 .. combining marks
    (0x0370, 0x052F),  # Greek, Cyrillic
    (0x1D00, 0x1FFF),  # phonetic, Latin Extended Additional, Greek Extended
    (0x2000, 0x206F),  # General Punctuation
    (0x2070, 0x20CF),  # super/subscripts, currency
    (0x2C60, 0x2C7F),
    (0xA720, 0xA7FF),
    (0xAB30, 0xAB6F),
    (0xFB00, 0xFB06),  # Latin ligatures
]
# CJK text sets these with the ideographs: dashes, curly quotes, the
# ellipsis and the bopomofo tone marks stay Noto's even where narrow,
# as does anything Noto draws full width in any region
NOTO_ALWAYS = {0x2013, 0x2014, *range(0x2018, 0x2020), 0x2026, 0x2C7, 0x2C9, 0x2CA, 0x2CB, 0x2D9}
INTER_FEATURES = ["ccmp", "locl", "kern", "mark", "mkmk", "tnum", "case"]
# Old Hangul jamo shaping keeps ~1900 glyphs alive; dropping it makes
# room for Inter under the 65535-glyph limit (modern Hangul syllables
# are precomposed and unaffected)
DROP_NOTO_FEATURES = {"ljmo", "vjmo", "tjmo"}
# tables every face takes from the first, so the OTC stores them once
SHARED = ("glyf", "loca", "hmtx", "vmtx", "hhea", "vhea", "maxp", "post", "GDEF", "BASE")

COPYRIGHT = (
    "Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font "
    "Name 'Source'. Copyright 2016 The Inter Project Authors "
    "(https://github.com/rsms/inter). Copyright 2026 Caffeine Type Foundry."
)
LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, "
    'Version 1.1. This Font Software is distributed on an "AS IS" BASIS, '
    "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. "
    "See the SIL Open Font License for the specific language, permissions "
    "and limitations governing your use of this Font Software."
)


def fetch():
    """Download the pinned sources once; always check their hashes."""
    for path, (url, sha) in SOURCES.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            print(f"downloading {url}")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sha:
            sys.exit(f"{path}: sha256 {digest}, expected {sha}")


def load_inter():
    with zipfile.ZipFile(INTER_ZIP) as z:
        return TTFont(io.BytesIO(z.read("InterVariable.ttf")))


def noto_subsetter(font, unicodes, gids=()):
    tags = {r.FeatureTag for t in ("GSUB", "GPOS") for r in font[t].table.FeatureList.FeatureRecord}
    opts = subset.Options()
    opts.layout_features = sorted(tags - DROP_NOTO_FEATURES)
    opts.layout_scripts = ["*"]
    opts.name_IDs, opts.name_languages, opts.name_legacy = ["*"], ["*"], True
    opts.notdef_outline, opts.glyph_names, opts.hinting = True, True, True
    s = subset.Subsetter(opts)
    s.populate(unicodes=unicodes, gids=gids)
    return s


def plan():
    """Code points Inter supplies, and the Noto glyphs every region keeps.

    Each region reaches different glyphs through its own GSUB, but the
    faces must share one glyph set, so every face keeps the union. The
    source has no glyph names, and fontTools derives them from each
    face's cmap, so the union is taken over glyph IDs.
    """
    cmaps, keep = [], set(NOTO_ALWAYS)
    for n in range(len(REGIONS)):
        f = TTFont(NOTO, fontNumber=n, lazy=True)
        cmap = f.getBestCmap()
        cmaps.append(cmap)
        keep |= {cp for cp, g in cmap.items() if f["hmtx"][g][0] == 1000}
    noto_cps = set().union(*cmaps)
    inter = set(load_inter().getBestCmap())
    letters = {cp for cp in inter if any(lo <= cp <= hi for lo, hi in LETTERS)}
    # outside the letter blocks Inter only fills gaps; never its PUA icons
    gaps = {cp for cp in inter - noto_cps if not 0xE000 <= cp <= 0xF8FF}
    from_inter = (letters - keep) | gaps

    gids = set()
    for n, cmap in enumerate(cmaps):
        f = TTFont(NOTO, fontNumber=n)
        ids = {name: i for i, name in enumerate(f.getGlyphOrder())}
        noto_subsetter(f, set(cmap) - from_inter).subset(f)
        gids |= {ids[name] for name in f.getGlyphOrder()}
        print(f"  closure {REGIONS[n]}: {len(gids)} glyphs", flush=True)
    return from_inter, gids


def spread_langsys(inter, noto):
    """Register Inter's features under every language Noto has for
    DFLT, latn, grek and cyrl; otherwise text tagged Chinese or
    Japanese selects Noto's language systems and loses Inter's kern."""
    for tag in ("GSUB", "GPOS"):
        it, nt = inter[tag].table, noto[tag].table
        recs = {r.ScriptTag: r for r in it.ScriptList.ScriptRecord}
        base = (recs.get("latn") or recs["DFLT"]).Script.DefaultLangSys
        for nrec in nt.ScriptList.ScriptRecord:
            if nrec.ScriptTag not in ("DFLT", "latn", "grek", "cyrl"):
                continue
            rec = recs.get(nrec.ScriptTag)
            if rec is None:
                rec = ot.ScriptRecord()
                rec.ScriptTag = nrec.ScriptTag
                rec.Script = ot.Script()
                rec.Script.DefaultLangSys = copy.deepcopy(base)
                rec.Script.LangSysRecord = []
                it.ScriptList.ScriptRecord.append(rec)
                recs[rec.ScriptTag] = rec
            have = {r.LangSysTag for r in rec.Script.LangSysRecord}
            for nl in nrec.Script.LangSysRecord:
                if nl.LangSysTag not in have:
                    r = ot.LangSysRecord()
                    r.LangSysTag = nl.LangSysTag
                    r.LangSys = copy.deepcopy(rec.Script.DefaultLangSys or base)
                    rec.Script.LangSysRecord.append(r)
            rec.Script.LangSysRecord.sort(key=lambda r: r.LangSysTag)
            rec.Script.LangSysCount = len(rec.Script.LangSysRecord)
        it.ScriptList.ScriptRecord.sort(key=lambda r: r.ScriptTag)
        it.ScriptList.ScriptCount = len(it.ScriptList.ScriptRecord)


def build_inter(wght, cps, noto):
    """Inter at one weight, cut to cps, in Noto's units and layout."""
    font = load_inter()
    instancer.instantiateVariableFont(
        font,
        {"wght": wght, "opsz": INTER_OPSZ},
        inplace=True,
        overlap=instancer.OverlapMode.REMOVE,
    )
    opts = subset.Options()
    opts.layout_features = INTER_FEATURES
    opts.glyph_names = True
    s = subset.Subsetter(opts)
    s.populate(unicodes=cps)
    s.subset(font)
    scale_upem(font, noto["head"].unitsPerEm)

    # Noto's vertical metrics: advance 1000, origin at the typo ascender
    font["vhea"] = vhea = newTable("vhea")
    vars(vhea).update(vars(noto["vhea"]))
    font["vmtx"] = vmtx = newTable("vmtx")
    vmtx.metrics = {}
    glyf, top = font["glyf"], noto["OS/2"].sTypoAscender
    for name in font.getGlyphOrder():
        g = glyf[name]
        g.recalcBounds(glyf)
        vmtx.metrics[name] = (noto["head"].unitsPerEm, top - getattr(g, "yMax", 0))
    spread_langsys(font, noto)
    return font


def rename(font, region, style):
    family = f"Inksans CJK {region}"
    ps = f"InksansCJK{region.lower()}-{style}"
    designer = font["name"].getDebugName(9)
    name = font["name"]
    name.names = []
    for nid, s in (
        (0, COPYRIGHT),
        (1, family),
        (2, style),
        (3, f"{VERSION};NONE;{ps}"),
        (4, f"{family} {style}"),
        (5, f"Version {VERSION}"),
        (6, ps),
        (8, "Caffeine Type Foundry"),
        (9, f"{designer}; Rasmus Andersson (Inter)"),
        (13, LICENSE),
        (14, "https://openfontlicense.org"),
    ):
        name.setName(s, nid, 3, 1, 0x409)

    bold = style == "Bold"
    os2 = font["OS/2"]
    os2.usWeightClass = 700 if bold else 400
    os2.achVendID = "NONE"
    os2.fsSelection = os2.fsSelection & ~0x61 | (0x20 if bold else 0x40)
    font["head"].macStyle = 1 if bold else 0
    font["head"].fontRevision = float(VERSION)


def build_face(job):
    """One region at one weight, merged, into a temporary TTF."""
    n, style, from_inter, keep_gids, tmp = job
    noto_wght, inter_wght = WEIGHTS[style]
    region = REGIONS[n]
    noto = TTFont(NOTO, fontNumber=n)
    if not noto["name"].getDebugName(1).endswith(region):
        raise ValueError(f"face {n} is not {region}")
    instancer.instantiateVariableFont(noto, {"wght": noto_wght}, inplace=True)
    noto_subsetter(noto, set(noto.getBestCmap()) - from_inter, keep_gids).subset(noto)
    # glyphs kept for other regions keep their code points too; the ones
    # Inter supplies must go, or the merge keeps Noto's (U+00A0, U+2011)
    for table in noto["cmap"].tables:
        for cp in from_inter & set(table.cmap):
            del table.cmap[cp]
    inter = build_inter(inter_wght, from_inter, noto)

    parts = [Path(tmp) / f"{style}-{n}.{p}.ttf" for p in ("noto", "inter")]
    noto.save(parts[0])
    inter.save(parts[1])
    font = Merger().merge(parts)
    for tag in ("DSIG", "STAT"):
        if tag in font:
            del font[tag]
    rename(font, region, style)
    if n == 0:
        # Variable masters draw crossing strokes as overlapping
        # contours, which some rasterizers fill as holes. The other
        # faces take these outlines (see SHARED).
        removeOverlaps(font)
    # the faces share outlines by glyph ID, so their glyph orders must
    # match; names differ per face (see plan), metrics do not
    hmtx = font["hmtx"]
    order = hashlib.sha256(repr([hmtx[g] for g in font.getGlyphOrder()]).encode()).hexdigest()
    font["post"].formatType = 3.0  # no glyph names: 64k of them is 1 MB
    path = Path(tmp) / f"{style}-{n}.ttf"
    font.save(path)
    return path, order


def main():
    fetch()
    OUT.mkdir(exist_ok=True)
    from_inter, keep_gids = plan()
    print(f"{len(from_inter)} code points from Inter", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [
            (n, style, from_inter, keep_gids, tmp) for style in WEIGHTS for n in range(len(REGIONS))
        ]
        # each instance peaks near 4 GB; two at a time stays within 8 GB
        with Pool(int(os.environ.get("INKSANS_JOBS", "2"))) as pool:
            faces = pool.map(build_face, jobs)
        for style in WEIGHTS:
            done = [(p, o) for p, o in faces if p.name.startswith(f"{style}-")]
            if len({o for _, o in done}) != 1:
                sys.exit(f"{style}: regions ended up with different glyph orders")
            fonts = [TTFont(p, lazy=True) for p, _ in done]
            # copy compiled bytes, not table objects: those are keyed by
            # glyph names, which differ per face
            for tag in SHARED:
                if tag in fonts[0]:
                    raw = fonts[0].reader[tag]
                    for f in fonts[1:]:
                        f[tag] = DefaultTable(tag)
                        f[tag].data = raw
            ttc = TTCollection()
            ttc.fonts = fonts
            out = OUT / f"InksansCJK-{style}.ttc"
            ttc.save(out, shareTables=True)  # identical tables stored once
            print(f"{out}: {len(fonts)} faces, {out.stat().st_size // 1048576} MB", flush=True)


if __name__ == "__main__":
    main()
