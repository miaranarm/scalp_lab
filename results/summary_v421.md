# SCALP LAB V4.21 — FINAL HOLDOUT AUDIT

## Integrity
- Source: `results/walk_forward_v41.csv`
- OOS rows: 66
- FINAL rows: 6
- Missing required columns: none

## Rule
- The FINAL HOLDOUT is read-only confirmation data.
- No candidate, signal, regime, exit, profile or threshold is selected from FINAL.
- V4.21 does not reuse OOS observations as holdout.

## FINAL HOLDOUT

| symbol | interval | candidate | signal | regime | profile | TP | SL | hold | n | mean/trade | t | PF | DD | return |
|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 5m | 25 | pullback rsi=35 | trend | maker_both | 3 | 1.5 | 36 | 12 | +0.0016% | 0.02 | 1.01 | -0.74% | +0.01% |
| ETHUSDT | 5m | 17 | donchian n=50 vol=1.5 | range | maker_both | 3 | 1.5 | 36 | 91 | -0.1337% | -3.30 | 0.46 | -11.93% | -11.52% |
| SOLUSDT | 5m | 25 | pullback rsi=35 | trend | maker_both | 2 | 2 | 24 | 11 | -0.1080% | -0.69 | 0.63 | -2.17% | -1.20% |
| BTCUSDT | 15m | 27 | pullback rsi=40 | all | maker_both | 2 | 1 | 24 | 41 | -0.1744% | -2.97 | 0.38 | -7.13% | -6.93% |
| ETHUSDT | 15m | 11 | donchian n=20 vol=0.0 | range | maker_both | 3 | 1.5 | 36 | 60 | -0.1864% | -2.38 | 0.51 | -11.82% | -10.68% |
| SOLUSDT | 15m | 14 | donchian n=20 vol=1.5 | range | maker_both | 3 | 1.5 | 36 | 29 | -0.3202% | -2.59 | 0.36 | -8.54% | -8.94% |

## STATUS

**VALID — FINAL HOLDOUT FOUND AND KEPT SEPARATE FROM OOS SELECTION.**

V4.21 performs an integrity/confirmation audit only. It does not retune the strategy.
