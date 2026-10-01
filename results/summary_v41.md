# SCALP LAB V4.1 — rapport de recherche

- Données : Binance USD-M
- TRAIN : 180 jours
- TEST : 45 jours
- STEP : 45 jours
- FINAL HOLDOUT : 45 jours
- Coût taker : 0.05%/côté
- Coût maker : 0.02%/côté
- Comparaison hasard : 100 tirages directionnels par fold

## Walk-forward OOS

### 5m

| mesure | valeur |
|---|---:|
| folds | 33 |
| test mean/trade | -0.0695% |
| folds positifs | 7/33 |
| PF médian | 0.65 |
| DD médian | -3.4713% |
| médiane trade | -0.2383% |
| mean/trade hasard (100 tirages) | -0.0821% |
| edge moyen vs hasard | +0.0125% |
| folds où stratégie > hasard | 18/33 |

### 15m

| mesure | valeur |
|---|---:|
| folds | 33 |
| test mean/trade | -0.1092% |
| folds positifs | 5/33 |
| PF médian | 0.71 |
| DD médian | -5.7723% |
| médiane trade | -0.3694% |
| mean/trade hasard (100 tirages) | -0.0876% |
| edge moyen vs hasard | -0.0215% |
| folds où stratégie > hasard | 13/33 |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | t | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 5m | +0.0016% | 0.0 | 1.01 | -0.7436% | 12 | +0.0142% |
| ETHUSDT | 5m | -0.1337% | -3.3 | 0.46 | -11.9317% | 91 | -11.5196% |
| SOLUSDT | 5m | -0.1080% | -0.7 | 0.63 | -2.1710% | 11 | -1.1953% |
| BTCUSDT | 15m | -0.1744% | -3.0 | 0.38 | -7.1264% | 41 | -6.9347% |
| ETHUSDT | 15m | -0.1864% | -2.4 | 0.51 | -11.8183% | 60 | -10.6847% |
| SOLUSDT | 15m | -0.3202% | -2.6 | 0.36 | -8.5380% | 29 | -8.9386% |

## Benchmarks

`benchmark mécanique` = toujours LONG à intervalle fixe (capte la dérive directionnelle du marché, PAS un repère « sans avantage »). `hasard (côté aléatoire)`, dans le tableau walk-forward ci-dessus, est le repère honnête : mêmes points d'entrée que la stratégie, côté tiré au hasard.

| intervalle | stratégie mean | benchmark mécanique (toujours LONG) |
|---|---:|---:|
| 5m | -0.0695% | -0.1954% |
| 15m | -0.1092% | -0.2103% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.0894% | 0.67 | -3.9921% |
| fees+100% | -0.1507% | 0.56 | -5.6515% |
| fees+25% | -0.1047% | 0.64 | -4.4019% |
| fees+50% | -0.1200% | 0.61 | -4.7623% |
| fees+50%_slip+100% | -0.1326% | 0.60 | -5.0552% |
| slip+100% | -0.1019% | 0.65 | -4.2745% |
| slip+50% | -0.0958% | 0.66 | -4.1159% |

## Distribution des stratégies sélectionnées

### signal

{'pullback rsi=35': 19, 'pullback rsi=40': 11, 'breakout n=20': 11, 'donchian n=50 vol=1.5': 10, 'donchian n=20 vol=0.0': 8, 'donchian n=20 vol=1.5': 4, 'vwap n=48 k=3.0': 3}

### regime

{'range': 33, 'trend': 19, 'all': 14}

### profile

{'maker_both': 61, 'maker_tp': 5}

## Limites

- OHLCV uniquement.
- Pas de carnet d'ordres.
- Exécution maker approximée (seuil de franchissement fixe, appliqué de façon symétrique entrée/sortie).
- Pas de funding.
- Pas de latence réseau réelle.
- Ambiguïté intrabougie TP/SL résolue par priorité au SL.
- Monte-Carlo basé sur les trades observés.
- Le FINAL HOLDOUT n'est pas utilisé pour la sélection.
- Le nombre de folds dépend de la profondeur historique demandée ; avec 730 jours, la fenêtre 180/45/45 produit généralement 11 folds par paire.
- Le score de sélection ne pénalise pas explicitement l'incertitude d'échantillonnage (pas de terme de significativité) au-delà du nombre minimal de trades : un point élevé sur peu de trades peut encore être choisi alors qu'il est surtout du bruit.

## Interprétation

V4.1 ne considère pas une stratégie comme validée sur la seule base d'un fold positif. La confirmation doit survivre à plusieurs folds OOS, battre de façon répétée le hasard directionnel aux mêmes points d'entrée, résister aux coûts et rester cohérente sur le FINAL HOLDOUT.
