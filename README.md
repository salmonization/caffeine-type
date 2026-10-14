# Caffeine Type

Bitmap fonts from Caffeine Type Foundry, and the tools that build them.

## Inkscreen 14

A screen font in Regular and Bold: a 14-row design (cap height 10,
x-height 7, descenders 3) in an 8x16 cell, after the 1980s
workstation screen fonts. Regular is 8 px wide, Bold 9 px; the left
column of every glyph is empty, so letters never touch. Covers ASCII
and Latin-1. It is GNU Unifont with the Latin glyphs redrawn.

- `fonts/inkscreen14.bdf`, `fonts/inkscreen14b.bdf` - the fonts
- `tools/mkinkscreen.py` - builds them from Unifont and the hand edits
  in `tools/inkscreen-overrides.txt`
- `tools/inkscreenedit.py` - pixel editor in the browser
- `tools/bdf2ttf.py` - BDF to pixel-outline TrueType

Release packages (BDF, TTF, license) come from `tools/dist.sh`.

## License

The fonts are licensed under the SIL Open Font License 1.1
([fonts/OFL.txt](fonts/OFL.txt)). The tools are BSD-2-Clause
([LICENSE](LICENSE)).
