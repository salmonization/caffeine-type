"""Checks for tools/mkinkscreen.py: python3 tools/test_mkinkscreen.py"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mkinkscreen as m


def test_overrides_roundtrip():
    # a row starting with '#' must not be mistaken for a comment
    rows = {y: 0 for y in range(m.TOP, m.BOTTOM - 1, -1)}
    rows[5], rows[0], rows[-3] = 0b10000001, 0xFF, 0b01111110
    bold = {y: v << 1 | 1 for y, v in rows.items()}  # 9 wide, x 8 inked
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "o.txt"
        m.write_overrides(path, {ord("#"): rows}, {ord("a"): bold})
        assert "#########" in path.read_text()
        got_regular, got_bold = m.read_overrides(path)
        assert got_regular == {ord("#"): rows}
        assert got_bold == {ord("a"): bold}

        # 8-wide bold blocks from before bold went 9 wide gain an empty x 8
        path.write_text("U+0041 bold\n" + "#.......\n" * 14)
        assert m.read_overrides(path)[1][0x41][0] == 0b100000000


def test_embolden():
    # 9 wide, thickened right, never clipped
    assert m.embolden({0: 0b01000000}) == {0: 0b011000000}
    assert m.embolden({0: 0b00000001}) == {0: 0b000000011}
    assert m.embolden({0: 0b10000001}) == {0: 0b110000011}


def test_check():
    assert m.check({0x41: {0: 0b01000000}}, {0x41: {0: 0b011000000}}) == []
    assert m.check({0x41: {0: 0b10000000}}, {0x41: {0: 0b100000000}}) != []


def test_auto_metrics():
    auto = m.auto_regular([])
    x_top, x_bottom = m.ink(auto[ord("x")])
    assert (x_top, x_bottom) == (6, 0)  # x-height 7
    assert m.ink(auto[ord("g")])[1] == -3  # descender 3
    assert m.ink(auto[ord("H")]) == (9, 0)  # caps untouched
    for rows in auto.values():
        assert all(m.BOTTOM <= y <= m.TOP for y, v in rows.items() if v)


def test_derived_bold_follows_bold_base():
    # a hand-drawn bold n must show up in bold ñ, not emboldened regular
    regular = m.auto_regular([])
    n_bold = {y: v | (1 << 8 if y == 0 else 0) for y, v in m.embolden(regular[ord("n")]).items()}
    bold = m.auto_bold(regular, {ord("n"): n_bold})
    assert all(bold[0xF1][y] == v for y, v in n_bold.items() if y <= 0)
    assert bold[0xB5][-2] == m.embolden(regular[ord("p")])[-2]  # µ takes p's stem


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
