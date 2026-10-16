# Caffeine Type

Bitmap fonts by Caffeine Type Foundry (BDF foundry `Caffeine`); every
font name takes the `Ink` prefix. Fonts are OFL 1.1, tools BSD-2.
Inkscreen ships inside InkView (`../../Kindle/InkView/fonts/`); copy the
BDFs there after a rebuild.

## Commands

```sh
python3 tools/mkinkscreen.py          # rebuild fonts/inkscreen14*.bdf
python3 tools/inkscreenedit.py        # pixel editor, http://127.0.0.1:8765/
python3 tools/test_mkinkscreen.py     # generator checks
uv run --with fonttools --with skia-pathops python -I tools/test_bdf2ttf.py  # TTF == BDF
tools/dist.sh                         # build/inkscreen-VERSION.zip
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

Plan 9 bitmap fonts are not all MIT: `luc`, `lucm`, `lucsans`, `pelm`
are B&H (no derivatives); only `misc`/`fixed` (X11) are free.
