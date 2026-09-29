# SCALP LAB V4 (corrigé) — rapport de recherche

- Données : Binance USD-M
- TRAIN : 180 jours
- TEST : 45 jours
- STEP : 45 jours
- FINAL HOLDOUT : 45 jours
- Coût taker : 0.05%/côté
- Coût maker : 0.02%/côté

## Walk-forward OOS

### 1h

| mesure | valeur |
|---|---:|
| folds | 9 |
| test mean/trade | -0.1804% |
| folds positifs | 2/9 |
| PF médian | 0.77 |
| DD médian | -5.3011% |
| médiane trade | -0.8285% |
| mean/trade hasard (côté aléatoire) | -0.1950% |

## FINAL HOLDOUT

| symbole | intervalle | mean/trade | t | PF | DD | n | return |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 1h | +0.0739% | 0.3 | 1.30 | -0.8690% | 6 | +0.4314% |
| ETHUSDT | 1h | -0.3759% | -1.0 | 0.62 | -18.4275% | 24 | -8.9659% |
| SOLUSDT | 1h | +0.3198% | 0.9 | 1.38 | -5.6318% | 36 | +11.2518% |

## Benchmarks

`benchmark mécanique` = toujours LONG à intervalle fixe (capte la dérive directionnelle du marché, PAS un repère « sans avantage »). `hasard (côté aléatoire)`, dans le tableau walk-forward ci-dessus, est le repère honnête : mêmes points d'entrée que la stratégie, côté tiré au hasard.

| intervalle | stratégie mean | benchmark mécanique (toujours LONG) |
|---|---:|---:|
| 1h | -0.1804% | -0.2910% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.1804% | 0.77 | -5.3011% |
| fees+100% | -0.2439% | 0.72 | -6.4033% |
| fees+25% | -0.1963% | 0.76 | -5.5778% |
| fees+50% | -0.2121% | 0.75 | -5.8538% |
| fees+50%_slip+100% | -0.2250% | 0.73 | -5.9953% |
| slip+100% | -0.1933% | 0.75 | -5.4435% |
| slip+50% | -0.1868% | 0.76 | -5.3723% |

## Distribution des stratégies sélectionnées

### signal

{'donchian n=20 vol=1.5': 5, 'donchian n=50 vol=1.5': 2, 'donchian n=20 vol=0.0': 1, 'vwap n=96 k=2.0': 1}

### regime

{'all': 5, 'trend': 4}

### profile

{'maker_both': 8, 'maker_tp': 1}

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
