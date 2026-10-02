# SCALP LAB V4.5.7 — MISSED TP FORENSICS

## Source

- V4.4 OOS trades : 2196
- Final holdout : exclu
- V4.4 non modifiée
- Aucun nouveau signal
- Aucune optimisation
- Aucun trading réel

## Exit integrity

- TP : 791
- SL : 1213
- TIME : 192
- EXIT CHECK : PASS

## TP reached

- TP atteint selon MFE : 808
- Taux : 36.79%
- TP réellement enregistré : 791

## Missed TP

- Missed TP : 17
- Taux : 0.77%

## Forensic classification

- Clean missed TP : 6
- TP + SL tous deux atteints : 11
- TP atteint + sortie SL : 11
- TP atteint + sortie TIME : 6

## CLEAN_MISSED_TP

MFE >= TP
ET MAE < SL
ET sortie != TP.

Le trade a donc atteint le TP selon son excursion
maximale sans atteindre le SL selon son excursion adverse.

## TP_SL_AMBIGUOUS

MFE >= TP
ET MAE >= SL.

Les deux niveaux ont été atteints à un moment du trade.
Avec OHLC/MFE/MAE, l'ordre intrabougie exact n'est pas reconstructible.

V4.1 conserve la priorité SL en cas d'ambiguïté intrabougie.

## Important

Cette analyse est strictement OOS.
Elle ne modifie ni les signaux ni les paramètres V4.1.

MFE/MAE sont des excursions de trade :
TP + SL atteints ne signifie pas nécessairement
qu'ils ont été touchés dans la même bougie.

## Files

- v457_global.csv
- v457_classification.csv
- v457_missed_tp_forensics.csv
- v457_all_tp_reached.csv
- v457_symbol_interval.csv
- v457_strategy.csv
