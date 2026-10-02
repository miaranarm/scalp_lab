import os
import pandas as pd
import numpy as np

IN = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.6 | V4.1 PRICE FORMULA AUDIT")

df = pd.read_csv(IN)
print("INPUT", len(df))

REQ = [
    "symbol","interval","side","entry_price","tp_price","sl_price",
    "tp_mult","sl_mult","mfe","mae","exit_reason"
]

missing = [c for c in REQ if c not in df.columns]
if missing:
    raise SystemExit("ERROR missing=" + ",".join(missing))

# ------------------------------------------------------------
# SIDE
# ------------------------------------------------------------
s = df["side"].astype(str).str.strip().str.upper()
df["side_name"] = s.replace({
    "1":"LONG","+1":"LONG","LONG":"LONG",
    "-1":"SHORT","SHORT":"SHORT"
})

bad = ~df["side_name"].isin(["LONG","SHORT"])
if bad.any():
    raise SystemExit(f"ERROR invalid_side={bad.sum()}")

# ------------------------------------------------------------
# NUMERIC
# ------------------------------------------------------------
NUM = [
    "entry_price","tp_price","sl_price",
    "tp_mult","sl_mult","mfe","mae"
]

for c in NUM:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if df[NUM].isna().any().any():
    raise SystemExit("ERROR invalid_numeric")

# ------------------------------------------------------------
# EXIT CHECK
# ------------------------------------------------------------
df["exit"] = (
    df["exit_reason"]
    .astype(str).str.strip().str.lower()
)

tp = int((df["exit"] == "tp").sum())
sl = int((df["exit"] == "sl").sum())
tm = int((df["exit"] == "time").sum())

print("TP", tp)
print("SL", sl)
print("TIME", tm)

if (tp, sl, tm) != (791, 1213, 192):
    raise SystemExit("ERROR V4.4 EXIT CHECK")

print("EXIT CHECK PASS")

# ------------------------------------------------------------
# IMPLIED ATR FROM TP
#
# V4.1:
# LONG  TP = entry + tp_mult * ATR
# SHORT TP = entry - tp_mult * ATR
# ------------------------------------------------------------
df["atr_from_tp"] = np.where(
    df["side_name"].eq("LONG"),
    (df["tp_price"] - df["entry_price"]) / df["tp_mult"],
    (df["entry_price"] - df["tp_price"]) / df["tp_mult"]
)

# ------------------------------------------------------------
# IMPLIED ATR FROM SL
#
# V4.1:
# LONG  SL = entry - sl_mult * ATR
# SHORT SL = entry + sl_mult * ATR
# ------------------------------------------------------------
df["atr_from_sl"] = np.where(
    df["side_name"].eq("LONG"),
    (df["entry_price"] - df["sl_price"]) / df["sl_mult"],
    (df["sl_price"] - df["entry_price"]) / df["sl_mult"]
)

# ------------------------------------------------------------
# TP/SL FORMULA RECONSTRUCTION
# ------------------------------------------------------------
df["tp_reconstructed"] = np.where(
    df["side_name"].eq("LONG"),
    df["entry_price"] + df["tp_mult"] * df["atr_from_tp"],
    df["entry_price"] - df["tp_mult"] * df["atr_from_tp"]
)

df["sl_reconstructed"] = np.where(
    df["side_name"].eq("LONG"),
    df["entry_price"] - df["sl_mult"] * df["atr_from_sl"],
    df["entry_price"] + df["sl_mult"] * df["atr_from_sl"]
)

df["tp_error"] = df["tp_reconstructed"] - df["tp_price"]
df["sl_error"] = df["sl_reconstructed"] - df["sl_price"]

# ------------------------------------------------------------
# TP / SL DISTANCES
# ------------------------------------------------------------
df["tp_pct"] = np.where(
    df["side_name"].eq("LONG"),
    df["tp_price"] / df["entry_price"] - 1,
    1 - df["tp_price"] / df["entry_price"]
)

df["sl_pct"] = np.where(
    df["side_name"].eq("LONG"),
    1 - df["sl_price"] / df["entry_price"],
    df["sl_price"] / df["entry_price"] - 1
)

# ------------------------------------------------------------
# FORMULA INTEGRITY
# ------------------------------------------------------------
TP_OK = np.isclose(
    df["tp_reconstructed"],
    df["tp_price"],
    rtol=1e-10,
    atol=1e-8
)

SL_OK = np.isclose(
    df["sl_reconstructed"],
    df["sl_price"],
    rtol=1e-10,
    atol=1e-8
)

# Direction checks
TP_DIR_OK = np.where(
    df["side_name"].eq("LONG"),
    df["tp_price"] > df["entry_price"],
    df["tp_price"] < df["entry_price"]
)

SL_DIR_OK = np.where(
    df["side_name"].eq("LONG"),
    df["sl_price"] < df["entry_price"],
    df["sl_price"] > df["entry_price"]
)

print()
print("===== FORMULA CHECK =====")
print("TP FORMULA OK", int(TP_OK.sum()), "/", len(df))
print("SL FORMULA OK", int(SL_OK.sum()), "/", len(df))
print("TP DIRECTION OK", int(np.sum(TP_DIR_OK)), "/", len(df))
print("SL DIRECTION OK", int(np.sum(SL_DIR_OK)), "/", len(df))

if not TP_OK.all():
    raise SystemExit("ERROR TP FORMULA MISMATCH")

if not SL_OK.all():
    raise SystemExit("ERROR SL FORMULA MISMATCH")

if not np.all(TP_DIR_OK):
    raise SystemExit("ERROR TP DIRECTION")

if not np.all(SL_DIR_OK):
    raise SystemExit("ERROR SL DIRECTION")

# ------------------------------------------------------------
# ATR CONSISTENCY
# ------------------------------------------------------------
atr_diff = (
    df["atr_from_tp"] - df["atr_from_sl"]
).abs()

print()
print("===== ATR CHECK =====")
print("ATR TP MEAN", f"{df['atr_from_tp'].mean():.8f}")
print("ATR SL MEAN", f"{df['atr_from_sl'].mean():.8f}")
print("ATR DIFF MAX", f"{atr_diff.max():.12f}")

# ------------------------------------------------------------
# MFE
# ------------------------------------------------------------
df["mfe_decimal"] = df["mfe"]

df["mfe_to_tp"] = (
    df["mfe_decimal"] / df["tp_pct"]
)

df["reached_tp"] = (
    df["mfe_to_tp"] >= 1.0
)

df["missed_tp"] = (
    df["reached_tp"] &
    (df["exit"] != "tp")
)

# ------------------------------------------------------------
# SAMPLE
# ------------------------------------------------------------
SHOW = [
    "symbol","interval","side_name",
    "entry_price","tp_price","sl_price",
    "tp_mult","sl_mult",
    "atr_from_tp","atr_from_sl",
    "tp_pct","sl_pct",
    "mfe","mfe_to_tp","exit"
]

print()
print("===== SAMPLE =====")
print(df[SHOW].head(12).to_string(index=False))

# ------------------------------------------------------------
# GLOBAL
# ------------------------------------------------------------
global_df = pd.DataFrame([{
    "trades":len(df),
    "tp":tp,
    "sl":sl,
    "time":tm,
    "tp_pct_mean":df["tp_pct"].mean(),
    "tp_pct_median":df["tp_pct"].median(),
    "sl_pct_mean":df["sl_pct"].mean(),
    "sl_pct_median":df["sl_pct"].median(),
    "atr_tp_mean":df["atr_from_tp"].mean(),
    "atr_sl_mean":df["atr_from_sl"].mean(),
    "atr_diff_max":atr_diff.max(),
    "mfe_mean":df["mfe"].mean(),
    "mfe_to_tp_mean":df["mfe_to_tp"].mean(),
    "reached_tp":int(df["reached_tp"].sum()),
    "reached_tp_rate":df["reached_tp"].mean(),
    "missed_tp":int(df["missed_tp"].sum()),
    "missed_tp_rate":df["missed_tp"].mean(),
    "tp_formula_ok":int(TP_OK.sum()),
    "sl_formula_ok":int(SL_OK.sum())
}])

global_df.to_csv(
    f"{OUT}/v456_global.csv",
    index=False
)

# ------------------------------------------------------------
# BY TP MULT
# ------------------------------------------------------------
by_tp = (
    df.groupby("tp_mult")
    .agg(
        trades=("tp_mult","size"),
        tp_pct_mean=("tp_pct","mean"),
        tp_pct_median=("tp_pct","median"),
        atr_mean=("atr_from_tp","mean"),
        mfe_mean=("mfe","mean"),
        reached_tp=("reached_tp","sum")
    )
    .reset_index()
)

by_tp.to_csv(
    f"{OUT}/v456_by_tp_mult.csv",
    index=False
)

# ------------------------------------------------------------
# BY SL MULT
# ------------------------------------------------------------
by_sl = (
    df.groupby("sl_mult")
    .agg(
        trades=("sl_mult","size"),
        sl_pct_mean=("sl_pct","mean"),
        sl_pct_median=("sl_pct","median"),
        atr_mean=("atr_from_sl","mean")
    )
    .reset_index()
)

by_sl.to_csv(
    f"{OUT}/v456_by_sl_mult.csv",
    index=False
)

# ------------------------------------------------------------
# MISSED TP
# ------------------------------------------------------------
miss = df[df["missed_tp"]].copy()

miss.to_csv(
    f"{OUT}/v456_missed_tp.csv",
    index=False
)

# ------------------------------------------------------------
# AUDIT COMPLET
# ------------------------------------------------------------
df[SHOW + [
    "tp_reconstructed",
    "sl_reconstructed",
    "tp_error",
    "sl_error",
    "reached_tp",
    "missed_tp"
]].to_csv(
    f"{OUT}/v456_formula_audit.csv",
    index=False
)

# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------
g = global_df.iloc[0]

text = f"""# SCALP LAB V4.5.6 — V4.1 PRICE FORMULA AUDIT

## Source

- V4.4 OOS trades : {len(df)}
- Final holdout : exclu
- Aucun nouveau signal
- Aucune optimisation
- Aucun trading réel

## Exit integrity

- TP : {tp}
- SL : {sl}
- TIME : {tm}
- EXIT CHECK : PASS

## V4.1 formula

TP :

- LONG = entry + tp_mult × ATR
- SHORT = entry - tp_mult × ATR

SL :

- LONG = entry - sl_mult × ATR
- SHORT = entry + sl_mult × ATR

## Formula validation

- TP formula : {int(TP_OK.sum())}/{len(df)}
- SL formula : {int(SL_OK.sum())}/{len(df)}
- TP direction : {int(np.sum(TP_DIR_OK))}/{len(df)}
- SL direction : {int(np.sum(SL_DIR_OK))}/{len(df)}

## TP

- TP moyen : {g["tp_pct_mean"]:.4%}
- TP médian : {g["tp_pct_median"]:.4%}

Important : tp_mult = multiple d'ATR, PAS un pourcentage direct.

## SL

- SL moyen : {g["sl_pct_mean"]:.4%}
- SL médian : {g["sl_pct_median"]:.4%}

## ATR

- ATR depuis TP : {g["atr_tp_mean"]:.8f}
- ATR depuis SL : {g["atr_sl_mean"]:.8f}
- différence maximale : {g["atr_diff_max"]:.12f}

## MFE

- MFE moyen : {g["mfe_mean"]:.4%}
- ratio MFE/TP moyen : {g["mfe_to_tp_mean"]:.4f}
- trades ayant atteint le TP : {int(g["reached_tp"])}
- taux atteint : {g["reached_tp_rate"]:.2%}

## Missed TP

- Missed TP : {int(g["missed_tp"])}
- Taux : {g["missed_tp_rate"]:.2%}

## Conclusion technique

Le TP et le SL doivent être interprétés comme des multiples de l'ATR.
Une valeur tp_mult = 3.0 ne signifie donc pas +3%.

La vérification V4.5.6 contrôle directement les prix V4.4
contre cette formule V4.1.

Les données V4.4 ne sont pas modifiées.
"""

with open(
    f"{OUT}/summary_v456.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(text)

print()
print("===== RESULT =====")
print("TP FORMULA PASS")
print("SL FORMULA PASS")
print("MISSED_TP", int(g["missed_tp"]))
print("V4.5.6 TERMINÉ")
