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

num=["entry_price","tp_price","sl_price","net","gross",
     "duration_bars","mfe","mae"]
for c in num:d[c]=pd.to_numeric(d[c],errors="coerce")

side=d.side.astype(str).str.upper()
long=side.eq("LONG")

d["tp_dist"]=np.where(long,
    d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price)
d["sl_dist"]=np.where(long,
    1-d.sl_price/d.entry_price,
    d.sl_price/d.entry_price)

d["mfe_tp"]=d.mfe/d.tp_dist
d["mae_sl"]=abs(d.mae)/d.sl_dist

d["mfe50"]=d.mfe_tp>=.50
d["mfe75"]=d.mfe_tp>=.75
d["mfe100"]=d.mfe_tp>=1
d["mae50"]=d.mae_sl>=.50
d["mae75"]=d.mae_sl>=.75
d["mae100"]=d.mae_sl>=1

d["captured"]=np.where(d.mfe>0,d.net/d.mfe,np.nan)

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
        mean_capture=("captured","mean"),
        mean_duration=("duration_bars","mean"),
        mfe50=("mfe50","sum"),
        mfe75=("mfe75","sum"),
        mfe100=("mfe100","sum"),
        mae50=("mae50","sum"),
        mae75=("mae75","sum"),
        mae100=("mae100","sum")
    ).reset_index()
    x.to_csv(OUT/file,index=False)

# Découpes principales
agg(["exit_reason"],"v47_exit.csv")
agg(["side","exit_reason"],"v47_exit_side.csv")
agg(["signal","exit_reason"],"v47_signal_exit.csv")
agg(["symbol","interval","exit_reason"],"v47_market_exit.csv")
agg(["signal","side"],"v47_signal_side.csv")
agg(["regime","exit_reason"],"v47_regime_exit.csv")

# Excursion croisée
d["excursion_class"]=np.select(
    [
        d.mfe100&~d.mae100,
        d.mfe100&d.mae100,
        d.mfe75&~d.mfe100,
        d.mfe50&~d.mfe75,
        ~d.mfe50
    ],
    [
        "MFE>=TP / MAE<SL",
        "MFE>=TP / MAE>=SL",
        "MFE75-100",
        "MFE50-75",
        "MFE<50"
    ],
    default="OTHER"
)
agg(["excursion_class"],"v47_excursion.csv")

# TIME détaillé
t=d[d.exit_reason=="TIME"].copy()
rows=[]
for name,m in [
    ("TIME_MFE<50",t.mfe_tp<.50),
    ("TIME_MFE50-75",(t.mfe_tp>=.50)&(t.mfe_tp<.75)),
    ("TIME_MFE75-100",(t.mfe_tp>=.75)&(t.mfe_tp<1)),
    ("TIME_MFE>=TP",t.mfe_tp>=1)
]:
    x=t[m]
    rows.append({
        "class":name,"n":len(x),
        "mean_net":x.net.mean() if len(x) else np.nan,
        "win":(x.net>0).mean() if len(x) else np.nan,
        "mean_mfe_tp":x.mfe_tp.mean() if len(x) else np.nan,
        "mean_mae_sl":x.mae_sl.mean() if len(x) else np.nan
    })
pd.DataFrame(rows).to_csv(OUT/"v47_time_excursion.csv",index=False)

# SL détaillé
s=d[d.exit_reason=="SL"].copy()
rows=[]
for name,m in [
    ("SL_MFE<50",s.mfe_tp<.50),
    ("SL_MFE50-75",(s.mfe_tp>=.50)&(s.mfe_tp<.75)),
    ("SL_MFE75-100",(s.mfe_tp>=.75)&(s.mfe_tp<1)),
    ("SL_MFE>=TP",s.mfe_tp>=1)
]:
    x=s[m]
    rows.append({
        "class":name,"n":len(x),
        "mean_net":x.net.mean() if len(x) else np.nan,
        "mean_mfe_tp":x.mfe_tp.mean() if len(x) else np.nan,
        "mean_mae_sl":x.mae_sl.mean() if len(x) else np.nan
    })
pd.DataFrame(rows).to_csv(OUT/"v47_sl_excursion.csv",index=False)

# Résumé global
g={
    "trades":len(d),
    "mean_net":d.net.mean(),
    "win_rate":(d.net>0).mean(),
    "mean_mfe":d.mfe.mean(),
    "mean_mae":d.mae.mean(),
    "mean_mfe_tp":d.mfe_tp.mean(),
    "mean_mae_sl":d.mae_sl.mean(),
    "mean_capture":d.captured.mean(),
    "mean_duration":d.duration_bars.mean(),
    "tp":(d.exit_reason=="TP").sum(),
    "sl":(d.exit_reason=="SL").sum(),
    "time":(d.exit_reason=="TIME").sum(),
    "mfe50":d.mfe50.sum(),
    "mfe75":d.mfe75.sum(),
    "mfe100":d.mfe100.sum(),
    "mae50":d.mae50.sum(),
    "mae75":d.mae75.sum(),
    "mae100":d.mae100.sum()
}
pd.DataFrame([g]).to_csv(OUT/"v47_global.csv",index=False)

lines=[
"# SCALP LAB V4.7 — EXIT FORENSICS",
"",
f"- Trades OOS : {len(d)}",
"- FINAL HOLDOUT : exclu",
"- Source : V4.4 trade-level",
"- Stratégie V4.4 : inchangée",
"- Aucun nouveau paramètre testé",
"",
"## Global",
"",
f"- mean net/trade : {d.net.mean():+.4%}",
f"- win rate : {(d.net>0).mean():.2%}",
f"- mean MFE : {d.mfe.mean():+.4%}",
f"- mean MAE : {d.mae.mean():+.4%}",
f"- MFE/TP : {d.mfe_tp.mean():.3f}",
f"- MAE/SL : {d.mae_sl.mean():.3f}",
f"- capture net/MFE : {d.captured.mean():+.2%}",
f"- durée : {d.duration_bars.mean():.2f} bars",
"",
"## Excursion",
"",
f"- MFE >= 50% TP : {d.mfe50.sum()} ({d.mfe50.mean():.2%})",
f"- MFE >= 75% TP : {d.mfe75.sum()} ({d.mfe75.mean():.2%})",
f"- MFE >= TP : {d.mfe100.sum()} ({d.mfe100.mean():.2%})",
f"- MAE >= 50% SL : {d.mae50.sum()} ({d.mae50.mean():.2%})",
f"- MAE >= 75% SL : {d.mae75.sum()} ({d.mae75.mean():.2%})",
f"- MAE >= SL : {d.mae100.sum()} ({d.mae100.mean():.2%})",
"",
"## Sorties",
"",
f"- TP : {(d.exit_reason=='TP').sum()}",
f"- SL : {(d.exit_reason=='SL').sum()}",
f"- TIME : {(d.exit_reason=='TIME').sum()}",
"",
"## Méthode",
"",
"- Analyse strictement OOS.",
"- Holdout final exclu.",
"- Aucun recalcul de signal.",
"- Aucun changement TP/SL/TIME.",
"- Les MFE/MAE sont des excursions OHLC.",
"- TP+SL sur une même bougie reste ambigu quant à l'ordre intrabougie.",
"",
]
(OUT/"summary_v47.md").write_text("\n".join(lines),encoding="utf-8")

print("V4.7 | EXIT FORENSICS")
print("INPUT",len(d))
print(f"MEAN NET {d.net.mean():+.4%}")
print(f"WIN {d.net.gt(0).mean():.2%}")
print(f"MFE/TP {d.mfe_tp.mean():.3f}")
print(f"MAE/SL {d.mae_sl.mean():.3f}")
print(f"MFE>=75% {d.mfe75.sum()}")
print(f"MFE>=TP {d.mfe100.sum()}")
print("V4.7 TERMINÉ")
