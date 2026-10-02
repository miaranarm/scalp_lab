# SCALP LAB V4.8 — TRADE PATH FORENSICS

- Trades OOS : 2196
- FINAL HOLDOUT : exclu
- Source : V4.4 trade-level + Binance Futures OHLC
- Stratégie V4.4 : inchangée

## Touches

- TP 50% : 1254 (57.10%)
- TP 75% : 1009 (45.95%)
- TP 100% : 808 (36.79%)
- SL 50% : 1625 (74.00%)
- SL 75% : 1389 (63.25%)
- SL 100% : 1213 (55.24%)

## Ordre du chemin

- TP50 avant SL50 : 848
- TP75 avant SL50 : 664
- TP100 avant SL50 : 537
- SL50 avant TP50 : 1292

## Classes

path_class
EARLY_ADVERSE      1292
FAVORABLE_PATH      664
EARLY_FAVORABLE     184
AMBIGUOUS_PATH       55
NO_TOUCH              1

## Méthode

- Aucun signal ou paramètre modifié.
- Niveaux identiques à V4.4.
- Analyse OOS uniquement.
- Une même bougie peut toucher TP et SL.
- L'ordre intrabougie reste inconnu.