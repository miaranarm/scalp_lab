# SCALP LAB V4.22 — FINAL SURVIVORSHIP SYNTHESIS

## Scope
- V4.17 → V4.21 are synthesized only; no new tuning is performed.
- FINAL HOLDOUT remains confirmation-only.
- No parameter, signal, regime, exit or threshold is selected from FINAL.

## Sequential evidence

| Audit | Evidence | Result |
|---|---|---|
| V4.17 | B1_ALL mean | 0.0758% |
| V4.17 | GAP0 retained B1 mean | 0.1636% |
| V4.17 | Filtering improved the sample, but retained edge stayed negative | FAIL |
| V4.18 | 2,196 trades / aggregate net | -0.0450% |
| V4.19 | Donchian 50 vol1.5 mean | 5200.0000% |
| V4.19 | 95% CI upper bound for that signal | -0.0697% |
| V4.20 | strongest aggregate candidate | 1500.0000% |
| V4.20 | No candidate positive OOS globally | FAIL |
| V4.21 | FINAL holdout integrity | VALID |

## FINAL HOLDOUT

- Blocks: 6
- Trades represented: 244
- Positive blocks: 1/6
- Weighted mean/trade: -0.1679%
- BTCUSDT 5m: 12 trades, mean +0.0016%, return +0.01%
- ETHUSDT 5m: 91 trades, mean -0.1337%, return -11.52%
- SOLUSDT 5m: 11 trades, mean -0.1080%, return -1.20%
- BTCUSDT 15m: 41 trades, mean -0.1744%, return -6.93%
- ETHUSDT 15m: 60 trades, mean -0.1864%, return -10.68%
- SOLUSDT 15m: 29 trades, mean -0.3202%, return -8.94%

## Survival verdict

**NO SURVIVOR CONFIRMED.**

- V4.17 showed selection improvement without turning the retained sample positive.
- V4.18 showed the raw signal family remained net negative after costs.
- V4.19 found no signal with a clearly positive 95% confidence interval.
- V4.20 found no candidate with positive aggregate OOS net.
- V4.21 confirmed the selected OOS configurations do not generalize to the FINAL holdout.

## Methodological decision

**STOP PARAMETER TUNING FOR THIS SIGNAL FAMILY UNDER THE CURRENT MODEL.**

Further research should change the hypothesis rather than continue micro-optimizing the same VWAP / Donchian / breakout / pullback family. A new research branch should introduce a materially different source of edge, then restart with untouched OOS and FINAL holdout.

## STATUS

**VALID — SURVIVORSHIP SYNTHESIS COMPLETE. NO CONFIRMED EDGE.**
