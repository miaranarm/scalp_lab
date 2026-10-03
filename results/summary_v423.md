# SCALP LAB V4.23 — TAKER-IMBALANCE HYPOTHESIS

- New hypothesis: extreme taker-buy imbalance predicts short-horizon reversal.
- Binance USD-M Futures klines; imbalance = 2*taker-buy-volume/volume - 1.
- No VWAP, Donchian, breakout, pullback, RSI or regime filter.
- Fixed grid: thresholds 0.20/0.30/0.40; horizons 3/6/12 bars.
- Six chronological 120d TRAIN / 30d TEST folds. FINAL = last 30d and confirmation-only.
- Round-trip cost estimates: BTC 0.12%, ETH 0.13%, SOL 0.16%.

## OOS

 symbol interval  fold  threshold  horizon    n       net
BTCUSDT       5m     0        0.4       12  496 -0.001249
BTCUSDT       5m     1        0.2        6 3213 -0.001139
BTCUSDT       5m     2        0.2        6 3804 -0.001149
BTCUSDT       5m     3        0.4       12 1055 -0.001221
BTCUSDT       5m     4        0.4       12  734 -0.001182
BTCUSDT       5m     5        0.3       12 2115 -0.001242
BTCUSDT      15m     0        0.4        6   20 -0.002885
BTCUSDT      15m     1        0.4        3   27 -0.000418
BTCUSDT      15m     2        0.4        3   62 -0.000691
BTCUSDT      15m     3        0.4        3   86 -0.001171
BTCUSDT      15m     4        0.4       12   47 -0.001459
BTCUSDT      15m     5        0.3        6  273 -0.000975
ETHUSDT       5m     0        0.4        6  262 -0.000829
ETHUSDT       5m     1        0.4        6  284 -0.001575
ETHUSDT       5m     2        0.4        6  555 -0.001255
ETHUSDT       5m     3        0.4        6  789 -0.001333
ETHUSDT       5m     4        0.2        6 3212 -0.001361
ETHUSDT       5m     5        0.3        3 1772 -0.001356
ETHUSDT      15m     0        0.4       12   11 -0.003866
ETHUSDT      15m     1        0.3       12   59 -0.001963
ETHUSDT      15m     2        0.4       12   32  0.000076
ETHUSDT      15m     3        0.4        6   47 -0.001743
ETHUSDT      15m     4        0.4        6   25 -0.000946
ETHUSDT      15m     5        0.4        6   29  0.000104
SOLUSDT       5m     0        0.4       12  355 -0.001135
SOLUSDT       5m     1        0.4       12  474 -0.001375
SOLUSDT       5m     2        0.4       12  938 -0.001383
SOLUSDT       5m     3        0.4       12 1123 -0.001444
SOLUSDT       5m     4        0.4       12  789 -0.001697
SOLUSDT       5m     5        0.4        6  953 -0.001440
SOLUSDT      15m     0        0.3        6  100  0.000751
SOLUSDT      15m     1        0.4       12   14 -0.002540
SOLUSDT      15m     2        0.4       12   54 -0.001387
SOLUSDT      15m     3        0.4        6   72 -0.003063
SOLUSDT      15m     4        0.3        6  230 -0.002012
SOLUSDT      15m     5        0.3        3  205 -0.001209

## FINAL

 symbol interval  threshold  horizon    n  final_mean  final_sum               final_start                 final_end
BTCUSDT       5m        0.2        6 4216   -0.001121  -4.727952 2026-08-31 23:55:00+00:00 2026-09-30 23:55:00+00:00
BTCUSDT      15m        0.4        3   89   -0.000996  -0.088603 2026-08-31 23:45:00+00:00 2026-09-30 23:45:00+00:00
ETHUSDT       5m        0.4        6  766   -0.001196  -0.916149 2026-08-31 23:55:00+00:00 2026-09-30 23:55:00+00:00
ETHUSDT      15m        0.4       12   60   -0.000366  -0.021961 2026-08-31 23:45:00+00:00 2026-09-30 23:45:00+00:00
SOLUSDT       5m        0.4        6  656   -0.001505  -0.987193 2026-08-31 23:55:00+00:00 2026-09-30 23:55:00+00:00
SOLUSDT      15m        0.3        6  142   -0.001861  -0.264288 2026-08-31 23:45:00+00:00 2026-09-30 23:45:00+00:00
