import os
import pandas as pd
import numpy as np

SRC = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.7 | MISSED TP FORENSICS")

df = pd.read_csv(SRC)
print("INPUT", len(df))

# NORMALISATION
s = df["side"].astype(str).str.strip().str.upper()
df["side_name"] = s.replace({
    "1": "LONG", "+1": "LONG", "-1": "SHORT",
    "LONG": "LONG", "SHORT": "SHORT"
})

df["exit"] = df["exit_reason"].astype(str).str.strip().str.lower()

for c in [
    "entry_price", "tp_price", "sl_price",
    "mfe", "mae", "tp_mult", "sl_mult", "duration_bars"
]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# TP / SL DISTANCES
df["tp_dist"] = np.where(
    df["side_name"].eq("LONG"),
    df["tp_price"] / df["entry_price"] - 1,
    1 - df["tp_price"] / df["entry_price"]
)

df["sl_dist"] = np.where(
    df["side_name"].eq("LONG"),
    1 - df["sl_price"] / df["entry_price"],
    df["sl_price"] / df["entry_price"] - 1
)

df["tp_reached"] = df["mfe"] >= df["tp_dist"]
df["sl_reached"] = df["mae"].abs() >= df["sl_dist"]

df["tp_exit"] = df["exit"].eq("tp")
df["sl_exit"] = df["exit"].eq("sl")
df["time_exit"] = df["exit"].eq("time")

# MISSED TP
df["missed_tp"] = df["tp_reached"] & ~df["tp_exit"]

df["clean_missed_tp"] = (
    df["tp_reached"] &
    ~df["sl_reached"] &
    ~df["tp_exit"]
)

df["tp_sl_both_reached"] = df["tp_reached"] & df["sl_reached"]
df["tp_then_sl_candidate"] = df["tp_reached"] & df["sl_exit"]
df["tp_then_time_candidate"] = df["tp_reached"] & df["time_exit"]

# EXIT VALIDATION
tp = int(df["tp_exit"].sum())
sl = int(df["sl_exit"].sum())
tm = int(df["time_exit"].sum())

if (tp, sl, tm) != (791, 1213, 192):
    raise SystemExit(
        f"EXIT CHECK FAILED: TP={tp} SL={sl} TIME={tm}"
    )

print("EXIT CHECK PASS")
print("TP", tp)
print("SL", sl)
print("TIME", tm)
print("TP REACHED", int(df["tp_reached"].sum()))
print("MISSED TP", int(df["missed_tp"].sum()))
print("CLEAN MISSED TP", int(df["clean_missed_tp"].sum()))
print("BOTH TP+SL", int(df["tp_sl_both_reached"].sum()))

# CLASSIFICATION
def classify(r):
    if not r["missed_tp"]:
        return "NOT_MISSED"

    if r["clean_missed_tp"]:
        return "CLEAN_MISSED_TP"

    if r["tp_sl_both_reached"] and r["sl_exit"]:
        return "TP_SL_AMBIGUOUS_SL_EXIT"

    if r["tp_sl_both_reached"] and r["time_exit"]:
        return "TP_SL_AMBIGUOUS_TIME_EXIT"

    if r["tp_sl_both_reached"]:
        return "TP_SL_BOTH_REACHED"

    if r["tp_then_time_candidate"]:
        return "TP_REACHED_TIME_EXIT"

    return "OTHER_MISSED_TP"

df["forensic_class"] = df.apply(classify, axis=1)

# IMPORTANT: AFTER forensic_class
missed = df[df["missed_tp"]].copy()

# DETAIL FILES
cols = [
    "symbol", "interval", "fold", "candidate",
    "signal", "regime", "profile",
    "tp_mult", "sl_mult", "side_name",
    "signal_time", "entry_time", "exit_time",
    "entry_price", "tp_price", "sl_price", "exit_price",
    "tp_dist", "sl_dist", "mfe", "mae",
    "duration_bars", "exit",
    "tp_reached", "sl_reached",
    "tp_sl_both_reached", "clean_missed_tp",
    "forensic_class"
]

cols = [c for c in cols if c in df.columns]

missed[cols].to_csv(
    f"{OUT}/v457_missed_tp_forensics.csv", index=False
)

df[df["tp_reached"]][cols].to_csv(
    f"{OUT}/v457_all_tp_reached.csv", index=False
)

# GLOBAL
pd.DataFrame([{
    "trades": len(df),
    "tp_exits": tp,
    "sl_exits": sl,
    "time_exits": tm,
    "tp_reached": int(df["tp_reached"].sum()),
    "missed_tp": int(df["missed_tp"].sum()),
    "clean_missed_tp": int(df["clean_missed_tp"].sum()),
    "tp_sl_both_reached": int(df["tp_sl_both_reached"].sum()),
    "tp_then_sl": int(df["tp_then_sl_candidate"].sum()),
    "tp_then_time": int(df["tp_then_time_candidate"].sum())
}]).to_csv(
    f"{OUT}/v457_global.csv", index=False
)

# CLASSIFICATION
(
    missed.groupby("forensic_class")
    .agg(
        trades=("symbol", "size"),
        mean_net=("net", "mean"),
        median_net=("net", "median"),
        mean_mfe=("mfe", "mean"),
        mean_mae=("mae", "mean")
    )
    .reset_index()
    .to_csv(f"{OUT}/v457_classification.csv", index=False)
)

# SYMBOL / INTERVAL
(
    missed.groupby(["symbol", "interval"])
    .agg(
        missed_tp=("symbol", "size"),
        clean_missed_tp=("clean_missed_tp", "sum"),
        both_reached=("tp_sl_both_reached", "sum"),
        mean_net=("net", "mean"),
        mean_mfe=("mfe", "mean"),
        mean_mae=("mae", "mean")
    )
    .reset_index()
    .to_csv(f"{OUT}/v457_symbol_interval.csv", index=False)
)

# STRATEGY
(
    missed.groupby(
        ["symbol", "interval", "signal", "regime", "profile"]
    )
    .agg(
        missed_tp=("symbol", "size"),
        clean_missed_tp=("clean_missed_tp", "sum"),
        both_reached=("tp_sl_both_reached", "sum"),
        mean_net=("net", "mean"),
        mean_mfe=("mfe", "mean"),
        mean_mae=("mae", "mean")
    )
    .reset_index()
    .to_csv(f"{OUT}/v457_strategy.csv", index=False)
)

# SUMMARY
def pct(x, n):
    return 100 * x / n if n else 0

reached = int(df["tp_reached"].sum())
clean = int(df["clean_missed_tp"].sum())
both = int(df["tp_sl_both_reached"].sum())

summary = f"""# SCALP LAB V4.5.7 — MISSED TP FORENSICS

## Source

- V4.4 OOS trades : {len(df)}
- Final holdout : exclu
- V4.4 non modifiée
- Aucun nouveau signal
- Aucune optimisation
- Aucun trading réel

## Exit integrity

- TP : {tp}
- SL : {sl}
- TIME : {tm}
- EXIT CHECK : PASS

## TP reached

- TP atteint selon MFE : {reached}
- Taux : {pct(reached, len(df)):.2f}%
- TP réellement enregistré : {tp}

## Missed TP

- Missed TP : {len(missed)}
- Taux : {pct(len(missed), len(df)):.2f}%

## Forensic classification

- Clean missed TP : {clean}
- TP + SL tous deux atteints : {both}
- TP atteint + sortie SL : {int(df["tp_then_sl_candidate"].sum())}
- TP atteint + sortie TIME : {int(df["tp_then_time_candidate"].sum())}

## CLEAN_MISSED_TP

MFE >= TP
ET MAE < SL
ET sortie != TP.

Le trade a donc atteint le TP selon son excursion
maximale sans atteindre le SL selon son excursion adverse.

## TP_SL_AMBIGUOUS

MFE >= TP
ET MAE >= SL.

Les deux niveaux ont été atteints à un moment du trade.
Avec OHLC/MFE/MAE, l'ordre intrabougie exact n'est pas reconstructible.

V4.1 conserve la priorité SL en cas d'ambiguïté intrabougie.

## Important

Cette analyse est strictement OOS.
Elle ne modifie ni les signaux ni les paramètres V4.1.

MFE/MAE sont des excursions de trade :
TP + SL atteints ne signifie pas nécessairement
qu'ils ont été touchés dans la même bougie.

## Files

- v457_global.csv
- v457_classification.csv
- v457_missed_tp_forensics.csv
- v457_all_tp_reached.csv
- v457_symbol_interval.csv
- v457_strategy.csv
"""

with open(f"{OUT}/summary_v457.md", "w", encoding="utf-8") as f:
    f.write(summary)

print("")
print("===== V4.5.7 RESULT =====")
print("TP REACHED", reached)
print("MISSED TP", len(missed))
print("CLEAN MISSED TP", clean)
print("TP+SL BOTH", both)
print("V4.5.7 TERMINÉ")
