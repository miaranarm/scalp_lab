# SCALP LAB V4.2 — Diagnostic V4.1

V4.2 analyse les résultats V4.1 sans modifier
la sélection originale ni réutiliser le FINAL HOLDOUT.

## OOS global

- Folds OOS : 66
- Mean/trade : -0.0894%
- Médiane trade : -0.1047%
- PF médian : 0.67
- DD médian : -3.9921%
- Random : -0.0849%
- Edge vs random : -0.0045%
- Folds positifs : 12/66
- Folds > random : 31/66

## Signal

| signal | folds | mean | edge/random | +folds | PF |
|---|---:|---:|---:|---:|---:|
| donchian n=20 vol=0.0 | 8 | -0.0006% | 0.0900% | 1/8 | 0.78 |
| donchian n=50 vol=1.5 | 10 | -0.0626% | 0.0037% | 3/10 | 0.71 |
| pullback rsi=40 | 11 | -0.1019% | -0.0020% | 1/11 | 0.62 |
| pullback rsi=35 | 19 | -0.1021% | -0.0088% | 4/19 | 0.67 |
| breakout n=20 | 11 | -0.0784% | -0.0153% | 2/11 | 0.74 |
| donchian n=20 vol=1.5 | 4 | -0.1387% | -0.0674% | 1/4 | 0.67 |
| vwap n=48 k=3.0 | 3 | -0.2629% | -0.1425% | 0/3 | 0.52 |

## Régimes

| régime | folds | mean | edge/random | PF |
|---|---:|---:|---:|---:|
| all | 14 | -0.1457% | -0.0440% | 0.56 |
| range | 33 | -0.0868% | -0.0110% | 0.65 |
| trend | 19 | -0.0523% | 0.0359% | 0.77 |

## Intervalles

| intervalle | folds | mean | edge/random | PF |
|---|---:|---:|---:|---:|
| 15m | 33 | -0.1092% | -0.0215% | 0.71 |
| 5m | 33 | -0.0695% | 0.0125% | 0.65 |

## FINAL HOLDOUT

Le holdout est descriptif uniquement.
Il n'intervient jamais dans la sélection V4.2.

- BTCUSDT 5m : mean=0.0016%, PF=1.01, n=12
- ETHUSDT 5m : mean=-0.1337%, PF=0.46, n=91
- SOLUSDT 5m : mean=-0.1080%, PF=0.63, n=11
- BTCUSDT 15m : mean=-0.1744%, PF=0.38, n=41
- ETHUSDT 15m : mean=-0.1864%, PF=0.51, n=60
- SOLUSDT 15m : mean=-0.3202%, PF=0.36, n=29

## Fichiers

- v42_global.csv
- v42_by_symbol.csv
- v42_by_interval.csv
- v42_by_signal.csv
- v42_by_regime.csv
- v42_by_profile.csv
- v42_by_exit.csv
- v42_by_symbol_interval.csv
- v42_by_signal_regime.csv
- v42_by_signal_interval.csv
- v42_stability.csv
- v42_train_test.csv
- v42_trade_count.csv
- v42_holdout.csv