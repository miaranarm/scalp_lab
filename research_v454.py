import os
import pandas as pd
import numpy as np

IN = "results/v44_trades_oos.csv"
OUT = "results"
os.makedirs(OUT, exist_ok=True)

print("V4.5.4 | TP AUDIT")

df = pd.read_csv(IN)
print("INPUT", len(df))

req = [
    "symbol","interval","signal","regime","profile",
    "tp_mult","side","entry_price","tp_price","exit_price",
    "exit_reason","duration_bars","mfe","mae","net"
]

missing = [c for c in req if c not in df.columns]
if missing:
    raise SystemExit("ERROR colonnes: " + ",".join(missing))

# ---------- TYPES ----------
for c in [
    "tp_mult","entry_price","tp_price","exit_price",
    "duration_bars","mfe","mae","net"
]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df["side_name"] = (
    df["side"].astype(str).str.strip().str.upper()
    .replace({"1":"LONG","+1":"LONG","-1":"SHORT"})
)

df["exit"] = (
    df["exit_reason"].astype(str).str.strip().str.lower()
)

if (~df["side_name"].isin(["LONG","SHORT"])).any():
    raise SystemExit("ERROR side invalide")

if (~df["exit"].isin(["tp","sl","time"])).any():
    raise SystemExit("ERROR exit invalide")

if df[["entry_price","tp_price","mfe"]].isna().any().any():
    raise SystemExit("ERROR données prix/MFE invalides")

# ---------- TP RECONSTRUIT DEPUIS LES PRIX ----------
df["tp_target_price_pct"] = np.where(
    df["side_name"].eq("LONG"),
    df["tp_price"] / df["entry_price"] - 1.0,
    1.0 - df["tp_price"] / df["entry_price"]
)

df["tp_target_price_pct"] *= 100.0

# MFE V4.4 est exprimé en %
df["mfe_pct"] = df["mfe"]

# ---------- AUDIT ----------
df["reached_tp"] = df["mfe_pct"] + 1e-12 >= df["tp_target_price_pct"]

df["missed_tp"] = (
    df["reached_tp"] &
    (df["exit"] != "tp")
)

# progression vers TP
df["tp_progress"] = (
    df["mfe_pct"] /
    df["tp_target_price_pct"].replace(0, np.nan)
)

df["reached_50"] = df["tp_progress"] >= .50
df["reached_75"] = df["tp_progress"] >= .75
df["reached_90"] = df["tp_progress"] >= .90
df["reached_100"] = df["tp_progress"] >= 1.00

# ---------- CHECK GLOBAL ----------
tp = int((df["exit"] == "tp").sum())
sl = int((df["exit"] == "sl").sum())
tm = int((df["exit"] == "time").sum())

print("TP", tp)
print("SL", sl)
print("TIME", tm)

if (tp, sl, tm) != (791,1213,192):
    raise SystemExit(
        f"ERROR EXIT CHECK TP={tp} SL={sl} TIME={tm}"
    )

print("EXIT CHECK PASS")

# ---------- MISSED TP ----------
miss = df[df["missed_tp"]].copy()
miss.to_csv(f"{OUT}/v454_missed_tp.csv", index=False)

# ---------- GLOBAL ----------
summary = pd.DataFrame([{
    "trades": len(df),
    "tp": tp,
    "sl": sl,
    "time": tm,
    "mean_net": df["net"].mean(),
    "median_net": df["net"].median(),
    "win_rate": (df["net"] > 0).mean(),
    "mean_mfe": df["mfe_pct"].mean(),
    "mean_mae": df["mae"].mean(),
    "mean_tp_target": df["tp_target_price_pct"].mean(),
    "mean_tp_progress": df["tp_progress"].mean(),
    "reached_50": df["reached_50"].mean(),
    "reached_75": df["reached_75"].mean(),
    "reached_90": df["reached_90"].mean(),
    "reached_100": df["reached_100"].mean(),
    "missed_tp": len(miss),
    "missed_tp_rate": len(miss) / len(df)
}])

summary.to_csv(f"{OUT}/v454_global.csv", index=False)

# ---------- PAR EXIT ----------
by_exit = (
    df.groupby("exit")
      .agg(
          n=("exit","size"),
          mean_net=("net","mean"),
          mean_mfe=("mfe_pct","mean"),
          mean_tp_target=("tp_target_price_pct","mean"),
          mean_tp_progress=("tp_progress","mean"),
          reached_50=("reached_50","mean"),
          reached_75=("reached_75","mean"),
          reached_90=("reached_90","mean"),
          reached_100=("reached_100","mean"),
          missed_tp=("missed_tp","sum")
      )
      .reset_index()
)

by_exit.to_csv(f"{OUT}/v454_exit.csv", index=False)

# ---------- PAR COTE ----------
by_side = (
    df.groupby("side_name")
      .agg(
          n=("side_name","size"),
          mean_net=("net","mean"),
          mean_mfe=("mfe_pct","mean"),
          mean_tp_target=("tp_target_price_pct","mean"),
          mean_tp_progress=("tp_progress","mean"),
          reached_50=("reached_50","mean"),
          reached_75=("reached_75","mean"),
          reached_90=("reached_90","mean"),
          reached_100=("reached_100","mean"),
          missed_tp=("missed_tp","sum")
      )
      .reset_index()
)

by_side.to_csv(f"{OUT}/v454_side.csv", index=False)

# ---------- SIGNAL ----------
by_signal = (
    df.groupby(["signal"])
      .agg(
          n=("signal","size"),
          mean_net=("net","mean"),
          mean_mfe=("mfe_pct","mean"),
          mean_tp_target=("tp_target_price_pct","mean"),
          mean_tp_progress=("tp_progress","mean"),
          reached_50=("reached_50","mean"),
          reached_75=("reached_75","mean"),
          reached_90=("reached_90","mean"),
          reached_100=("reached_100","mean"),
          missed_tp=("missed_tp","sum")
      )
      .reset_index()
)

by_signal.to_csv(f"{OUT}/v454_signal.csv", index=False)

# ---------- SYMBOLE / INTERVALLE ----------
by_market = (
    df.groupby(["symbol","interval"])
      .agg(
          n=("symbol","size"),
          mean_net=("net","mean"),
          mean_mfe=("mfe_pct","mean"),
          mean_tp_target=("tp_target_price_pct","mean"),
          mean_tp_progress=("tp_progress","mean"),
          reached_50=("reached_50","mean"),
          reached_75=("reached_75","mean"),
          reached_90=("reached_90","mean"),
          reached_100=("reached_100","mean"),
          missed_tp=("missed_tp","sum")
      )
      .reset_index()
)

by_market.to_csv(f"{OUT}/v454_market.csv", index=False)

# ---------- REGIME ----------
by_regime = (
    df.groupby("regime")
      .agg(
          n=("regime","size"),
          mean_net=("net","mean"),
          mean_mfe=("mfe_pct","mean"),
          mean_tp_target=("tp_target_price_pct","mean"),
          mean_tp_progress=("tp_progress","mean"),
          reached_50=("reached_50","mean"),
          reached_75=("reached_75","mean"),
          reached_90=("reached_90","mean"),
          reached_100=("reached_100","mean"),
          missed_tp=("missed_tp","sum")
      )
      .reset_index()
)

by_regime.to_csv(f"{OUT}/v454_regime.csv", index=False)

# ---------- MISSED TP DETAIL ----------
if len(miss):
    miss_summary = (
        miss.groupby(
            ["symbol","interval","signal","regime",
             "side_name","tp_mult","sl_mult","hold"]
        )
        .agg(
            n=("missed_tp","size"),
            mean_mfe=("mfe_pct","mean"),
            mean_tp_target=("tp_target_price_pct","mean"),
            mean_tp_progress=("tp_progress","mean"),
            mean_net=("net","mean")
        )
        .reset_index()
    )
else:
    miss_summary = pd.DataFrame(
        columns=[
            "symbol","interval","signal","regime",
            "side_name","tp_mult","sl_mult","hold",
            "n","mean_mfe","mean_tp_target",
            "mean_tp_progress","mean_net"
        ]
    )

miss_summary.to_csv(
    f"{OUT}/v454_missed_tp_summary.csv",
    index=False
)

# ---------- CONSOLE ----------
print()
print("TP_TARGET_MEAN",
      f"{df['tp_target_price_pct'].mean():.4f}%")

print("MFE_MEAN",
      f"{df['mfe_pct'].mean():.4f}%")

print("REACHED_50",
      f"{df['reached_50'].mean():.2%}")

print("REACHED_75",
      f"{df['reached_75'].mean():.2%}")

print("REACHED_90",
      f"{df['reached_90'].mean():.2%}")

print("REACHED_100",
      f"{df['reached_100'].mean():.2%}")

print("MISSED_TP", len(miss))
print("MISSED_TP_RATE", f"{len(miss)/len(df):.2%}")

# ---------- SUMMARY ----------
text = f"""# SCALP LAB V4.5.4 — TP AUDIT

## Validation

- Input : {len(df)}
- TP : {tp}
- SL : {sl}
- TIME : {tm}
- EXIT CHECK : PASS
- OOS uniquement
- Final holdout exclu

## TP reconstruit

Le TP cible est reconstruit directement depuis
entry_price + tp_price + side.

Aucune dépendance à l'unité de tp_mult.

- TP cible moyen : {df["tp_target_price_pct"].mean():.4%}
- MFE moyen : {df["mfe_pct"].mean():.4%}

## Progression vers TP

- >= 50% : {df["reached_50"].mean():.2%}
- >= 75% : {df["reached_75"].mean():.2%}
- >= 90% : {df["reached_90"].mean():.2%}
- >= 100% : {df["reached_100"].mean():.2%}

## Missed TP

Définition :

MFE >= TP réellement reconstruit
ET sortie finale != TP.

- Missed TP : {len(miss)}
- Taux : {len(miss)/len(df):.2%}

## Intégrité

- données V4.4 inchangées
- aucun nouveau signal
- aucun nouveau paramètre
- aucune optimisation
- aucun trading réel
"""

with open(
    f"{OUT}/summary_v454.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(text)

print()
print("V4.5.4 TERMINÉ")
