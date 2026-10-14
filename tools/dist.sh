#!/bin/sh
# package Inkscreen for release: build/inkscreen-VERSION.zip
set -eu
cd "$(dirname "$0")/.."
v=$(python3 -c 'import sys; sys.path.insert(0, "tools"); import mkinkscreen; print(mkinkscreen.VERSION)')
out=build/inkscreen-$v
rm -rf "$out" "$out.zip"
mkdir -p "$out"
python3 tools/mkinkscreen.py >/dev/null
cp fonts/inkscreen14.bdf fonts/inkscreen14b.bdf fonts/OFL.txt "$out/"
cp fonts/README-inkscreen.txt "$out/README.txt"
uv run -q --with fonttools --with skia-pathops python -I tools/bdf2ttf.py "$out" \
    fonts/inkscreen14.bdf fonts/inkscreen14b.bdf
(cd build && zip -qrX "inkscreen-$v.zip" "inkscreen-$v")
echo "$out.zip"
