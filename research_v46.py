from pathlib import Path
import numpy as np
import pandas as pd

OUT=Path("results")
SRC=OUT/"v44_trades_oos.csv"

d=pd.read_csv(SRC)

need=["symbol","interval","signal","regime","profile","side",
      "entry_price","tp_price","sl_price","net","gross",
      "exit_reason","duration_bars","mfe","mae"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","sl_price","net","gross",
          "duration_bars","mfe","mae"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

# Distances TP/SL exactes depuis les prix V4.4
long=d.side.astype(str).str.upper().eq("LONG")

d["tp_dist"]=np.where(
    long,d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price
)
d["sl_dist"]=np.where(
    long,1-d.sl_price/d.entry_price,
    d.sl_price/d.entry_price-1
)

# Excursions normalisées
d["mfe_tp"]=d.mfe/d.tp_dist
d["mae_sl"]=abs(d.mae)/d.sl_dist

# Capture théorique du potentiel favorable
d["capture"]=np.where(d.mfe>0,d.net/d.mfe,np.nan)

# Classes simples, sans optimisation
d["mfe_zone"]=pd.cut(
    d.mfe_tp,
    [-np.inf,.25,.50,.75,1.00,1.50,2.00,np.inf],
    labels=["<25%","25-50%","50-75%","75-100%",
            "100-150%","150-200%",">200%"]
)

d["mae_zone"]=pd.cut(
    d.mae_sl,
    [-np.inf,.25,.50,.75,1.00,1.50,2.00,np.inf],
    labels=["<25%","25-50%","50-75%","75-100%",
            "100-150%","150-200%",">200%"]
)

d["duration_zone"]=pd.cut(
    d.duration_bars,
    [-np.inf,1,3,6,12,24,np.inf],
    labels=["1","2-3","4-6","7-12","13-24",">24"]
)

def agg(cols,file):
    x=d.groupby(cols,observed=True).agg(
        n=("net","size"),
        mean_net=("net","mean"),
        median_net=("net","median"),
        win=("net",lambda x:(x>0).mean()),
        mean_mfe=("mfe","mean"),
        mean_mae=("mae","mean"),
        mean_mfe_tp=("mfe_tp","mean"),
        mean_mae_sl=("mae_sl","mean"),
        mean_duration=("duration_bars","mean")
    ).reset_index()
    x.to_csv(OUT/file,index=False)

# Vues principales
agg(["mfe_zone"],"v46_mfe_zone.csv")
agg(["mae_zone"],"v46_mae_zone.csv")
agg(["duration_zone"],"v46_duration_zone.csv")
agg(["exit_reason"],"v46_exit.csv")
agg(["side"],"v46_side.csv")
agg(["symbol","interval"],"v46_symbol_interval.csv")
agg(["signal"],"v46_signal.csv")
agg(["regime"],"v46_regime.csv")
agg(["signal","regime"],"v46_signal_regime.csv")

# Interactions importantes
agg(["exit_reason","side"],"v46_exit_side.csv")
agg(["signal","side"],"v46_signal_side.csv")
agg(["signal","exit_reason"],"v46_signal_exit.csv")
agg(["symbol","interval","exit_reason"],"v46_market_exit.csv")

# Tableau global
g=pd.DataFrame([{
    "trades":len(d),
    "mean_net":d.net.mean(),
    "median_net":d.net.median(),
    "win_rate":(d.net>0).mean(),
    "mean_gross":d.gross.mean(),
    "mean_mfe":d.mfe.mean(),
    "mean_mae":d.mae.mean(),
    "mean_mfe_tp":d.mfe_tp.mean(),
    "mean_mae_sl":d.mae_sl.mean(),
    "mean_duration":d.duration_bars.mean(),
    "tp":(d.exit_reason=="TP").sum(),
    "sl":(d.exit_reason=="SL").sum(),
    "time":(d.exit_reason=="TIME").sum(),
    "mfe_ge_tp":(d.mfe_tp>=1).sum(),
    "mae_ge_sl":(d.mae_sl>=1).sum(),
    "mfe_ge_tp_pct":(d.mfe_tp>=1).mean(),
    "mae_ge_sl_pct":(d.mae_sl>=1).mean()
}])
g.to_csv(OUT/"v46_global.csv",index=False)

# Diagnostics de structure
d["mfe_ge_tp"]=d.mfe_tp>=1
d["mae_ge_sl"]=d.mae_sl>=1
d["good_excursion"]=d.mfe_tp>=.75
d["bad_excursion"]=d.mae_sl>=.75

classes=[
    ("TP_REACHED",d.mfe_ge_tp),
    ("TP_NOT_REACHED",~d.mfe_ge_tp),
    ("STRONG_MFE",d.good_excursion),
    ("STRONG_MAE",d.bad_excursion),
    ("MFE_AND_MAE_STRONG",d.good_excursion&d.bad_excursion),
    ("LOW_MFE_LOW_MAE",(d.mfe_tp<.50)&(d.mae_sl<.50)),
]

rows=[]
for name,m in classes:
    x=d[m]
    rows.append({
        "class":name,
        "n":len(x),
        "pct":len(x)/len(d),
        "mean_net":x.net.mean() if len(x) else np.nan,
        "win":(x.net>0).mean() if len(x) else np.nan,
        "mean_mfe_tp":x.mfe_tp.mean() if len(x) else np.nan,
        "mean_mae_sl":x.mae_sl.mean() if len(x) else np.nan
    })

pd.DataFrame(rows).to_csv(OUT/"v46_excursion_classes.csv",index=False)

# Rapport lisible
lines=[
"# SCALP LAB V4.6 — ENTRY / EXCURSION FORENSICS",
"",
f"- Trades OOS : {len(d)}",
"- FINAL HOLDOUT : exclu",
"- Source : V4.4 trade-level",
"- Aucun signal ou paramètre ajouté",
"",
"## Global",
"",
f"- mean net/trade : {d.net.mean():+.4%}",
f"- median net : {d.net.median():+.4%}",
f"- win rate : {(d.net>0).mean():.2%}",
f"- mean MFE : {d.mfe.mean():+.4%}",
f"- mean MAE : {d.mae.mean():+.4%}",
f"- MFE / TP moyen : {d.mfe_tp.mean():.3f}",
f"- MAE / SL moyen : {d.mae_sl.mean():.3f}",
f"- durée moyenne : {d.duration_bars.mean():.2f} bars",
"",
"## Excursions",
"",
f"- MFE >= TP : {(d.mfe_tp>=1).sum()} ({(d.mfe_tp>=1).mean():.2%})",
f"- MAE >= SL : {(d.mae_sl>=1).sum()} ({(d.mae_sl>=1).mean():.2%})",
f"- MFE >=75% TP : {(d.mfe_tp>=.75).sum()} ({(d.mfe_tp>=.75).mean():.2%})",
f"- MAE >=75% SL : {(d.mae_sl>=.75).sum()} ({(d.mae_sl>=.75).mean():.2%})",
"",
"## Sorties",
"",
f"- TP : {(d.exit_reason=='TP').sum()}",
f"- SL : {(d.exit_reason=='SL').sum()}",
f"- TIME : {(d.exit_reason=='TIME').sum()}",
"",
"## Important",
"",
"- Analyse strictement OOS.",
"- Holdout final exclu.",
"- Aucune optimisation.",
"- V4.4 inchangée.",
"- MFE/MAE proviennent du replay OHLC V4.4.",
"- L'ordre intrabougie reste inconnu lorsque TP et SL sont",
"  tous deux atteints sur la même bougie.",
""
]

(OUT/"summary_v46.md").write_text("\n".join(lines),encoding="utf-8")

print("V4.6 | ENTRY / EXCURSION FORENSICS")
print("INPUT",len(d))
print(f"MEAN NET {d.net.mean():+.4%}")
print(f"WIN {d.net.gt(0).mean():.2%}")
print(f"MFE/TP {d.mfe_tp.mean():.3f}")
print(f"MAE/SL {d.mae_sl.mean():.3f}")
print(f"TP REACHED {(d.mfe_tp>=1).sum()}")
print(f"SL REACHED {(d.mae_sl>=1).sum()}")
print("V4.6 TERMINÉ")
