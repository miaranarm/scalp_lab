# SCALP LAB V4.3 — EDGE ISOLATION

V4.3 analyse uniquement les résultats V4.1.

**Aucune nouvelle stratégie n'est optimisée.**

Le FINAL HOLDOUT est conservé hors sélection.

## Global OOS

- Folds : 66
- Mean/trade : -0.0894%
- Médiane : -0.1047%
- PF médian : 0.67
- DD médian : -3.9921%
- Random : -0.0849%
- Edge : -0.0045%
- Folds positifs : 12/66
- Folds > random : 31/66

## Combinaisons OOS

Les combinaisons ci-dessous sont descriptives.
Elles ne constituent pas une sélection de trading.

| symbole | TF | signal | régime | folds | mean | edge | +folds | PF |
|---|---|---|---|---:|---:|---:|---:|---:|
| ETHUSDT | 15m | donchian n=20 vol=0.0 | range | 3 | +0.2447% | +0.3195% | 1/3 | 0.81 |
| SOLUSDT | 5m | pullback rsi=35 | trend | 3 | +0.0228% | +0.1032% | 1/3 | 0.96 |
| ETHUSDT | 15m | donchian n=20 vol=0.0 | trend | 1 | -0.0319% | +0.0714% | 0/1 | 0.93 |
| ETHUSDT | 5m | donchian n=50 vol=1.5 | range | 4 | +0.0203% | +0.0596% | 2/4 | 1.06 |
| BTCUSDT | 15m | pullback rsi=40 | all | 2 | -0.0519% | +0.0587% | 1/2 | 0.84 |
| BTCUSDT | 5m | pullback rsi=35 | trend | 5 | -0.0309% | +0.0555% | 2/5 | 0.73 |
| SOLUSDT | 5m | breakout n=20 | trend | 1 | -0.0379% | +0.0472% | 0/1 | 0.89 |
| BTCUSDT | 5m | pullback rsi=35 | all | 3 | -0.0449% | +0.0341% | 1/3 | 0.58 |
| BTCUSDT | 15m | pullback rsi=40 | trend | 1 | -0.0759% | +0.0280% | 0/1 | 0.77 |
| BTCUSDT | 5m | pullback rsi=40 | trend | 3 | -0.0667% | +0.0269% | 0/3 | 0.65 |
| SOLUSDT | 5m | donchian n=20 vol=0.0 | range | 1 | -0.0686% | +0.0239% | 0/1 | 0.76 |
| SOLUSDT | 15m | pullback rsi=40 | all | 1 | -0.0822% | +0.0206% | 0/1 | 0.86 |
| BTCUSDT | 15m | donchian n=50 vol=1.5 | trend | 1 | -0.0549% | +0.0141% | 0/1 | 0.85 |
| BTCUSDT | 15m | donchian n=20 vol=0.0 | trend | 2 | -0.0963% | -0.0077% | 0/2 | 0.66 |
| ETHUSDT | 15m | breakout n=20 | range | 1 | -0.0078% | -0.0133% | 0/1 | 0.98 |

## Combinaisons les plus faibles

| symbole | TF | signal | régime | folds | mean | edge | PF |
|---|---|---|---|---:|---:|---:|---:|
| ETHUSDT | 5m | pullback rsi=40 | range | 4 | -0.1647% | -0.0671% | 0.34 |
| SOLUSDT | 15m | pullback rsi=35 | all | 4 | -0.1915% | -0.0693% | 0.70 |
| SOLUSDT | 15m | donchian n=20 vol=1.5 | range | 3 | -0.1501% | -0.0782% | 0.70 |
| BTCUSDT | 15m | vwap n=48 k=3.0 | trend | 1 | -0.1686% | -0.0885% | 0.55 |
| SOLUSDT | 5m | vwap n=48 k=3.0 | range | 1 | -0.1665% | -0.0886% | 0.52 |
| ETHUSDT | 5m | pullback rsi=35 | all | 2 | -0.2064% | -0.0945% | 0.41 |
| BTCUSDT | 15m | pullback rsi=35 | all | 1 | -0.2199% | -0.1676% | 0.38 |
| ETHUSDT | 15m | pullback rsi=35 | all | 1 | -0.3210% | -0.2229% | 0.36 |
| SOLUSDT | 15m | vwap n=48 k=3.0 | range | 1 | -0.4536% | -0.2506% | 0.34 |
| SOLUSDT | 15m | donchian n=20 vol=0.0 | range | 1 | -0.4455% | -0.3184% | 0.34 |

## Stabilité

Top combinaisons avec plusieurs observations :

| symbole | TF | signal | régime | folds | + | edge | score |
|---|---|---|---|---:|---:|---:|---:|
| SOLUSDT | 5m | pullback rsi=35 | trend | 3 | 1/3 | +0.1032% | 0.498 |
| ETHUSDT | 15m | donchian n=20 vol=0.0 | range | 3 | 1/3 | +0.3195% | 0.446 |
| ETHUSDT | 5m | donchian n=50 vol=1.5 | range | 4 | 2/4 | +0.0596% | 0.368 |
| BTCUSDT | 5m | pullback rsi=35 | trend | 5 | 2/5 | +0.0555% | 0.367 |
| BTCUSDT | 5m | pullback rsi=35 | all | 3 | 1/3 | +0.0341% | 0.360 |
| BTCUSDT | 5m | pullback rsi=40 | trend | 3 | 0/3 | +0.0269% | 0.358 |
| SOLUSDT | 15m | donchian n=20 vol=1.5 | range | 3 | 1/3 | -0.0782% | 0.210 |
| SOLUSDT | 5m | breakout n=20 | range | 5 | 1/5 | -0.0171% | 0.205 |
| ETHUSDT | 15m | donchian n=50 vol=1.5 | range | 4 | 1/4 | -0.0382% | 0.164 |
| SOLUSDT | 15m | pullback rsi=35 | all | 4 | 0/4 | -0.0693% | 0.154 |
| ETHUSDT | 5m | pullback rsi=40 | range | 4 | 0/4 | -0.0671% | 0.067 |

## FINAL HOLDOUT

Le holdout reste strictement descriptif.

- BTCUSDT 5m : +0.0016%, PF=1.01, n=12
- ETHUSDT 5m : -0.1337%, PF=0.46, n=91
- SOLUSDT 5m : -0.1080%, PF=0.63, n=11
- BTCUSDT 15m : -0.1744%, PF=0.38, n=41
- ETHUSDT 15m : -0.1864%, PF=0.51, n=60
- SOLUSDT 15m : -0.3202%, PF=0.36, n=29

## Limitation

Le fichier walk_forward_v41.csv ne contient pas les trades individuels. V4.3 ne prétend donc pas analyser séparément LONG/SHORT ni la distribution trade par trade.

Une analyse LONG/SHORT et trade-level nécessitera une nouvelle sortie de recherche dédiée, sans toucher au FINAL HOLDOUT.

## Fichiers

- v43_global.csv
- v43_symbol.csv
- v43_interval.csv
- v43_signal.csv
- v43_regime.csv
- v43_profile.csv
- v43_symbol_interval.csv
- v43_signal_regime.csv
- v43_signal_interval.csv
- v43_signal_symbol.csv
- v43_regime_interval.csv
- v43_signal_regime_interval.csv
- v43_stability.csv
- v43_train_test.csv
- v43_trade_count.csv
- v43_combinations.csv
- v43_holdout.csv
