# SCALP LAB V4.24 — UTC HOUR SEASONALITY

- Independent hypothesis: crypto returns contain stable UTC-hour seasonality.
- Signal uses only the historical mean forward return for the entry candle's UTC hour.
- No VWAP, Donchian, imbalance, RSI, ATR, breakout, pullback or regime filter.
- Fixed horizons: 1/3/6 bars; fixed activation thresholds: 0/2/4/8 bps.
- Six chronological 120d TRAIN / 30d TEST folds. FINAL = last 30d and confirmation-only.
- Parameters are selected on aggregate OOS before FINAL; FINAL is never used for selection.

## OOS

 symbol interval       fold  threshold  horizon    n       net
BTCUSDT       5m 2026-01-29     0.0004        6  720 -0.000749
BTCUSDT       5m 2026-02-28     0.0004        6  720 -0.000988
BTCUSDT       5m 2026-03-30     0.0004        6 1080 -0.001414
BTCUSDT       5m 2026-04-29     0.0004        6 1440 -0.001339
BTCUSDT       5m 2026-05-29     0.0004        6  360 -0.000023
BTCUSDT       5m 2026-06-28     0.0004        6  360 -0.001813
BTCUSDT       5m 2026-07-28     0.0004        6  720 -0.001091
BTCUSDT      15m 2026-01-29     0.0008        6  360 -0.000592
BTCUSDT      15m 2026-02-28     0.0008        6  720 -0.000905
BTCUSDT      15m 2026-03-30     0.0008        6  360 -0.001553
BTCUSDT      15m 2026-04-29     0.0008        6  240 -0.001782
BTCUSDT      15m 2026-05-29     0.0008        6  360 -0.001032
BTCUSDT      15m 2026-06-28     0.0008        6  240 -0.000792
BTCUSDT      15m 2026-07-28     0.0008        6  360 -0.000157
ETHUSDT       5m 2026-01-29     0.0008        6  360 -0.001343
ETHUSDT       5m 2026-02-28     0.0004        6 2880 -0.001017
ETHUSDT       5m 2026-03-30     0.0008        6  360 -0.001504
ETHUSDT       5m 2026-04-29     0.0004        6 3600 -0.001279
ETHUSDT       5m 2026-05-29     0.0004        6 2880 -0.001308
ETHUSDT       5m 2026-06-28     0.0004        6  720 -0.001742
ETHUSDT       5m 2026-07-28     0.0004        6 1440 -0.000905
ETHUSDT      15m 2026-01-29     0.0008        6  840 -0.001323
ETHUSDT      15m 2026-02-28     0.0008        6 1080 -0.000629
ETHUSDT      15m 2026-03-30     0.0008        6  960 -0.001342
ETHUSDT      15m 2026-04-29     0.0008        6  960 -0.001289
ETHUSDT      15m 2026-05-29     0.0008        6 1080 -0.000231
ETHUSDT      15m 2026-06-28     0.0008        6  360 -0.002673
ETHUSDT      15m 2026-07-28     0.0008        6  480  0.000002
SOLUSDT       5m 2026-01-29     0.0008        6  360 -0.001321
SOLUSDT       5m 2026-02-28     0.0008        6  360 -0.001016
SOLUSDT       5m 2026-03-30     0.0008        6  360 -0.001802
SOLUSDT       5m 2026-04-29     0.0004        6 2520 -0.001533
SOLUSDT       5m 2026-05-29     0.0004        6 2880 -0.001909
SOLUSDT       5m 2026-06-28     0.0004        6 1080 -0.001442
SOLUSDT       5m 2026-07-28     0.0004        6 1440 -0.001307
SOLUSDT      15m 2026-01-29     0.0008        6 1080 -0.001607
SOLUSDT      15m 2026-02-28     0.0008        6 1440 -0.001094
SOLUSDT      15m 2026-03-30     0.0008        6 1080 -0.001997
SOLUSDT      15m 2026-04-29     0.0008        6  840 -0.001999
SOLUSDT      15m 2026-05-29     0.0008        6  840 -0.001108
SOLUSDT      15m 2026-06-28     0.0008        6  360 -0.001215
SOLUSDT      15m 2026-07-28     0.0008        6  480 -0.000678

## FINAL

 symbol interval  threshold  horizon   n  final_mean
BTCUSDT       5m     0.0004        6   0         NaN
BTCUSDT      15m     0.0008        6   0         NaN
ETHUSDT       5m     0.0004        6 360   -0.002281
ETHUSDT      15m     0.0008        6 120   -0.003252
SOLUSDT       5m     0.0008        6   0         NaN
SOLUSDT      15m     0.0008        6   0         NaN