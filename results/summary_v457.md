# SCALP LAB V4.5.7

Input OOS : 2196
Holdout : exclu

EXIT : TP 791 | SL 1213 | TIME 192
EXIT CHECK : PASS

TP REACHED : 808 (36.79%)
MISSED TP : 17 (0.77%)
CLEAN MISSED TP : 6
TP+SL BOTH : 11

CLEAN = MFE >= TP, MAE < SL, sortie != TP.
BOTH = MFE >= TP et MAE >= SL.
OHLC/MFE/MAE ne permet pas de reconstruire
l'ordre intrabougie exact.
V4.1 conserve la priorité SL.

V4.4 inchangée.
Aucune optimisation.
Aucun trading réel.
