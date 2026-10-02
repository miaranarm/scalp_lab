# SCALP LAB V4.13 — B1 ENTRY FILTER

Trades OOS : 2196
Holdout : exclu

## Comparaison
    mode    n  mean_net  median_net      win       pf        dd  compound  TP  SL  TIME
ORIGINAL 1659 -0.001577   -0.003478 0.399638 0.591996 -0.930364 -0.930096 606 904   149
  B1_ALL 1659 -0.001220   -0.003036 0.424352 0.669998 -0.875719 -0.873624 651 847   161
B1_GAP25 1029 -0.001078   -0.003069 0.428571 0.712361 -0.680775 -0.679867 409 527    93
 B1_GAP0  655 -0.000838   -0.002828 0.435115 0.756965 -0.441191 -0.432042 265 327    63

## Delta vs ORIGINAL
    mode  delta_mean  delta_win  delta_pf  delta_dd
ORIGINAL    0.000000   0.000000  0.000000  0.000000
  B1_ALL    0.000357   0.024714  0.078001  0.054645
B1_GAP25    0.000499   0.028933  0.120364  0.249588
 B1_GAP0    0.000739   0.035476  0.164969  0.489173

## Méthode
- ORIGINAL = entrée V4.4.
- B1_ALL = ouverture de la bougie suivante.
- B1_GAP0 = B1 uniquement si l'ouverture n'est pas défavorable.
- B1_GAP25 = même filtre avec tolérance de -0.25 ATR.
- Le gap est calculé uniquement à l'ouverture de B1.
- Aucun renseignement de B1 après son ouverture n'est utilisé pour le filtre.
- ATR14 Wilder.
- TP/SL = multiples ATR V4.4.
- Même hold, frais et slippage que V4.4.
- SL prioritaire en ambiguïté intrabar.
- Aucun nouveau signal.
- Holdout non utilisé.