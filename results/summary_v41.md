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
| test mean/trade | -0.2007% |
| folds positifs | 7/33 |
| PF médian | 0.77 |
| DD médian | -10.7369% |
| médiane trade | -0.9194% |
| mean/trade hasard (100 tirages) | -0.0921% |
| edge moyen vs hasard | -0.1086% |
| folds où stratégie > hasard | 12/33 |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | t | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 1h | -0.9594% | -3.6 | 0.00 | -3.1928% | 4 | -3.7869% |
| ETHUSDT | 1h | -0.4012% | -1.1 | 0.60 | -18.4275% | 24 | -9.5201% |
| SOLUSDT | 1h | -0.5340% | -2.8 | 0.06 | -2.8256% | 5 | -2.6454% |

## Benchmarks

`benchmark mécanique` = toujours LONG à intervalle fixe (capte la dérive directionnelle du marché, PAS un repère « sans avantage »). `hasard (côté aléatoire)`, dans le tableau walk-forward ci-dessus, est le repère honnête : mêmes points d'entrée que la stratégie, côté tiré au hasard.

| intervalle | stratégie mean | benchmark mécanique (toujours LONG) |
|---|---:|---:|
| 1h | -0.2007% | -0.2780% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.2007% | 0.77 | -10.7369% |
| fees+100% | -0.2644% | 0.68 | -11.2711% |
| fees+25% | -0.2166% | 0.75 | -10.8633% |
| fees+50% | -0.2325% | 0.73 | -10.9894% |
| fees+50%_slip+100% | -0.2452% | 0.71 | -11.1576% |
| slip+100% | -0.2133% | 0.75 | -10.9058% |
| slip+50% | -0.2070% | 0.76 | -10.8214% |

## Distribution des stratégies sélectionnées

### signal

{'vwap n=48 k=2.0': 6, 'donchian n=50 vol=1.5': 6, 'zscore n=30 thr=2.0': 5, 'donchian n=20 vol=1.5': 4, 'breakout n=20': 3, 'vwap n=48 k=3.0': 2, 'donchian n=20 vol=0.0': 2, 'pullback rsi=40': 2, 'vwap n=96 k=2.0': 2, 'zscore n=60 thr=2.5': 1}

### regime

{'all': 18, 'trend': 15}

### profile

{'maker_both': 29, 'maker_tp': 4}

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
