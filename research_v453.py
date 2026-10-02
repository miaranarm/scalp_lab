import os
import pandas as pd
import numpy as np

IN = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.3 | TRADE FORENSICS FINAL")

df = pd.read_csv(IN)
print("INPUT", len(df))
print("COLUMNS", ",".join(df.columns))

req = [
    "symbol","interval","fold","signal","regime","profile",
    "tp_mult","sl_mult","hold","side","entry_price","exit_price",
    "gross","net","exit_reason","duration_bars","mfe","mae"
]

missing = [c for c in req if c not in df.columns]
if missing:
    raise SystemExit("ERROR: colonnes absentes: " + ",".join(missing))

# ---------- SIDE ----------
s = df["side"].astype(str).str.strip().str.upper()

df["side_name"] = s.replace({
    "1": "LONG",
    "+1": "LONG",
    "-1": "SHORT",
    "LONG": "LONG",
    "SHORT": "SHORT",
})

# ---------- EXIT ----------
df["exit"] = (
    df["exit_reason"]
    .astype(str)
    .str.strip()
    .str.lower()
)

bad_side = (~df["side_name"].isin(["LONG","SHORT"])).sum()
bad_exit = (~df["exit"].isin(["tp","sl","time"])).sum()

if bad_side or bad_exit:
    print("SIDE VALUES", sorted(s.unique().tolist()))
    print("EXIT VALUES", sorted(df["exit"].unique().tolist()))
    raise SystemExit(
        f"ERROR: side_invalid={bad_side} exit_invalid={bad_exit}"
    )

# ---------- EXACT V4.4 CHECK ----------
cnt = df["exit"].value_counts()

tp = int(cnt.get("tp", 0))
sl = int(cnt.get("sl", 0))
tm = int(cnt.get("time", 0))

print("TP", tp)
print("SL", sl)
print("TIME", tm)
print("TOTAL", tp + sl + tm)

if (tp, sl, tm) != (791, 1213, 192):
    raise SystemExit(
        f"ERROR: EXIT CHECK FAIL | TP={tp} SL={sl} TIME={tm}"
    )

print("V44 EXIT CHECK PASS")

# ---------- NUMERIC ----------
for c in [
    "tp_mult","sl_mult","hold",
    "entry_price","exit_price","gross","net",
    "duration_bars","mfe","mae"
]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if df[["tp_mult","sl_mult","mfe","mae"]].isna().any().any():
    raise SystemExit("ERROR: valeurs numériques invalides")

# ---------- STATS ----------
def stats(x):
    if len(x) == 0:
        return dict(
            n=0,
            mean_net=np.nan,
            median_net=np.nan,
            win_rate=np.nan,
            mean_mfe=np.nan,
            mean_mae=np.nan,
            mean_duration=np.nan
        )

    return dict(
        n=len(x),
        mean_net=x["net"].mean(),
        median_net=x["net"].median(),
        win_rate=(x["net"] > 0).mean(),
        mean_mfe=x["mfe"].mean(),
        mean_mae=x["mae"].mean(),
        mean_duration=x["duration_bars"].mean()
    )

# ---------- GLOBAL ----------
g = pd.DataFrame([stats(df)])
g.to_csv(f"{OUT}/v453_global.csv", index=False)

# ---------- EXIT ----------
def grouped(cols, name):
    z = (
        df.groupby(cols, dropna=False)
          .apply(lambda x: pd.Series(stats(x)),
                 include_groups=False)
          .reset_index()
    )
    z.to_csv(f"{OUT}/{name}.csv", index=False)
    return z

grouped(["exit"], "v453_exit")
grouped(["side_name"], "v453_side")
grouped(["side_name","exit"], "v453_side_exit")
grouped(["signal","exit"], "v453_signal_exit")
grouped(["signal","side_name"], "v453_signal_side")
grouped(["signal","regime"], "v453_signal_regime")
grouped(["regime","exit"], "v453_regime_exit")
grouped(["symbol","interval","exit"],
        "v453_symbol_interval_exit")
grouped(["tp_mult","sl_mult","hold"],
        "v453_tp_profile")

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

mfe.to_csv(f"{OUT}/v453_mfe.csv", index=False)

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

mae.to_csv(f"{OUT}/v453_mae.csv", index=False)

# ---------- DURATION ----------
dur = (
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

dur.to_csv(f"{OUT}/v453_duration.csv", index=False)

# ==========================================================
# MISSED TP — TARGET EXACT DE CHAQUE TRADE
# ==========================================================
df["tp_target"] = df["tp_mult"].abs()

df["reached_tp"] = df["mfe"] >= df["tp_target"]

df["missed_tp"] = (
    df["reached_tp"] &
    (df["exit"] != "tp")
)

miss = df[df["missed_tp"]].copy()

miss.to_csv(
    f"{OUT}/v453_missed_tp.csv",
    index=False
)

if len(miss):
    msum = (
        miss.groupby(
            [
                "symbol","interval","signal",
                "regime","profile","tp_mult",
                "sl_mult","hold","side_name"
            ],
            dropna=False
        )
        .agg(
            missed_tp=("missed_tp","size"),
            mean_net=("net","mean"),
            median_net=("net","median"),
            mean_mfe=("mfe","mean"),
            mean_mae=("mae","mean"),
            mean_duration=("duration_bars","mean")
        )
        .reset_index()
    )

    mside = (
        miss.groupby(["side_name"])
            .agg(
                missed_tp=("missed_tp","size"),
                mean_net=("net","mean"),
                mean_mfe=("mfe","mean"),
                mean_mae=("mae","mean")
            )
            .reset_index()
    )
else:
    msum = pd.DataFrame()
    mside = pd.DataFrame()

msum.to_csv(
    f"{OUT}/v453_missed_tp_summary.csv",
    index=False
)

mside.to_csv(
    f"{OUT}/v453_missed_tp_side.csv",
    index=False
)

# ---------- TP ATTEINT MAIS SORTIE SL/TIME ----------
print()
print("MISSED_TP", len(miss))
print(
    "MISSED_TP_RATE",
    f"{len(miss)/len(df):.2%}"
)

# ---------- SUMMARY ----------
gs = stats(df)

summary = f"""# SCALP LAB V4.5.3 — TRADE FORENSICS FINAL

## Validation V4.4

- Input : {len(df)}
- TP : {tp}
- SL : {sl}
- TIME : {tm}
- Total : {tp + sl + tm}
- EXIT CHECK : PASS

## Global OOS

- mean net/trade : {gs["mean_net"]:.4%}
- median net : {gs["median_net"]:.4%}
- win rate : {gs["win_rate"]:.2%}
- mean MFE : {gs["mean_mfe"]:.4%}
- mean MAE : {gs["mean_mae"]:.4%}
- mean duration : {gs["mean_duration"]:.2f} bars

## Missed TP

Définition stricte :

MFE >= TP cible propre au trade
ET sortie finale != TP.

- reached TP then not TP : {len(miss)}
- rate : {len(miss)/len(df):.2%}

## Données analysées

- LONG / SHORT
- TP / SL / TIME
- signal
- régime
- symbole
- intervalle
- profil TP/SL/hold
- MFE
- MAE
- durée

## Intégrité

- OOS uniquement
- Final holdout exclu
- Aucun nouveau signal
- Aucun nouveau paramètre
- Aucune optimisation
- Aucun trading réel
"""

with open(
    f"{OUT}/summary_v453.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(summary)

print()
print("V4.5.3 TERMINÉ")
print("V44 CHECK : PASS")
print("TRADES", len(df))
print("TP", tp)
print("SL", sl)
print("TIME", tm)
print("MISSED_TP", len(miss))
print("MISSED_TP_RATE", f"{len(miss)/len(df):.2%}")
