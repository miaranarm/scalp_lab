# SCALP LAB V4.2 — rapport de recherche

## Configuration

- Binance Futures USD-M
- OHLCV uniquement
- TRAIN : 180 jours
- TEST : 45 jours
- STEP : 45 jours
- FINAL HOLDOUT : 90 jours
- Frais taker : 0.05%/côté
- Frais maker : 0.02%/côté

## Critères de robustesse

- folds actifs minimum : 5
- trades cumulés minimum : 50
- folds positifs minimum : 50%
- folds > hasard minimum : 50%
- PF médian minimum : 1.00
- edge médian vs hasard minimum : 0.0000%

Une configuration n'est dite ROBUSTE que si tous les critères sont satisfaits.

## Walk-forward OOS

### 1h

| mesure | valeur |
|---|---:|
| folds | 30 |
| test mean/trade | -0.1629% |
| folds positifs | 7/30 |
| PF médian | 0.81 |
| DD médian | -10.7700% |
| médiane trade | -1.0160% |
| hasard moyen | -0.0398% |
| edge moyen vs hasard | -0.1231% |
| folds > hasard | 10/30 |

## Configurations robustes

| actif | intervalle | signal | régime | profil | folds | trades | mean OOS | PF médian | edge médian | score |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| — | — | Aucune configuration ne satisfait les critères | — | — | — | — | — | — | — | — |

## Analyse globale multi-actifs

| intervalle | signal | régime | profil | actifs | actifs robustes | trades | PF médian | edge médian | global robuste |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 1h | vwap n=48 k=2.0 | all | maker_tp | 1 | 0 | 56 | 0.71 | -0.2532% | False |

## Final holdout

| actif | intervalle | signal | mean | t | PF | DD | n | return |
|---|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 1h | zscore n=30 thr=2.0 | -0.0334% | -0.2 | 0.90 | -4.9014% | 28 | -1.0118% |
| ETHUSDT | 1h | donchian n=50 vol=1.5 | -0.0292% | -0.1 | 0.96 | -18.4275% | 46 | -1.9597% |
| SOLUSDT | 1h | pullback rsi=40 | -0.3033% | -1.4 | 0.56 | -10.2817% | 28 | -8.3079% |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.1629% | 0.81 | -10.7700% |
| fees+100% | -0.2250% | 0.75 | -11.2064% |
| fees+25% | -0.1784% | 0.80 | -10.8793% |
| fees+50% | -0.1939% | 0.79 | -10.9885% |
| fees+50%_slip+100% | -0.2066% | 0.77 | -11.0523% |
| slip+100% | -0.1756% | 0.79 | -10.8340% |
| slip+50% | -0.1692% | 0.80 | -10.8020% |

## Limites

- OHLCV uniquement.
- Pas de carnet d'ordres.
- Pas de funding.
- Pas de latence réseau réelle.
- Ambiguïté intrabougie TP/SL : priorité SL.
- Exécution maker approximée.
- Monte-Carlo basé sur les trades observés.
- Le final holdout n'est pas utilisé pour le filtre de robustesse.
- Une configuration avec trop peu de trades est exclue.

## Règle d'interprétation

Une absence de configuration robuste constitue un résultat valide de la recherche. Les seuils ne doivent pas être abaissés après observation des résultats uniquement pour faire apparaître une configuration positive.
