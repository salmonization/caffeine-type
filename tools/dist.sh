#!/bin/sh
# package a font family for release: build/FAMILY-VERSION.zip
set -eu
cd "$(dirname "$0")/.."
family=${1:?usage: tools/dist.sh inkscreen|inksans}
v=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "tools/mk$family.py")
out=build/$family-$v
rm -rf "$out" "$out.zip"
mkdir -p "$out"
case $family in
inkscreen)
    python3 tools/mkinkscreen.py >/dev/null
    cp fonts/inkscreen14.bdf fonts/inkscreen14b.bdf fonts/OFL.txt "$out/"
    uv run -q --with fonttools --with skia-pathops python -I tools/bdf2ttf.py "$out" \
        fonts/inkscreen14.bdf fonts/inkscreen14b.bdf
    ;;
inksans)
    # a few minutes: instances Noto Sans CJK and Inter, merges them
    uv run -q --with fonttools --with skia-pathops python -I tools/mkinksans.py
    uv run -q --with fonttools --with skia-pathops python -I tools/test_mkinksans.py
    cp build/InksansCJK-Regular.ttc build/InksansCJK-Bold.ttc "$out/"
    cp fonts/OFL-inksans.txt "$out/OFL.txt"
    ;;
*)
    echo "unknown family: $family" >&2
    exit 2
    ;;
esac
cp "fonts/README-$family.txt" "$out/README.txt"
(cd build && zip -qrX "$family-$v.zip" "$family-$v")
echo "$out.zip"
