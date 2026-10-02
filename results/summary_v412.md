# SCALP LAB V4.12 — ENTRY REPLAY

Trades OOS : 2196
Holdout : exclu

## Comparaison
    mode    n  mean_net  median_net      win       pf        dd  compound  TP  SL  TIME
ORIGINAL 1659 -0.001576   -0.003448 0.399638 0.591867 -0.930269 -0.930001 606 904   149
 B1_OPEN 1659 -0.001224   -0.003018 0.423749 0.668627 -0.876657 -0.874578 650 847   162
 B2_OPEN 1659 -0.001358   -0.003195 0.407474 0.640748 -0.901203 -0.899586 615 854   190

## Delta vs ORIGINAL
    mode  delta_mean  delta_win  delta_pf  delta_dd
ORIGINAL    0.000000   0.000000  0.000000  0.000000
 B1_OPEN    0.000352   0.024111  0.076760  0.053612
 B2_OPEN    0.000218   0.007836  0.048881  0.029066

## Méthode
- ORIGINAL = entrée/prix V4.4.
- B1_OPEN = ouverture de la bougie suivante.
- B2_OPEN = ouverture de la deuxième bougie suivante.
- ATR14 Wilder recalculé à l'entrée.
- TP = tp_mult × ATR.
- SL = sl_mult × ATR.
- Même hold que V4.4.
- SL prioritaire en cas d'ambiguïté intrabar.
- Frais et slippage inclus.
- Signaux V4.4 conservés.
- Aucun nouveau signal sélectionné.