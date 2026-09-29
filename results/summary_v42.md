# SCALP LAB V4.2

- History : 365 jours
- TRAIN/TEST/STEP : 180/45/45 jours
- HOLDOUT : 90 jours
- MC : 0
- Robustesse : folds>=5, trades>=50, positifs>=50%, >random>=50%, PF>=1.0

## Résultat

- Configurations analysées : 6
- Configurations robustes : 0
- Holdouts exécutés : 0

## Limites

- OHLCV uniquement.
- Pas de funding, carnet d'ordres ou latence réelle.
- Priorité SL si TP et SL sont touchés dans la même bougie.
- Exécution maker approximée.
- Le holdout final n'intervient jamais dans le filtre de robustesse.
- Un fold avec n=0 n'est pas actif.
- Une absence de configuration robuste est un résultat valide.
