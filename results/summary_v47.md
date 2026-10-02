# SCALP LAB V4.7 — EXIT FORENSICS

- Trades OOS : 2196
- FINAL HOLDOUT : exclu
- Source : V4.4 trade-level
- Stratégie V4.4 : inchangée
- Aucun nouveau paramètre testé

## Global

- mean net/trade : -0.0940%
- win rate : 40.53%
- mean MFE : +0.5030%
- mean MAE : -0.4736%
- MFE/TP : 0.735
- MAE/SL : 0.525
- capture net/MFE : -2697.17%
- durée : 9.05 bars

## Excursion

- MFE >= 50% TP : 1254 (57.10%)
- MFE >= 75% TP : 1009 (45.95%)
- MFE >= TP : 808 (36.79%)
- MAE >= 50% SL : 874 (39.80%)
- MAE >= 75% SL : 749 (34.11%)
- MAE >= SL : 665 (30.28%)

## Sorties

- TP : 791
- SL : 1213
- TIME : 192

## Méthode

- Analyse strictement OOS.
- Holdout final exclu.
- Aucun recalcul de signal.
- Aucun changement TP/SL/TIME.
- Les MFE/MAE sont des excursions OHLC.
- TP+SL sur une même bougie reste ambigu quant à l'ordre intrabougie.
