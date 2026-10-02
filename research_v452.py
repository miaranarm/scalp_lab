import os
import pandas as pd
import numpy as np

IN = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.2 | TRADE FORENSICS")

df = pd.read_csv(IN)
print("INPUT", len(df))

required = [
    "symbol","interval","fold","signal","regime","profile",
    "tp_mult","sl_mult","hold","side","entry_price","exit_price",
    "gross","net","exit_reason","duration_bars","mfe","mae"
]

missing = [c for c in required if c not in df.columns]
if missing:
    raise SystemExit("ERROR: colonnes absentes: " + ",".join(missing))

# ---------- NORMALISATION ----------
df["side_name"] = df["side"].map({1:"LONG",-1:"SHORT"})
df["exit"] = df["exit_reason"].astype(str).str.lower().str.strip()

bad_side = df["side_name"].isna().sum()
bad_exit = (~df["exit"].isin(["tp","sl","time"])).sum()

if bad_side or bad_exit:
    raise SystemExit(
        f"ERROR: side_invalid={bad_side} exit_invalid={bad_exit}"
    )

# ---------- CHECK EXACT V4.4 ----------
counts = df["exit"].value_counts()

tp = int(counts.get("tp",0))
sl = int(counts.get("sl",0))
tm = int(counts.get("time",0))

print("TP",tp)
print("SL",sl)
print("TIME",tm)
print("TOTAL",tp+sl+tm)

if (tp,sl,tm) != (791,1213,192):
    raise SystemExit(
        f"ERROR: EXIT CHECK FAIL | TP={tp} SL={sl} TIME={tm}"
    )

print("V44 EXIT CHECK PASS")

# ---------- MISSED TP ----------
# MFE et TP_mult sont exprimés en décimal.
# Exemple TP 1.5% = 0.015.
df["tp_target"] = df["tp_mult"].abs()

df["reached_tp"] = df["mfe"] >= df["tp_target"]

df["missed_tp"] = (
    df["reached_tp"] &
    (df["exit"] != "tp")
)

# ---------- GLOBAL ----------
def stats(x):
    if len(x) == 0:
        return {
            "n":0,"mean_net":np.nan,"median_net":np.nan,
            "win_rate":np.nan,"mean_mfe":np.nan,
            "mean_mae":np.nan,"mean_duration":np.nan
        }

    return {
        "n":len(x),
        "mean_net":x["net"].mean(),
        "median_net":x["net"].median(),
        "win_rate":(x["net"] > 0).mean(),
        "mean_mfe":x["mfe"].mean(),
        "mean_mae":x["mae"].mean(),
        "mean_duration":x["duration_bars"].mean()
    }

global_s = stats(df)

pd.DataFrame([global_s]).to_csv(
    f"{OUT}/v452_global.csv",index=False
)

# ---------- MFE ----------
mfe = (
    df.groupby(["symbol","interval"])
      .agg(
          n=("mfe","size"),
          mean_mfe=("mfe","mean"),
          median_mfe=("mfe","median"),
          p25=("mfe",lambda x:x.quantile(.25)),
          p75=("mfe",lambda x:x.quantile(.75))
      )
      .reset_index()
)

mfe.to_csv(f"{OUT}/v452_mfe.csv",index=False)

# ---------- MAE ----------
mae = (
    df.groupby(["symbol","interval"])
      .agg(
          n=("mae","size"),
          mean_mae=("mae","mean"),
          median_mae=("mae","median"),
          p25=("mae",lambda x:x.quantile(.25)),
          p75=("mae",lambda x:x.quantile(.75))
      )
      .reset_index()
)

mae.to_csv(f"{OUT}/v452_mae.csv",index=False)

# ---------- MISSED TP DETAIL ----------
miss = df[df["missed_tp"]].copy()

miss.to_csv(
    f"{OUT}/v452_missed_tp.csv",
    index=False
)

# ---------- MISSED TP SUMMARY ----------
if len(miss):
    msum = (
        miss.groupby(
            ["symbol","interval","signal","regime","profile","tp_mult"]
        )
        .agg(
            missed_tp=("missed_tp","size"),
            mean_net=("net","mean"),
            mean_mfe=("mfe","mean"),
            mean_mae=("mae","mean"),
            mean_duration=("duration_bars","mean")
        )
        .reset_index()
    )
else:
    msum = pd.DataFrame()

msum.to_csv(
    f"{OUT}/v452_missed_tp_summary.csv",
    index=False
)

# ---------- DURATION ----------
duration = (
    df.groupby(["symbol","interval"])
      .agg(
          n=("duration_bars","size"),
          mean_bars=("duration_bars","mean"),
          median_bars=("duration_bars","median"),
          p25=("duration_bars",lambda x:x.quantile(.25)),
          p75=("duration_bars",lambda x:x.quantile(.75))
      )
      .reset_index()
)

duration.to_csv(f"{OUT}/v452_duration.csv",index=False)

# ---------- EXIT ----------
exit_tab = (
    df.groupby(["exit"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

exit_tab.to_csv(f"{OUT}/v452_exit.csv",index=False)

# ---------- SIDE ----------
side_tab = (
    df.groupby(["side_name"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

side_tab.to_csv(f"{OUT}/v452_side.csv",index=False)

# ---------- SIDE x EXIT ----------
side_exit = (
    df.groupby(["side_name","exit"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

side_exit.to_csv(
    f"{OUT}/v452_side_exit.csv",index=False
)

# ---------- SIGNAL x EXIT ----------
signal_exit = (
    df.groupby(["signal","exit"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

signal_exit.to_csv(
    f"{OUT}/v452_signal_exit.csv",index=False
)

# ---------- SIGNAL x SIDE ----------
signal_side = (
    df.groupby(["signal","side_name"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

signal_side.to_csv(
    f"{OUT}/v452_signal_side.csv",index=False
)

# ---------- SIGNAL x REGIME ----------
signal_regime = (
    df.groupby(["signal","regime"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

signal_regime.to_csv(
    f"{OUT}/v452_signal_regime.csv",index=False
)

# ---------- REGIME x EXIT ----------
regime_exit = (
    df.groupby(["regime","exit"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

regime_exit.to_csv(
    f"{OUT}/v452_regime_exit.csv",index=False
)

# ---------- SYMBOL / INTERVAL / EXIT ----------
sie = (
    df.groupby(["symbol","interval","exit"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

sie.to_csv(
    f"{OUT}/v452_symbol_interval_exit.csv",
    index=False
)

# ---------- TP PROFILE ----------
tp_profile = (
    df.groupby(["tp_mult","sl_mult","hold"])
      .apply(lambda x: pd.Series(stats(x)))
      .reset_index()
)

tp_profile.to_csv(
    f"{OUT}/v452_tp_profile.csv",
    index=False
)

# ---------- MISSED TP BY SIDE ----------
if len(miss):
    missed_side = (
        miss.groupby(["side_name"])
            .agg(
                n=("missed_tp","size"),
                mean_net=("net","mean"),
                mean_mfe=("mfe","mean"),
                mean_mae=("mae","mean")
            )
            .reset_index()
    )
else:
    missed_side = pd.DataFrame()

missed_side.to_csv(
    f"{OUT}/v452_missed_tp_side.csv",
    index=False
)

# ---------- SUMMARY ----------
miss_rate = len(miss) / len(df) if len(df) else 0

summary = f"""# SCALP LAB V4.5.2 — TRADE FORENSICS

## Input

- OOS trades : {len(df)}
- Final holdout : EXCLU
- TP : {tp}
- SL : {sl}
- TIME : {tm}

## Global

- mean net/trade : {global_s["mean_net"]:.4%}
- median net : {global_s["median_net"]:.4%}
- win rate : {global_s["win_rate"]:.2%}
- mean MFE : {global_s["mean_mfe"]:.4%}
- mean MAE : {global_s["mean_mae"]:.4%}
- mean duration : {global_s["mean_duration"]:.2f} bars

## Sorties

- TP : {tp}
- SL : {sl}
- TIME : {tm}

## Missed TP

Definition:

MFE >= TP target defined by the actual `tp_mult` of each trade,
while final exit != TP.

- missed TP : {len(miss)}
- missed TP rate : {miss_rate:.2%}

## TP profiles

Actual `tp_mult`, `sl_mult` and `hold` from V4.4 are preserved.

## Important

- Strictly OOS.
- Final holdout excluded.
- No new signal.
- No parameter optimisation.
- No live execution.
- Missed TP uses the actual TP target of each trade.
"""

with open(
    f"{OUT}/summary_v452.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(summary)

print()
print("V4.5.2 TERMINÉ")
print("V44 CHECK : PASS")
print("TRADES",len(df))
print("TP",tp)
print("SL",sl)
print("TIME",tm)
print("MISSED_TP",len(miss))
print("MISSED_TP_RATE",f"{miss_rate:.2%}")
