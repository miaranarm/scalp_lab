import os
import pandas as pd
import numpy as np

IN = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.5 | TP UNIT AUDIT")

df = pd.read_csv(IN)
print("INPUT", len(df))

# ---------- REQUIRED ----------
req = [
    "symbol","interval","side","entry_price","exit_price",
    "tp_price","sl_price","tp_mult","sl_mult","hold",
    "mfe","mae","net","exit_reason"
]
missing = [c for c in req if c not in df.columns]
if missing:
    raise SystemExit("ERROR: missing=" + ",".join(missing))

# ---------- SIDE ----------
side = df["side"].astype(str).str.strip().str.upper()
df["side_name"] = side.replace({
    "1":"LONG","+1":"LONG",
    "-1":"SHORT",
    "LONG":"LONG","SHORT":"SHORT"
})

bad = ~df["side_name"].isin(["LONG","SHORT"])
if bad.any():
    print("SIDE VALUES", sorted(side.unique().tolist()))
    raise SystemExit(f"ERROR: invalid_side={bad.sum()}")

# ---------- NUMERIC ----------
num = [
    "entry_price","exit_price","tp_price","sl_price",
    "tp_mult","sl_mult","hold","mfe","mae","net"
]
for c in num:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if df[num].isna().any().any():
    raise SystemExit("ERROR: numeric values invalid")

# ---------- EXIT ----------
df["exit"] = (
    df["exit_reason"]
    .astype(str).str.strip().str.lower()
)

if not df["exit"].isin(["tp","sl","time"]).all():
    print("EXIT VALUES", sorted(df["exit"].unique().tolist()))
    raise SystemExit("ERROR: invalid exit_reason")

tp = int((df["exit"] == "tp").sum())
sl = int((df["exit"] == "sl").sum())
tm = int((df["exit"] == "time").sum())

print("TP", tp)
print("SL", sl)
print("TIME", tm)

if (tp, sl, tm) != (791,1213,192):
    raise SystemExit(
        f"ERROR: V44 CHECK FAIL TP={tp} SL={sl} TIME={tm}"
    )

print("V44 EXIT CHECK PASS")

# =========================================================
# RAW SAMPLE
# =========================================================
cols = [
    "symbol","interval","side_name",
    "entry_price","tp_price","sl_price",
    "tp_mult","sl_mult","mfe","mae",
    "exit","exit_price"
]

print()
print("===== RAW SAMPLE =====")
print(df[cols].head(12).to_string(index=False))

# =========================================================
# RECONSTRUCTION
# =========================================================

# Price-derived target percentage.
# LONG  : TP / Entry - 1
# SHORT : 1 - TP / Entry
df["tp_from_price"] = np.where(
    df["side_name"].eq("LONG"),
    df["tp_price"] / df["entry_price"] - 1,
    1 - df["tp_price"] / df["entry_price"]
)

# Same calculation in percent.
df["tp_from_price_pct"] = df["tp_from_price"] * 100

# MFE is assumed decimal in V4.4.
# Keep both decimal and percent representations.
df["mfe_decimal"] = df["mfe"]
df["mfe_pct"] = df["mfe"] * 100

# Ratios.
df["mfe_to_tp"] = np.where(
    df["tp_from_price"] > 0,
    df["mfe"] / df["tp_from_price"],
    np.nan
)

# Reached target using price-derived TP.
df["reached_tp"] = (
    df["mfe_decimal"] >= df["tp_from_price"]
)

df["missed_tp"] = (
    df["reached_tp"] &
    (df["exit"] != "tp")
)

# =========================================================
# DIAGNOSTIC
# =========================================================
print()
print("===== UNIT DIAGNOSTIC =====")

print(
    "TP_PRICE_MEAN",
    f"{df['tp_from_price'].mean():.6%}"
)

print(
    "TP_PRICE_MEDIAN",
    f"{df['tp_from_price'].median():.6%}"
)

print(
    "MFE_MEAN_DECIMAL",
    f"{df['mfe_decimal'].mean():.6f}"
)

print(
    "MFE_MEAN_PERCENT",
    f"{df['mfe_pct'].mean():.4f}%"
)

print(
    "MFE/TP_MEAN",
    f"{df['mfe_to_tp'].mean():.4f}"
)

for x in [.5,.75,.9,1.0]:
    reached = (df["mfe_to_tp"] >= x).mean()
    print(
        f"REACHED_{int(x*100)}",
        f"{reached:.2%}"
    )

print(
    "MISSED_TP",
    int(df["missed_tp"].sum())
)

print(
    "MISSED_TP_RATE",
    f"{df['missed_tp'].mean():.2%}"
)

# =========================================================
# COMPARE tp_mult
# =========================================================
print()
print("===== TP_MULT COMPARISON =====")

cmp = df[
    [
        "tp_mult",
        "tp_from_price",
        "tp_from_price_pct"
    ]
].describe()

print(cmp.to_string())

print()
print(
    "TP_MULT UNIQUE",
    sorted(df["tp_mult"].dropna().unique().tolist())
)

# =========================================================
# SAVE RAW AUDIT
# =========================================================
audit_cols = cols + [
    "tp_from_price",
    "tp_from_price_pct",
    "mfe_decimal",
    "mfe_pct",
    "mfe_to_tp",
    "reached_tp",
    "missed_tp"
]

df[audit_cols].to_csv(
    f"{OUT}/v455_tp_audit.csv",
    index=False
)

# =========================================================
# MISSED TP
# =========================================================
miss = df[df["missed_tp"]].copy()

miss.to_csv(
    f"{OUT}/v455_missed_tp.csv",
    index=False
)

if len(miss):
    summary = (
        miss.groupby(
            ["symbol","interval","side_name","exit"],
            dropna=False
        )
        .agg(
            n=("net","size"),
            mean_net=("net","mean"),
            mean_mfe=("mfe","mean"),
            mean_tp=("tp_from_price","mean")
        )
        .reset_index()
    )
else:
    summary = pd.DataFrame(
        columns=[
            "symbol","interval","side_name","exit",
            "n","mean_net","mean_mfe","mean_tp"
        ]
    )

summary.to_csv(
    f"{OUT}/v455_missed_tp_summary.csv",
    index=False
)

# =========================================================
# GLOBAL
# =========================================================
global_df = pd.DataFrame([{
    "trades":len(df),
    "tp":tp,
    "sl":sl,
    "time":tm,
    "tp_target_mean":df["tp_from_price"].mean(),
    "tp_target_median":df["tp_from_price"].median(),
    "mfe_mean":df["mfe"].mean(),
    "mfe_median":df["mfe"].median(),
    "mfe_to_tp_mean":df["mfe_to_tp"].mean(),
    "reached_50":(df["mfe_to_tp"]>=.50).mean(),
    "reached_75":(df["mfe_to_tp"]>=.75).mean(),
    "reached_90":(df["mfe_to_tp"]>=.90).mean(),
    "reached_100":(df["mfe_to_tp"]>=1.00).mean(),
    "missed_tp":int(df["missed_tp"].sum()),
    "missed_tp_rate":df["missed_tp"].mean()
}])

global_df.to_csv(
    f"{OUT}/v455_global.csv",
    index=False
)

# =========================================================
# SUMMARY
# =========================================================
g = global_df.iloc[0]

summary_text = f"""# SCALP LAB V4.5.5 — TP UNIT AUDIT

## Validation V4.4

- Input : {len(df)}
- TP : {tp}
- SL : {sl}
- TIME : {tm}
- EXIT CHECK : PASS
- OOS uniquement
- Final holdout exclu

## Reconstruction

Le TP est reconstruit uniquement avec :

- entry_price
- tp_price
- side

Formule LONG :

TP = tp_price / entry_price - 1

Formule SHORT :

TP = 1 - tp_price / entry_price

## Résultats

- TP cible moyen : {g["tp_target_mean"]:.4%}
- TP cible médian : {g["tp_target_median"]:.4%}
- MFE moyen : {g["mfe_mean"]:.4%}
- MFE médian : {g["mfe_median"]:.4%}
- ratio MFE/TP moyen : {g["mfe_to_tp_mean"]:.4f}

## Progression vers TP

- >= 50% : {g["reached_50"]:.2%}
- >= 75% : {g["reached_75"]:.2%}
- >= 90% : {g["reached_90"]:.2%}
- >= 100% : {g["reached_100"]:.2%}

## Missed TP

Définition :

MFE >= TP reconstruit
ET sortie finale != TP.

- Missed TP : {int(g["missed_tp"])}
- Taux : {g["missed_tp_rate"]:.2%}

## Contrôle d'unité

Les valeurs brutes sont conservées dans :

results/v455_tp_audit.csv

Aucune optimisation.
Aucun nouveau signal.
Aucun nouveau paramètre.
Aucun trading réel.
"""

with open(
    f"{OUT}/summary_v455.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(summary_text)

print()
print("V4.5.5 TERMINÉ")
print("AUDIT FILE results/v455_tp_audit.csv")
print("MISSED_TP", len(miss))
print("MISSED_TP_RATE", f"{len(miss)/len(df):.2%}")
