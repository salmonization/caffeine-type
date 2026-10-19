#!/bin/sh
# package a font family for release: build/FAMILY-VERSION.zip
# (Inksans: also build/inksans-VERSION-W1.zip .. W8.zip, one weight each)
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
    # ~15 minutes: instances Noto Sans CJK and Inter, merges them
    uv run -q --with fonttools --with skia-pathops python -I tools/mkinksans.py
    uv run -q --with fonttools --with skia-pathops python -I tools/test_mkinksans.py
    cp build/InksansCJK-W?.ttc "$out/"
    cp fonts/OFL-inksans.txt "$out/OFL.txt"
    # and one zip per weight: each is 22 MB, many want only one or two
    for w in W1 W2 W3 W4 W5 W6 W7 W8; do
        d=build/$family-$v-$w
        rm -rf "$d" "$d.zip"
        mkdir -p "$d"
        cp "build/InksansCJK-$w.ttc" "$d/"
        cp fonts/OFL-inksans.txt "$d/OFL.txt"
        cp fonts/README-inksans.txt "$d/README.txt"
        (cd build && zip -qrX "$family-$v-$w.zip" "$family-$v-$w")
        echo "$d.zip"
    done
    ;;
*)
    echo "unknown family: $family" >&2
    exit 2
    ;;
esac
cp "fonts/README-$family.txt" "$out/README.txt"
(cd build && zip -qrX "$family-$v.zip" "$family-$v")
echo "$out.zip"
