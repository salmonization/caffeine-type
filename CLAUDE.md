# Caffeine Type

Fonts by Caffeine Type Foundry (BDF foundry `Caffeine`); every
font name takes the `Ink` prefix. Fonts are OFL 1.1, tools BSD-2.
Inkscreen ships inside InkView (`../../Kindle/InkView/fonts/`); copy the
BDFs there after a rebuild.

## Commands

```sh
python3 tools/mkinkscreen.py          # rebuild fonts/inkscreen14*.bdf
python3 tools/inkscreenedit.py        # pixel editor, http://127.0.0.1:8765/
python3 tools/test_mkinkscreen.py     # generator checks
uv run --with fonttools --with skia-pathops python -I tools/test_bdf2ttf.py  # TTF == BDF
tools/dist.sh inkscreen               # build/inkscreen-VERSION.zip
uv run --with fonttools --with skia-pathops python -I tools/mkinksans.py  # build/InksansCJK-*.ttc, ~3 min
uv run --with fonttools --with skia-pathops python -I tools/test_mkinksans.py  # checks the OTCs
tools/dist.sh inksans                 # build/inksans-VERSION.zip
python3 tools/mkcompare.py docs/inkscreen-vs-unifont.png  # hand-tuned vs Unifont
uvx ruff format tools/*.py && uvx ruff check tools/*.py
```

Comparison chart and editor references (screen.r/b.14 are Sun fonts,
kept outside this repo and never copied into it):

```sh
R=../../Kindle/sunos-fonts/bdf/fixedwidthfonts
python3 tools/mkinkscreen.py --chart build/inkscreen-chart.png --ref $R/screen.r.14.bdf --refb $R/screen.b.14.bdf
python3 tools/inkscreenedit.py --ref $R/screen.r.14.bdf --refb $R/screen.b.14.bdf
```

## Inkscreen

Based on GNU Unifont: its 16-row Latin glyphs fitted into 14 rows
(ink rows 10..-3, x-height 8 -> 7, descenders 2 -> 3) in the same
8x16 cell (ascent 12, descent 4), with some details changed by hand.
Covers ASCII and Latin-1. Public text (README, package README) says
exactly that: based on Unifont, 16 -> 14 rows, some details changed;
never "redrawn" or a nod to old workstations. `VERSION` in
`mkinkscreen.py` goes into the BDF (`FONT_VERSION`) and the TTF name
table; bump it for each release.

- Accented letters: our base letter plus Unifont's mark, one blank
  row between; marks on capitals use row 11 and the capital loses one
  row (Å two). `µ`, `þ` are spliced from u, b, p; the soft hyphen
  copies `-`. Bold derived glyphs build on the bold bases
  (`auto_bold`).
- Override blocks (`tools/inkscreen-overrides.txt`) are 15 rows
  (11..-3); comments start with `;` since rows may start with `#`.
- Gap rule: column x 0 stays empty in every glyph. Regular is 8 wide,
  bold 9 (like screen.b.14). `mkinkscreen.py` reports violations.
- After hand edits, regenerate `docs/inkscreen-vs-unifont.png`
  (the README shows it).
- Licensing: a Unifont derivative under OFL 1.1; ship `fonts/OFL.txt`
  and never call it Unifont. No Reserved Font Name, so anyone may
  convert it (BDF -> PCF/TTF) without renaming. screen.r.14 is a visual
  reference only: do not copy Sun bitmaps.
- TTF: one square per pixel, unitsPerEm 1600, exact at 16 px; the
  family comes out as "Inkscreen 16" (pixel size). `test_bdf2ttf.py`
  samples outlines with fontTools: Pillow's text placement shifts tall
  glyphs by a pixel, so it is not used as the reference.

## Inksans CJK

Noto Sans CJK (= Source Han Sans, OFL 1.1, Reserved Font Name
"Source"; "Noto" is a Google trademark) plus Inter 4.1 (OFL 1.1, no
RFN) for Latin, Greek and Cyrillic. Sources are pinned by URL and
SHA-256 in `mkinksans.py` and downloaded to `fonts/src/{noto,inter}/`
(git-ignored). FreeSans is GPL and cannot be merged with an OFL font.

- Weights: Noto wght 340 / 590 (matched to Hiragino Sans W3/W6 by stem
  width and ink; Hiragino has more stroke contrast, so its W6 falls
  between Noto 545 by ink and 640 by vertical stems). Inter wght
  345 / 610 at opsz 14, whose stems match Noto's own Latin at 340/590
  (and Hiragino's Latin). No scaling: Inter's cap and x-height at 1000
  units are within 1% of Noto's Latin.
- Split: Inter supplies the letter blocks (`LETTERS`) and fills gaps
  Noto lacks (never its PUA). Noto keeps `NOTO_ALWAYS` (dashes, curly
  quotes, ellipsis, bopomofo tone marks) and anything it draws full
  width in any region (SC/TC/HK quotes, middle dot, × ÷ § ...).
- Glyph limit: Noto already has 65535 glyphs. Dropping Noto's Old
  Hangul jamo features (ljmo/vjmo/tjmo) frees ~1900; the merged faces
  have ~64900. Modern Hangul is precomposed and unaffected.
- One OTC per weight, five faces in source order JP KR SC TC HK. All
  faces keep the union of the regions' glyph closures (by glyph ID:
  the source has no glyph names and fontTools derives them per face
  from its cmap), merge the same Inter subset, and then take the
  compiled `SHARED` tables (glyf, hmtx, vmtx, ...) of the JP face as
  raw bytes, so the OTC stores them once. A metrics hash guards that
  the glyph orders really match.
- Inter's features (`INTER_FEATURES`; no calt, which turns `->` into
  an arrow) are registered under every language Noto has for DFLT,
  latn, grek, cyrl (`spread_langsys`); otherwise text tagged zh/ja
  picks Noto's language systems and loses Inter's kern.
- Inter glyphs get Noto's vertical metrics: advance 1000, origin at the
  typo ascender (880).
- Overlaps are removed (skia-pathops) on the JP face, whose outlines
  the others reuse: variable masters draw crossing strokes as
  overlapping contours, which some rasterizers (macOS Quick Look)
  fill as holes.
- `post` is format 3 (no glyph names; 64k names cost 1 MB).
- Names: `Inksans CJK <region>`, PostScript `InksansCJK<region>-<style>`,
  vendor `NONE`; "Noto", "Source", "Inter" only in the copyright and
  designer credits.

Plan 9 bitmap fonts are not all MIT: `luc`, `lucm`, `lucsans`, `pelm`
are B&H (no derivatives); only `misc`/`fixed` (X11) are free.
