# Caffeine Type

Bitmap fonts from Caffeine Type Foundry, and the tools that build them.

## Inkscreen 14

A screen font in Regular and Bold, based on GNU Unifont. Unifont's
Latin glyphs use 16 rows; Inkscreen fits them into 14 (x-height 8 -> 7
rows, descenders 2 -> 3, accents moved to suit) in the same 8x16
cell, and changes some details by hand. Bold is 9 px wide, so the
extra stroke pixel never closes the empty column between letters.
Covers ASCII and Latin-1.

The glyphs changed by hand, next to Unifont:

![Unifont and Inkscreen side by side](docs/inkscreen-vs-unifont.png)

- `fonts/inkscreen14.bdf`, `fonts/inkscreen14b.bdf` - the fonts
- `tools/mkinkscreen.py` - builds them from Unifont and the hand edits
  in `tools/inkscreen-overrides.txt`
- `tools/inkscreenedit.py` - pixel editor in the browser
- `tools/bdf2ttf.py` - BDF to pixel-outline TrueType
- `tools/mkcompare.py` - the overview image above

Release packages (BDF, TTF, license) come from `tools/dist.sh`.

## License

The fonts are licensed under the SIL Open Font License 1.1
([fonts/OFL.txt](fonts/OFL.txt)). The tools are BSD-2-Clause
([LICENSE](LICENSE)).
