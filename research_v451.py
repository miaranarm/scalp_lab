from pathlib import Path
import pandas as pd
import numpy as np

IN=Path("results/v44_trades_oos.csv")
OUT=Path("results")
OUT.mkdir(exist_ok=True)

def S(d,names,default=np.nan):
    for n in names:
        if n in d.columns:return d[n]
    return pd.Series(default,index=d.index)

def pct(x):
    return "nan" if pd.isna(x) else f"{x*100:+.4f}%"

def agg(d,cols):
    return d.groupby(cols,dropna=False).agg(
        trades=("net","size"),
        mean_net=("net","mean"),
        median_net=("net","median"),
        win_rate=("win","mean"),
        mean_mfe=("mfe","mean"),
        mean_mae=("mae","mean"),
        mean_duration=("duration","mean")
    ).reset_index()

print("V4.5.1 | TRADE FORENSICS CORRECTED")

if not IN.exists():
    raise SystemExit("ERROR: v44_trades_oos.csv absent")

d=pd.read_csv(IN)

print("INPUT",len(d))
print("COLUMNS",",".join(d.columns))

# ------------------------------------------------------------
# COLONNES V4.4
# ------------------------------------------------------------
d["net"]=pd.to_numeric(S(d,["net"]),errors="coerce")
d["gross"]=pd.to_numeric(S(d,["gross"]),errors="coerce")
d["mfe"]=pd.to_numeric(S(d,["mfe","MFE"]),errors="coerce")
d["mae"]=pd.to_numeric(S(d,["mae","MAE"]),errors="coerce")
d["duration"]=pd.to_numeric(S(d,["duration"]),errors="coerce")

# V4.4 utilise "kind" : tp / sl / time
if "kind" not in d.columns:
    raise SystemExit("ERROR: colonne V4.4 'kind' absente")

d["exit"]=d["kind"].astype(str).str.lower()

# V4.4 side : 1 = LONG, -1 = SHORT
if "side" not in d.columns:
    raise SystemExit("ERROR: colonne V4.4 'side' absente")

sv=pd.to_numeric(d["side"],errors="coerce")
d["side"]=sv.map({1:"LONG",-1:"SHORT"}).fillna(d["side"].astype(str))

d["signal"]=S(d,["signal"],"NA")
d["regime"]=S(d,["regime"],"NA")
d["symbol"]=S(d,["symbol"],"NA")
d["interval"]=S(d,["interval"],"NA")
d["profile"]=S(d,["profile"],"NA")

d["win"]=(d["net"]>0).astype(float)
d=d.dropna(subset=["net"]).copy()

# ------------------------------------------------------------
# CONTROLE STRICT V4.4
# ------------------------------------------------------------
counts=d["exit"].value_counts().to_dict()

tp=int(counts.get("tp",0))
sl=int(counts.get("sl",0))
tm=int(counts.get("time",0))
total=tp+sl+tm

print("TP",tp)
print("SL",sl)
print("TIME",tm)
print("TOTAL",total)

if not (tp==791 and sl==1213 and tm==192 and total==2196):
    raise SystemExit(
        f"ERROR COHERENCE V4.4 | TP={tp} SL={sl} "
        f"TIME={tm} TOTAL={total}"
    )

print("V44 EXIT CHECK PASS")

# ------------------------------------------------------------
# GLOBAL
# ------------------------------------------------------------
pd.DataFrame([{
    "trades":len(d),
    "mean_net":d.net.mean(),
    "median_net":d.net.median(),
    "win_rate":d.win.mean(),
    "mean_gross":d.gross.mean(),
    "mean_mfe":d.mfe.mean(),
    "mean_mae":d.mae.mean(),
    "mean_duration":d.duration.mean()
}]).to_csv(OUT/"v451_global.csv",index=False)

# ------------------------------------------------------------
# MFE
# ------------------------------------------------------------
bins=[-np.inf,.001,.0025,.005,.0075,.01,np.inf]
labs=[
    "<0.10%",
    "0.10-0.25%",
    "0.25-0.50%",
    "0.50-0.75%",
    "0.75-1.00%",
    ">1.00%"
]

d["mfe_bucket"]=pd.cut(
    d.mfe,bins=bins,labels=labs
)

d.groupby(
    "mfe_bucket",observed=False
).agg(
    trades=("net","size"),
    mean_net=("net","mean"),
    win_rate=("win","mean"),
    mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")
).reset_index().to_csv(
    OUT/"v451_mfe.csv",index=False
)

# ------------------------------------------------------------
# MAE
# ------------------------------------------------------------
bins=[-np.inf,-.01,-.0075,-.005,-.0025,-.001,0]
labs=[
    "<-1.00%",
    "-1.00/-0.75%",
    "-0.75/-0.50%",
    "-0.50/-0.25%",
    "-0.25/-0.10%",
    "-0.10/0%"
]

d["mae_bucket"]=pd.cut(
    d.mae,bins=bins,labels=labs
)

d.groupby(
    "mae_bucket",observed=False
).agg(
    trades=("net","size"),
    mean_net=("net","mean"),
    win_rate=("win","mean"),
    mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")
).reset_index().to_csv(
    OUT/"v451_mae.csv",index=False
)

# ------------------------------------------------------------
# MISSED TP
# ------------------------------------------------------------
# Analyse descriptive :
# MFE >= 1.5% mais sortie différente de TP.
d["missed_tp"]=(
    (d.mfe>=0.015) &
    (d.exit!="tp")
)

miss=d[d.missed_tp].copy()

miss.to_csv(
    OUT/"v451_missed_tp.csv",index=False
)

pd.DataFrame([{
    "trades":len(miss),
    "mean_net":miss.net.mean(),
    "win_rate":miss.win.mean(),
    "mean_mfe":miss.mfe.mean(),
    "mean_mae":miss.mae.mean(),
    "mean_duration":miss.duration.mean()
}]).to_csv(
    OUT/"v451_missed_tp_summary.csv",
    index=False
)

# ------------------------------------------------------------
# DUREE
# ------------------------------------------------------------
bins=[0,3,6,12,24,np.inf]
labs=["1-3","4-6","7-12","13-24",">24"]

d["duration_bucket"]=pd.cut(
    d.duration,bins=bins,labels=labs
)

d.groupby(
    "duration_bucket",observed=False
).agg(
    trades=("net","size"),
    mean_net=("net","mean"),
    win_rate=("win","mean"),
    mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")
).reset_index().to_csv(
    OUT/"v451_duration.csv",index=False
)

# ------------------------------------------------------------
# ANALYSES
# ------------------------------------------------------------
for name,cols in {
    "v451_exit.csv":["exit"],
    "v451_side.csv":["side"],
    "v451_side_exit.csv":["side","exit"],
    "v451_signal_exit.csv":["signal","exit"],
    "v451_regime_exit.csv":["regime","exit"],
    "v451_symbol_interval_exit.csv":["symbol","interval","exit"],
    "v451_signal_side.csv":["signal","side"],
    "v451_signal_regime.csv":["signal","regime"],
}.items():
    agg(d,cols).to_csv(OUT/name,index=False)

# ------------------------------------------------------------
# SORTIES
# ------------------------------------------------------------
exit_rows=[]
for k,g in d.groupby("exit"):
    exit_rows.append({
        "exit":k,
        "trades":len(g),
        "mean_net":g.net.mean(),
        "median_net":g.net.median(),
        "win_rate":g.win.mean(),
        "mean_mfe":g.mfe.mean(),
        "mean_mae":g.mae.mean(),
        "mean_duration":g.duration.mean()
    })

pd.DataFrame(exit_rows).to_csv(
    OUT/"v451_exit_detail.csv",index=False
)

# ------------------------------------------------------------
# RAPPORT
# ------------------------------------------------------------
r=[
"# SCALP LAB V4.5.1 — TRADE FORENSICS CORRECTED",
"",
"- Source : `results/v44_trades_oos.csv`",
"- FINAL HOLDOUT : EXCLU",
"- Aucun nouveau backtest.",
"- Aucun nouveau signal.",
"- Aucun changement de stratégie.",
"",
"## Contrôle V4.4",
"",
f"- Total : {len(d)}",
f"- TP : {tp}",
f"- SL : {sl}",
f"- TIME : {tm}",
"- Statut : PASS",
"",
"## Global",
"",
f"- Mean net/trade : {pct(d.net.mean())}",
f"- Median net : {pct(d.net.median())}",
f"- Win rate : {d.win.mean()*100:.2f}%",
f"- Mean gross : {pct(d.gross.mean())}",
f"- Mean MFE : {pct(d.mfe.mean())}",
f"- Mean MAE : {pct(d.mae.mean())}",
f"- Mean duration : {d.duration.mean():.2f} bars",
"",
"## Côté",
""
]

for k,g in d.groupby("side"):
    r.append(
        f"- {k}: n={len(g)}, "
        f"mean={pct(g.net.mean())}, "
        f"win={g.win.mean()*100:.2f}%, "
        f"MFE={pct(g.mfe.mean())}, "
        f"MAE={pct(g.mae.mean())}"
    )

r+=["","## Sorties",""]

for k,g in d.groupby("exit"):
    r.append(
        f"- {k.upper()}: n={len(g)}, "
        f"mean={pct(g.net.mean())}, "
        f"win={g.win.mean()*100:.2f}%, "
        f"MFE={pct(g.mfe.mean())}, "
        f"MAE={pct(g.mae.mean())}, "
        f"duration={g.duration.mean():.2f}"
    )

r+=[
"",
"## Missed TP",
"",
f"- MFE >= 1.50% mais sortie != TP : {len(miss)}",
f"- Part des trades : {len(miss)/len(d)*100:.2f}%",
f"- Mean net : {pct(miss.net.mean())}",
f"- Mean MFE : {pct(miss.mfe.mean())}",
f"- Mean MAE : {pct(miss.mae.mean())}",
"",
"## Principe",
"",
"Cette analyse reste descriptive.",
"Aucun paramètre n'est optimisé.",
"Le FINAL HOLDOUT reste verrouillé.",
]

(OUT/"summary_v451.md").write_text(
    "\n".join(r)+"\n",
    encoding="utf-8"
)

print("")
print("========================================")
print("V4.5.1 TERMINÉ")
print("V44 CHECK : PASS")
print("TRADES",len(d))
print("TP",tp)
print("SL",sl)
print("TIME",tm)
print("MISSED_TP",len(miss))
print("MEAN",pct(d.net.mean()))
print("WIN",f"{d.win.mean()*100:.2f}%")
print("MFE",pct(d.mfe.mean()))
print("MAE",pct(d.mae.mean()))
print("========================================")
