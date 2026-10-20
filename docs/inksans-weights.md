# Inksans CJK weights

Inksans CJK W1 to W8 match the stroke weights of Hiragino Sans W1 to
W8. W numbers are not a standard. Each Japanese foundry has its own
scale, and DynaFont goes to W12. Thus Inksans follows one family:
Hiragino Sans, the CJK font of macOS and iOS.

## Method

`tools/measureweights.py` measures Hiragino Sans and the weight axis
of Noto Sans CJK (100 to 900, in steps of 5). It uses three measures:

- 一 and 丨: the stroke thickness through the middle of the
  character, per 1000 units of em. The script cuts a cross-section
  and does not use the bounding box. The flared ends of the strokes
  make the bounding box too thick.
- Ink: the mean area of 永国東語書道愛識鬱あのカ, in % of the em square.

For each Hiragino weight, the script gives the closest Noto weight on
each measure. At W1, W6 and W7 the measures do not agree. At these
weights, the vertical strokes of Hiragino are heavier than its
horizontal strokes, more than in Noto. Inksans uses a weight between
the measures.

## Results

Noto Sans CJK 2.004 (variable), Hiragino Sans 20.0d1e1 (macOS 15).

| Hiragino | 一 | 丨 | ink % | Noto by 一 | by 丨 | by ink | Inksans |
|---|---|---|---|---|---|---|---|
| W0 | 20 | 22 | 10.4 | - | - | - | - |
| W1 | 45 | 49 | 18.6 | 220 | 285 | 215 | 250 |
| W2 | 56 | 58 | 22.4 | 305 | 315 | 305 | 315 |
| W3 | 69 | 70 | 27.0 | 340 | 345 | 340 | 340 |
| W4 | 85 | 85 | 31.8 | 415 | 420 | 415 | 415 |
| W5 | 102 | 100 | 36.9 | 495 | 485 | 490 | 490 |
| W6 | 118 | 123 | 43.4 | 605 | 640 | 645 | 620 |
| W7 | 137 | 145 | 49.9 | 740 | 795 | 815 | 780 |
| W8 | 158 | 170 | 56.7 | 895 | - | - | 900 |
| W9 | 182 | 198 | 64.4 | - | - | - | - |
| Noto 100 | 33 | 30 | 14.6 | | | | |
| Noto 400 | 82 | 81 | 30.9 | | | | |
| Noto 700 | 131 | 131 | 45.5 | | | | |
| Noto 900 | 159 | 160 | 53.0 | | | | |

A "-" cell means that the Hiragino weight is outside the Noto axis.
W0 is lighter than Noto 100, and W9 is heavier than Noto 900. Thus
Inksans has no W0 or W9. W8 at Noto 900 matches on 一, but it has
about 7% less ink.

The Regular weight of Noto (400) is close to W4. The Bold weight of
Noto (700) is between W6 and W7. Thus text for Hiragino W3 and W6
becomes lighter or darker in Noto Sans CJK. In Inksans, the text
keeps its weight.

## Latin

Inter replaces the Latin, Greek and Cyrillic of Noto. For each Noto
weight, Inksans uses the Inter weight (optical size 14) whose stem of
"I" matches the "I" of Noto. `WEIGHTS` in `tools/mkinksans.py` holds
the two weights.

Hiragino is a trademark of SCREEN Holdings Co., Ltd. Inksans CJK
contains no Hiragino outlines. We only measured the weights of
Hiragino Sans.
