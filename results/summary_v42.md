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
- Monte-Carlo demandé : 0

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
| folds | 6 |
| test mean/trade | -0.2711% |
| folds positifs | 1/6 |
| PF médian | 0.60 |
| DD médian | -7.0529% |
| médiane trade | -0.9746% |
| hasard moyen | -0.0723% |
| edge moyen vs hasard | -0.1989% |
| folds > hasard | 2/6 |

## Configurations robustes

| actif | intervalle | signal | régime | profil | folds | trades | mean OOS | PF médian | edge médian | score |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| — | — | Aucune configuration ne satisfait les critères | — | — | — | — | — | — | — | — |

## Analyse globale multi-actifs

| intervalle | signal | régime | profil | actifs | actifs robustes | trades | PF médian | edge médian | global robuste |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 1h | donchian n=20 vol=1.5 | all | maker_both | 1 | 0 | 39 | 1.65 | +0.5548% | False |
| 1h | donchian n=20 vol=0.0 | trend | maker_both | 1 | 0 | 14 | 0.99 | +0.0505% | False |
| 1h | vwap n=96 k=2.0 | trend | maker_tp | 1 | 0 | 21 | 0.68 | -0.2257% | False |
| 1h | donchian n=20 vol=1.5 | all | maker_both | 1 | 0 | 40 | 0.53 | -0.3094% | False |
| 1h | donchian n=20 vol=0.0 | trend | maker_tp | 1 | 0 | 12 | 0.34 | -0.4672% | False |
| 1h | donchian n=50 vol=1.5 | all | maker_both | 1 | 0 | 21 | 0.27 | -0.7962% | False |

## Final holdout

| actif | intervalle | signal | mean | t | PF | DD | n | return |
|---|---|---|---:|---:|---:|---:|---:|---:|
| — | — | Aucun holdout exécuté : aucune configuration robuste | — | — | — | — | — | — |

## Robustesse des coûts

| scénario | mean/trade | PF médian | DD médian |
|---|---:|---:|---:|
| base | -0.2711% | 0.60 | -7.0529% |
| fees+100% | -0.3402% | 0.55 | -7.9326% |
| fees+25% | -0.2884% | 0.59 | -7.2742% |
| fees+50% | -0.3057% | 0.58 | -7.4945% |
| fees+50%_slip+100% | -0.3186% | 0.56 | -7.7132% |
| slip+100% | -0.2841% | 0.59 | -7.2734% |
| slip+50% | -0.2776% | 0.60 | -7.1633% |

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
- Un fold OOS avec n=0 n'est pas considéré comme actif.
- Le holdout final n'est exécuté que si une configuration passe tous les critères de robustesse.

## Règle d'interprétation

Une absence de configuration robuste constitue un résultat valide de la recherche. Les seuils ne doivent pas être abaissés après observation des résultats uniquement pour faire apparaître une configuration positive.
