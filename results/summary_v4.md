# SCALP LAB V4 (corrigé) — rapport de recherche

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
| test mean/trade | -0.0482% |
| folds positifs | 3/9 |
| PF médian | 0.64 |
| DD médian | -1.5545% |
| médiane trade | -0.0579% |
| mean/trade hasard (côté aléatoire) | -0.1057% |

### 15m

| mesure | valeur |
|---|---:|
| folds | 9 |
| test mean/trade | -0.0778% |
| folds positifs | 2/9 |
| PF médian | 0.84 |
| DD médian | -2.7557% |
| médiane trade | -0.2372% |
| mean/trade hasard (côté aléatoire) | -0.1990% |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | t | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 5m | -0.0675% | -0.8 | 0.59 | -0.8207% | 13 | -0.8787% |
| ETHUSDT | 5m | -0.0235% | -0.4 | 0.85 | -2.0686% | 31 | -0.7447% |
| SOLUSDT | 5m | -0.1080% | -0.7 | 0.63 | -2.1710% | 11 | -1.1953% |
| BTCUSDT | 15m | +0.0085% | 0.1 | 1.04 | -4.1126% | 37 | +0.2796% |
| ETHUSDT | 15m | -0.3018% | -2.5 | 0.34 | -8.7062% | 29 | -8.4481% |
| SOLUSDT | 15m | -0.2481% | -1.0 | 0.49 | -2.4152% | 11 | -2.7297% |

## Benchmarks

`benchmark mécanique` = toujours LONG à intervalle fixe (capte la dérive directionnelle du marché, PAS un repère « sans avantage »). `hasard (côté aléatoire)`, dans le tableau walk-forward ci-dessus, est le repère honnête : mêmes points d'entrée que la stratégie, côté tiré au hasard.

| intervalle | stratégie mean | benchmark mécanique (toujours LONG) |
|---|---:|---:|
| 5m | -0.0482% | -0.1805% |
| 15m | -0.0778% | -0.2078% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.0630% | 0.77 | -2.2566% |
| fees+100% | -0.1241% | 0.63 | -2.7998% |
| fees+25% | -0.0783% | 0.73 | -2.3488% |
| fees+50% | -0.0936% | 0.69 | -2.4940% |
| fees+50%_slip+100% | -0.1064% | 0.67 | -2.6413% |
| slip+100% | -0.0758% | 0.74 | -2.3539% |
| slip+50% | -0.0703% | 0.75 | -2.2972% |

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
- Exécution maker approximée (seuil de franchissement fixe, appliqué de façon symétrique entrée/sortie).
- Pas de funding.
- Pas de latence réseau réelle.
- Ambiguïté intrabougie TP/SL résolue par priorité au SL.
- Monte-Carlo basé sur les trades observés.
- Le FINAL HOLDOUT n'est pas utilisé pour la sélection.
- Seulement 3 folds de walk-forward par paire : les intervalles de confiance sur le mean/trade restent larges, à lire avec prudence (voir la colonne t ci-dessus).
- Le score de sélection ne pénalise pas explicitement l'incertitude d'échantillonnage (pas de terme de significativité) au-delà du nombre minimal de trades : un point élevé sur peu de trades peut encore être choisi alors qu'il est surtout du bruit.

## Interprétation

V4 ne considère pas une stratégie comme validée sur la seule base d'un fold positif. La confirmation doit survivre à plusieurs folds OOS, aux coûts et au FINAL HOLDOUT.
