# SCALP LAB V4.25 — VOLATILITY-NORMALIZED EXTREME

Independent hypothesis: price extremes normalized by recent true range mean revert.

Fixed z thresholds: 1/1.5/2 ATR; horizons 1/3/6 bars. Six chronological 120d TRAIN / 30d TEST folds. FINAL last 30d, confirmation only.

## OOS

 symbol interval       fold   z  horizon    n       net
BTCUSDT       5m 2026-01-29 1.0        3 4506 -0.002052
BTCUSDT       5m 2026-02-28 1.0        6 4473 -0.001750
BTCUSDT       5m 2026-03-30 1.0        6 4612 -0.001681
BTCUSDT       5m 2026-04-29 1.0        6 4697 -0.001572
BTCUSDT       5m 2026-05-29 1.0        6 4742 -0.001813
BTCUSDT       5m 2026-06-28 1.0        6 4773 -0.001628
BTCUSDT       5m 2026-07-28 1.0        6 4972 -0.001679
BTCUSDT      15m 2026-01-29 1.0        1 1461 -0.002818
BTCUSDT      15m 2026-02-28 1.0        1 1369 -0.002441
BTCUSDT      15m 2026-03-30 1.0        1 1365 -0.002148
BTCUSDT      15m 2026-04-29 1.0        6 1406 -0.001863
BTCUSDT      15m 2026-05-29 1.0        6 1503 -0.001714
BTCUSDT      15m 2026-06-28 1.0        6 1481 -0.001599
BTCUSDT      15m 2026-07-28 1.0        6 1587 -0.002331
ETHUSDT       5m 2026-01-29 1.0        1 4332 -0.002539
ETHUSDT       5m 2026-02-28 1.0        3 4188 -0.002224
ETHUSDT       5m 2026-03-30 1.0        3 4188 -0.001975
ETHUSDT       5m 2026-04-29 1.0        6 4447 -0.001876
ETHUSDT       5m 2026-05-29 1.0        6 4333 -0.002169
ETHUSDT       5m 2026-06-28 1.0        1 4275 -0.001930
ETHUSDT       5m 2026-07-28 1.0        1 4360 -0.001886
ETHUSDT      15m 2026-01-29 1.0        1 1440 -0.003449
ETHUSDT      15m 2026-02-28 1.0        1 1307 -0.002826
ETHUSDT      15m 2026-03-30 1.0        3 1314 -0.002757
ETHUSDT      15m 2026-04-29 1.0        6 1297 -0.002310
ETHUSDT      15m 2026-05-29 1.0        1 1382 -0.002785
ETHUSDT      15m 2026-06-28 1.0        6 1271 -0.002179
ETHUSDT      15m 2026-07-28 1.0        6 1425 -0.002723
SOLUSDT       5m 2026-01-29 1.0        1 4581 -0.002828
SOLUSDT       5m 2026-02-28 1.0        6 4230 -0.002479
SOLUSDT       5m 2026-03-30 1.0        3 4250 -0.002264
SOLUSDT       5m 2026-04-29 1.0        6 4476 -0.002251
SOLUSDT       5m 2026-05-29 1.0        6 4652 -0.002594
SOLUSDT       5m 2026-06-28 1.0        6 4333 -0.002136
SOLUSDT       5m 2026-07-28 1.0        6 4503 -0.002308
SOLUSDT      15m 2026-01-29 1.0        1 1483 -0.003951
SOLUSDT      15m 2026-02-28 1.0        1 1426 -0.003172
SOLUSDT      15m 2026-03-30 1.0        1 1389 -0.002953
SOLUSDT      15m 2026-04-29 1.0        1 1359 -0.002795
SOLUSDT      15m 2026-05-29 1.0        1 1501 -0.003276
SOLUSDT      15m 2026-06-28 1.0        6 1356 -0.001995
SOLUSDT      15m 2026-07-28 1.0        6 1477 -0.002958

## FINAL

 symbol interval   z  horizon    n  final_mean
BTCUSDT       5m 1.0        6 4657   -0.001555
BTCUSDT      15m 1.0        6 1423   -0.001876
ETHUSDT       5m 1.0        6 4329   -0.001766
ETHUSDT      15m 1.0        6 1407   -0.002519
SOLUSDT       5m 1.0        3 4263   -0.002253
SOLUSDT      15m 1.0        6 1384   -0.002697