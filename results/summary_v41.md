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

### 1h

| mesure | valeur |
|---|---:|
| folds | 33 |
| test mean/trade | -0.1493% |
| folds positifs | 8/33 |
| PF médian | 0.85 |
| DD médian | -11.0086% |
| médiane trade | -0.9708% |
| mean/trade hasard (100 tirages) | -0.0436% |
| edge moyen vs hasard | -0.1057% |
| folds où stratégie > hasard | 12/33 |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | t | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 1h | -0.4532% | -1.6 | 0.17 | -3.7869% | 7 | -3.1456% |
| ETHUSDT | 1h | -0.3759% | -1.0 | 0.62 | -18.4275% | 24 | -8.9659% |
| SOLUSDT | 1h | -0.3928% | -1.0 | 0.54 | -4.8632% | 11 | -4.3239% |

## Benchmarks

`benchmark mécanique` = toujours LONG à intervalle fixe (capte la dérive directionnelle du marché, PAS un repère « sans avantage »). `hasard (côté aléatoire)`, dans le tableau walk-forward ci-dessus, est le repère honnête : mêmes points d'entrée que la stratégie, côté tiré au hasard.

| intervalle | stratégie mean | benchmark mécanique (toujours LONG) |
|---|---:|---:|
| 1h | -0.1493% | -0.2593% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.1493% | 0.85 | -11.0086% |
| fees+100% | -0.2111% | 0.77 | -11.4121% |
| fees+25% | -0.1648% | 0.84 | -11.1021% |
| fees+50% | -0.1802% | 0.82 | -11.1955% |
| fees+50%_slip+100% | -0.1928% | 0.81 | -11.2617% |
| slip+100% | -0.1619% | 0.84 | -11.0750% |
| slip+50% | -0.1556% | 0.84 | -11.0418% |

## Distribution des stratégies sélectionnées

### signal

{'donchian n=50 vol=1.5': 7, 'donchian n=20 vol=1.5': 5, 'vwap n=48 k=2.0': 5, 'zscore n=30 thr=2.0': 4, 'vwap n=48 k=3.0': 3, 'pullback rsi=40': 3, 'vwap n=96 k=2.0': 2, 'breakout n=20': 2, 'donchian n=20 vol=0.0': 1, 'zscore n=60 thr=2.5': 1}

### regime

{'all': 19, 'trend': 14}

### profile

{'maker_both': 31, 'maker_tp': 2}

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
