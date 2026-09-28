# SCALP LAB V4 — rapport de recherche

- Données : Binance USD-M
- TRAIN : 180 jours
- TEST : 45 jours
- STEP : 45 jours
- FINAL HOLDOUT : 45 jours
- Coût taker : 0.05%/côté
- Coût maker : 0.02%/côté

## Walk-forward OOS

### 5m

| mesure | valeur |
|---|---:|
| folds | 9 |
| test mean/trade | -0.0379% |
| folds positifs | 3/9 |
| PF médian | 0.64 |
| DD médian | -1.5545% |
| médiane trade | -0.0579% |

### 15m

| mesure | valeur |
|---|---:|
| folds | 9 |
| test mean/trade | -0.0873% |
| folds positifs | 2/9 |
| PF médian | 0.80 |
| DD médian | -2.7557% |
| médiane trade | -0.2939% |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 5m | -0.0675% | 0.59 | -0.8207% | 13 | -0.8787% |
| ETHUSDT | 5m | -0.0162% | 0.90 | -1.9458% | 31 | -0.5187% |
| SOLUSDT | 5m | -0.1080% | 0.63 | -2.1710% | 11 | -1.1953% |
| BTCUSDT | 15m | +0.0117% | 1.06 | -3.1781% | 38 | +0.4050% |
| ETHUSDT | 15m | -0.3018% | 0.34 | -8.7062% | 29 | -8.4481% |
| SOLUSDT | 15m | -0.2481% | 0.49 | -2.4152% | 11 | -2.7297% |

## Benchmarks

| intervalle | stratégie mean | benchmark mécanique |
|---|---:|---:|
| 5m | -0.0379% | -0.1858% |
| 15m | -0.0873% | -0.2187% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.0626% | 0.75 | -2.2566% |
| fees+100% | -0.1237% | 0.59 | -2.7998% |
| fees+25% | -0.0779% | 0.71 | -2.3488% |
| fees+50% | -0.0931% | 0.67 | -2.4940% |
| fees+50%_slip+100% | -0.1066% | 0.65 | -2.6413% |
| slip+100% | -0.0759% | 0.73 | -2.3539% |
| slip+50% | -0.0686% | 0.74 | -2.2972% |

## Distribution des stratégies sélectionnées

### signal

{'pullback rsi=35': 10, 'pullback rsi=40': 4, 'donchian n=50 vol=1.5': 4}

### regime

{'range': 7, 'trend': 6, 'all': 5}

### profile

{'maker_both': 16, 'maker_tp': 2}

## Limites

- OHLCV uniquement.
- Pas de carnet d'ordres.
- Exécution maker approximée.
- Pas de funding.
- Pas de latence réseau réelle.
- Ambiguïté intrabougie TP/SL résolue par priorité au SL.
- Monte-Carlo basé sur les trades observés.
- Le FINAL HOLDOUT n'est pas utilisé pour la sélection.

## Interprétation

V4 ne considère pas une stratégie comme validée sur la seule base d'un fold positif. La confirmation doit survivre à plusieurs folds OOS, aux coûts et au FINAL HOLDOUT.
