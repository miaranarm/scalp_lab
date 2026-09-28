# SCALP LAB V2 — recherche scalping Binance USD-M

## Méthode
- données réelles Binance USD-M, bougies publiques
- coûts: taker 0.05% / maker 0.02% par côté
- slippage spécifique par symbole + stress-test
- signal sur bougie clôturée, entrée sur bougie suivante
- 1h = régime, 5m/15m = setup et entrée
- walk-forward: 180j train / 45j test / pas de 45j
- position fixe, aucune martingale, une position à la fois

## BTCUSDT 5m
Téléchargement BTCUSDT 5m...
Téléchargement BTCUSDT 1h...
- 104921 bougies 5m, 8743 bougies 1h, 4 folds
  fold 1: trend_pullback rsi<35 / trend / maker_both → TEST +0.0032% PF=1.02 DD=-1.82% n=21
  fold 2: trend_pullback rsi<35 / trend / maker_both → TEST -0.0690% PF=0.73 DD=-1.81% n=25
  fold 3: trend_pullback rsi<35 / trend / maker_both → TEST -0.0643% PF=0.63 DD=-2.05% n=26
  fold 4: trend_pullback rsi<35 / trend / maker_both → TEST -0.0801% PF=0.51 DD=-2.57% n=28
## ETHUSDT 5m
Téléchargement ETHUSDT 5m...
Téléchargement ETHUSDT 1h...
- 104921 bougies 5m, 8743 bougies 1h, 4 folds
  fold 1: donchian n=50 vol>1.5x / range / maker_both → TEST -0.0942% PF=0.50 DD=-10.02% n=106
  fold 2: breakout20_atr_expansion / range / maker_both → TEST -0.0835% PF=0.55 DD=-8.29% n=83
  fold 3: trend_pullback rsi<40 / range / maker_both → TEST -0.1127% PF=0.48 DD=-3.01% n=27
  fold 4: trend_pullback rsi<40 / trend_up / maker_both → TEST +0.0730% PF=1.43 DD=-1.92% n=48
## SOLUSDT 5m
Téléchargement SOLUSDT 5m...
Téléchargement SOLUSDT 1h...
- 104921 bougies 5m, 8743 bougies 1h, 4 folds
  fold 1: ema20_50_cross / trend / maker_both → TEST -0.1058% PF=0.62 DD=-10.75% n=96
  fold 2: ema20_50_cross / trend_up / maker_both → TEST +0.0495% PF=1.24 DD=-1.66% n=18
  fold 3: ema20_50_cross / trend_up / maker_both → TEST -0.0297% PF=0.88 DD=-4.10% n=49
  fold 4: ema20_50_cross / trend_up / maker_both → TEST -0.1319% PF=0.56 DD=-10.56% n=71
## BTCUSDT 15m
Téléchargement BTCUSDT 15m...
Téléchargement BTCUSDT 1h...
- 34973 bougies 15m, 8743 bougies 1h, 4 folds
  fold 1: ema20_50_cross / range / maker_both → TEST +0.0941% PF=1.53 DD=-0.94% n=18
  fold 2: trend_pullback rsi<40 / trend_up / maker_both → TEST -0.3206% PF=0.21 DD=-3.17% n=10
  fold 3: trend_pullback rsi<40 / all / maker_both → TEST -0.1280% PF=0.54 DD=-6.89% n=35
  fold 4: trend_pullback rsi<40 / all / maker_both → TEST -0.2302% PF=0.36 DD=-8.20% n=35
## ETHUSDT 15m
Téléchargement ETHUSDT 15m...
Téléchargement ETHUSDT 1h...
- 34973 bougies 15m, 8743 bougies 1h, 4 folds
  fold 1: breakout20_atr_expansion / range / maker_tp → TEST +0.0213% PF=1.06 DD=-4.76% n=34
  fold 2: breakout20_atr_expansion / range / maker_tp → TEST -0.0614% PF=0.84 DD=-4.51% n=22
  fold 3: donchian n=50 vol>0.0x / range / maker_both → TEST +0.0340% PF=1.13 DD=-3.21% n=36
  fold 4: donchian n=50 vol>0.0x / range / maker_both → TEST -0.1229% PF=0.67 DD=-6.73% n=52
## SOLUSDT 15m
Téléchargement SOLUSDT 15m...
Téléchargement SOLUSDT 1h...
- 34973 bougies 15m, 8743 bougies 1h, 4 folds
  fold 1: breakout20_atr_expansion / all / maker_both → TEST +0.0222% PF=1.05 DD=-13.98% n=122
  fold 2: breakout20_atr_expansion / range / maker_both → TEST -0.1422% PF=0.56 DD=-3.27% n=17
  fold 3: breakout20_atr_expansion / range / maker_both → TEST -0.0268% PF=0.91 DD=-6.60% n=44
  fold 4: donchian n=50 vol>0.0x / range / maker_both → TEST -0.1949% PF=0.49 DD=-8.36% n=44

## Résultat global walk-forward

| intervalle | folds | test mean/trade | folds positifs | return médian | DD médian | PF médian |
|---|---:|---:|---:|---:|---:|---:|
| 15m | 12 | -0.0880% | 4/12 | -1.91% | -5.68% | 0.76 |
| 5m | 12 | -0.0538% | 3/12 | -1.99% | -2.79% | 0.62 |

## Résultat par symbole
| symbole | intervalle | folds | test moyen | positifs | return médian | DD médian |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 15m | 4 | -0.1462% | 1/4 | -3.79% | -5.03% |
| BTCUSDT | 5m | 4 | -0.0526% | 1/4 | -1.71% | -1.93% |
| ETHUSDT | 15m | 4 | -0.0323% | 2/4 | -0.40% | -4.64% |
| ETHUSDT | 5m | 4 | -0.0544% | 1/4 | -4.87% | -5.65% |
| SOLUSDT | 15m | 4 | -0.0854% | 1/4 | -1.83% | -7.48% |
| SOLUSDT | 5m | 4 | -0.0545% | 1/4 | -5.27% | -7.33% |

## Robustesse des coûts
- **base** : mean/trade -0.0727% ; PF médian 0.68 ; DD médian -4.31%
- **fees+100%** : mean/trade -0.1343% ; PF médian 0.52 ; DD médian -6.15%
- **fees+25%** : mean/trade -0.0881% ; PF médian 0.64 ; DD médian -4.77%
- **fees+50%** : mean/trade -0.1035% ; PF médian 0.60 ; DD médian -5.24%
- **fees+50%_slip+100%** : mean/trade -0.1155% ; PF médian 0.59 ; DD médian -5.66%
- **slip+100%** : mean/trade -0.0847% ; PF médian 0.66 ; DD médian -4.74%
- **slip+50%** : mean/trade -0.0786% ; PF médian 0.67 ; DD médian -4.52%

## Verdict V2
Le laboratoire ne trouve pas encore de preuve suffisante d'un avantage robuste hors échantillon sur les folds testés. Il faut améliorer les hypothèses/signaux ou étendre l'échantillon avant de construire le bot réel.

Limites: bougies OHLCV, pas de carnet d'ordres, exécution limite approximée, pas de funding, pas de latence réseau, et Monte-Carlo basé sur les trades observés.