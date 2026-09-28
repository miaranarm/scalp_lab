# SCALP LAB V3.1 — recherche scalping Binance USD-M

Méthode: données Binance USD-M | signal clôturé → entrée suivante | 1h contexte | 5m/15m entrée
Coûts: taker=0.05% maker=0.02% par côté | WF=180j/45j/45j
Recherche: 4 exits × 3 profils | minimum TRAIN=80

BTCUSDT 5m | 104911 candles | 8742 h1 | 315 candidats | 4 folds
  Fold 1/4 → bb_rsi k=2.0 rsi<30 / trend / normal / maker_both | TEST -0.0813% | PF=0.61 | DD=-2.94% | n=29
  Fold 2/4 → bb_rsi k=2.0 rsi<30 / trend / normal / maker_both | TEST -0.0190% | PF=0.89 | DD=-4.06% | n=31
  Fold 3/4 → vwap n=48 k=3.0atr / trend_up / normal / maker_both | TEST -0.0987% | PF=0.46 | DD=-3.25% | n=31
  Fold 4/4 → vwap n=96 k=3.0atr / trend_up / high / maker_both | TEST -0.1942% | PF=0.21 | DD=-4.75% | n=25
  → terminé en 1.8 min
ETHUSDT 5m | 104910 candles | 8742 h1 | 315 candidats | 4 folds
  Fold 1/4 → donchian n=50 vol>1.5x / range / low / maker_both | TEST -0.1168% | PF=0.37 | DD=-4.53% | n=39
  Fold 2/4 → breakout20_atr_expansion / range / low / maker_both | TEST -0.0737% | PF=0.57 | DD=-3.53% | n=44
  Fold 3/4 → donchian n=50 vol>1.5x / range / normal / maker_both | TEST -0.0585% | PF=0.68 | DD=-2.77% | n=36
  Fold 4/4 → donchian n=50 vol>1.5x / range / normal / maker_both | TEST -0.1436% | PF=0.43 | DD=-7.12% | n=48
  → terminé en 1.7 min
SOLUSDT 5m | 104910 candles | 8742 h1 | 315 candidats | 4 folds
  Fold 1/4 → donchian n=20 vol>1.5x / strong_trend / low / maker_both | TEST -0.1330% | PF=0.55 | DD=-2.59% | n=17
  Fold 2/4 → zscore n=60 thr=2.5 / all / high / maker_both | TEST -0.1033% | PF=0.79 | DD=-11.11% | n=76
  Fold 3/4 → donchian n=50 vol>0.0x / strong_trend / normal / maker_both | TEST -0.1743% | PF=0.48 | DD=-6.63% | n=39
  Fold 4/4 → zscore n=60 thr=2.5 / range / normal / maker_both | TEST -0.1320% | PF=0.59 | DD=-6.61% | n=39
  → terminé en 1.7 min
BTCUSDT 15m | 34970 candles | 8742 h1 | 315 candidats | 4 folds
  Fold 1/4 → vwap n=96 k=2.0atr / trend / normal / maker_both | TEST +0.0982% | PF=1.45 | DD=-1.64% | n=19
  Fold 2/4 → vwap n=96 k=2.0atr / trend / normal / maker_both | TEST -0.0636% | PF=0.80 | DD=-3.61% | n=23
  Fold 3/4 → zscore n=30 thr=2.0 / trend / normal / maker_both | TEST -0.1073% | PF=0.66 | DD=-3.64% | n=25
  Fold 4/4 → zscore n=30 thr=2.0 / trend / normal / maker_both | TEST -0.0545% | PF=0.78 | DD=-2.27% | n=17
  → terminé en 1.0 min
ETHUSDT 15m | 34969 candles | 8742 h1 | 313 candidats | 4 folds
  Fold 1/4 → donchian n=20 vol>0.0x / range / low / maker_both | TEST +0.0047% | PF=1.03 | DD=-1.05% | n=24
  Fold 2/4 → donchian n=20 vol>1.5x / range / low / maker_both | TEST -0.0622% | PF=0.80 | DD=-2.73% | n=21
  Fold 3/4 → donchian n=20 vol>1.5x / range / low / maker_both | TEST -0.0631% | PF=0.76 | DD=-2.17% | n=21
  Fold 4/4 → donchian n=20 vol>0.0x / range / low / maker_both | TEST -0.0880% | PF=0.63 | DD=-3.66% | n=32
  → terminé en 1.0 min
SOLUSDT 15m | 34969 candles | 8742 h1 | 313 candidats | 4 folds
  Fold 1/4 → donchian n=50 vol>1.5x / all / high / maker_both | TEST +0.2357% | PF=1.58 | DD=-3.13% | n=36
  Fold 2/4 → ema20_50_cross / all / normal / maker_both | TEST +0.0370% | PF=1.08 | DD=-3.59% | n=22
  Fold 3/4 → ema20_50_cross / all / normal / maker_both | TEST -0.1851% | PF=0.59 | DD=-6.72% | n=25
  Fold 4/4 → ema20_50_cross / all / normal / maker_both | TEST -0.0397% | PF=0.91 | DD=-6.05% | n=30
  → terminé en 1.0 min

## Résultat global walk-forward

| intervalle | folds | test mean/trade | folds positifs | return médian | DD médian | PF médian |
|---|---:|---:|---:|---:|---:|---:|
| 15m | 12 | -0.0240% | 4/12 | -1.32% | -3.36% | 0.80 |
| 5m | 12 | -0.1107% | 0/12 | -3.84% | -4.29% | 0.56 |

## Résultat par symbole

| symbole | intervalle | folds | test moyen | positifs | return médian | DD médian |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 15m | 4 | -0.0318% | 1/4 | -1.22% | -2.94% |
| BTCUSDT | 5m | 4 | -0.0983% | 0/4 | -2.69% | -3.65% |
| ETHUSDT | 15m | 4 | -0.0522% | 1/4 | -1.34% | -2.45% |
| ETHUSDT | 5m | 4 | -0.0981% | 0/4 | -3.84% | -4.03% |
| SOLUSDT | 15m | 4 | +0.0120% | 2/4 | -0.30% | -4.82% |
| SOLUSDT | 5m | 4 | -0.1357% | 0/4 | -5.85% | -6.62% |

## Résultat par régime V3

| régime | folds | test moyen | positifs | PF médian | DD médian |
|---|---:|---:|---:|---:|---:|
| all | 5 | -0.0111% | 2/5 | 0.91 | -6.05% |
| range | 9 | -0.0815% | 1/9 | 0.63 | -3.53% |
| strong_trend | 2 | -0.1536% | 0/2 | 0.52 | -4.61% |
| trend | 6 | -0.0379% | 1/6 | 0.79 | -3.27% |
| trend_up | 2 | -0.1464% | 0/2 | 0.34 | -4.00% |

## Résultat par volatilité V3

| volatilité | folds | test moyen | positifs | PF médian | DD médian |
|---|---:|---:|---:|---:|---:|
| high | 3 | -0.0206% | 1/3 | 0.79 | -4.75% |
| low | 7 | -0.0760% | 1/7 | 0.63 | -2.73% |
| normal | 14 | -0.0730% | 2/14 | 0.67 | -3.62% |

## Robustesse des coûts

- **base** : mean/trade -0.0673% ; PF médian 0.67 ; DD médian -3.60%
- **fees+100%** : mean/trade -0.1260% ; PF médian 0.52 ; DD médian -4.90%
- **fees+25%** : mean/trade -0.0820% ; PF médian 0.62 ; DD médian -3.83%
- **fees+50%** : mean/trade -0.0966% ; PF médian 0.58 ; DD médian -4.17%
- **fees+50%_slip+100%** : mean/trade -0.1081% ; PF médian 0.56 ; DD médian -4.33%
- **slip+100%** : mean/trade -0.0788% ; PF médian 0.64 ; DD médian -3.73%
- **slip+50%** : mean/trade -0.0731% ; PF médian 0.66 ; DD médian -3.68%

## Distribution des choix V3

- régimes sélectionnés: {'range': 9, 'trend': 6, 'all': 5, 'trend_up': 2, 'strong_trend': 2}
- volatilités sélectionnées: {'normal': 14, 'low': 7, 'high': 3}

## Verdict V3
Le laboratoire ne trouve pas encore de preuve suffisante d'un avantage robuste hors échantillon. Les filtres de contexte V3 doivent être évalués sur leurs résultats TEST et non sur leur performance TRAIN.

Limites: bougies OHLCV, pas de carnet d'ordres, exécution limite approximée, pas de funding, pas de latence réseau, et Monte-Carlo basé sur les trades observés.