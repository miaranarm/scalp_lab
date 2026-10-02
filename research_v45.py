from pathlib import Path
import pandas as pd
import numpy as np

IN=Path("results/v44_trades_oos.csv")
OUT=Path("results")
OUT.mkdir(exist_ok=True)

def pct(x): return f"{x*100:+.4f}%"
def pick(df,names,default=np.nan):
    for n in names:
        if n in df.columns:return df[n]
    return pd.Series(default,index=df.index)

def agg(df,cols):
    if df.empty:return pd.DataFrame()
    g=df.groupby(cols,dropna=False)
    return g.agg(
        trades=("net", "size"),
        mean_net=("net","mean"),
        median_net=("net","median"),
        win_rate=("win","mean"),
        mean_mfe=("mfe","mean"),
        mean_mae=("mae","mean"),
        mean_duration=("duration","mean")
    ).reset_index()

print("V4.5 | TRADE FORENSICS DEEP ANALYSIS")

if not IN.exists():
    raise SystemExit("ERROR: results/v44_trades_oos.csv absent")

d=pd.read_csv(IN)
print("INPUT",len(d),"trades")

# ---- normalisation des colonnes V4.4 ----
d["net"]=pd.to_numeric(pick(d,["net","net_return","return"]),errors="coerce")
d["gross"]=pd.to_numeric(pick(d,["gross","gross_return"]),errors="coerce")
d["mfe"]=pd.to_numeric(pick(d,["mfe","MFE"]),errors="coerce")
d["mae"]=pd.to_numeric(pick(d,["mae","MAE"]),errors="coerce")
d["duration"]=pd.to_numeric(pick(d,["duration","bars","duration_bars"]),errors="coerce")

d["side"]=pick(d,["side","direction"],"NA")
d["exit"]=pick(d,["exit","exit_type"],"NA")
d["signal"]=pick(d,["signal"],"NA")
d["regime"]=pick(d,["regime"],"NA")
d["symbol"]=pick(d,["symbol"],"NA")
d["interval"]=pick(d,["interval"],"NA")
d["profile"]=pick(d,["profile"],"NA")

# win robuste
if "win" not in d:
    d["win"]=(d["net"]>0).astype(float)
else:
    d["win"]=pd.to_numeric(d["win"],errors="coerce")
    d.loc[d["win"].isna(),"win"]=(d.loc[d["win"].isna(),"net"]>0).astype(float)

d=d.dropna(subset=["net"]).copy()

# ============================================================
# 1. GLOBAL
# ============================================================
g=pd.DataFrame([{
    "trades":len(d),
    "mean_net":d.net.mean(),
    "median_net":d.net.median(),
    "win_rate":d.win.mean(),
    "mean_gross":d.gross.mean(),
    "mean_mfe":d.mfe.mean(),
    "mean_mae":d.mae.mean(),
    "mean_duration":d.duration.mean()
}])
g.to_csv(OUT/"v45_global.csv",index=False)

# ============================================================
# 2. MFE / MAE
# ============================================================
mfe_bins=[-np.inf,.001,.0025,.005,.0075,.01,np.inf]
mfe_lab=["<0.10%","0.10-0.25%","0.25-0.50%","0.50-0.75%",
         "0.75-1.00%",">1.00%"]
d["mfe_bucket"]=pd.cut(d.mfe,mfe_bins,labels=mfe_lab)

mae_bins=[-np.inf,-.01,-.0075,-.005,-.0025,-.001,0]
mae_lab=["<-1.00%","-1.00/-0.75%","-0.75/-0.50%",
         "-0.50/-0.25%","-0.25/-0.10%","-0.10/0%"]
d["mae_bucket"]=pd.cut(d.mae,mae_bins,labels=mae_lab)

d.groupby("mfe_bucket",observed=False).agg(
    trades=("net","size"),mean_net=("net","mean"),
    win_rate=("win","mean"),mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")).reset_index().to_csv(
        OUT/"v45_mfe.csv",index=False)

d.groupby("mae_bucket",observed=False).agg(
    trades=("net","size"),mean_net=("net","mean"),
    win_rate=("win","mean"),mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")).reset_index().to_csv(
        OUT/"v45_mae.csv",index=False)

# ============================================================
# 3. MISSED TP
# ============================================================
# MFE >= TP théorique mais sortie différente de TP.
# TP dépend du scénario V4.1 : 1.5%, 2%, 3%, 2%.
# Si la colonne tp existe, on l'utilise.
tp=pick(d,["tp","tp_pct","target"],np.nan)
tp=pd.to_numeric(tp,errors="coerce")

if tp.notna().any():
    d["tp_level"]=tp.abs()
else:
    d["tp_level"]=np.nan

# fallback : approximation par MFE >= 1.5%
d["reached_1p5"]=d.mfe>=.015
d["missed_tp"]=d.reached_1p5 & d.exit.ne("TP")

d[d.missed_tp].to_csv(OUT/"v45_missed_tp.csv",index=False)

miss=d[d.missed_tp]
pd.DataFrame([{
    "trades":len(miss),
    "mean_net":miss.net.mean() if len(miss) else np.nan,
    "win_rate":miss.win.mean() if len(miss) else np.nan,
    "mean_mfe":miss.mfe.mean() if len(miss) else np.nan,
    "mean_mae":miss.mae.mean() if len(miss) else np.nan
}]).to_csv(OUT/"v45_missed_tp_summary.csv",index=False)

# ============================================================
# 4. DUREE
# ============================================================
bins=[0,3,6,12,24,np.inf]
labs=["1-3","4-6","7-12","13-24",">24"]
d["duration_bucket"]=pd.cut(d.duration,bins= bins,labels=labs)

d.groupby("duration_bucket",observed=False).agg(
    trades=("net","size"),mean_net=("net","mean"),
    win_rate=("win","mean"),mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")).reset_index().to_csv(
        OUT/"v45_duration.csv",index=False)

# ============================================================
# 5. EXIT / SIDE / SIGNAL / REGIME / SYMBOL
# ============================================================
for name,cols in {
    "v45_exit.csv":["exit"],
    "v45_side.csv":["side"],
    "v45_side_exit.csv":["side","exit"],
    "v45_signal_exit.csv":["signal","exit"],
    "v45_regime_exit.csv":["regime","exit"],
    "v45_symbol_interval_exit.csv":["symbol","interval","exit"],
    "v45_signal_side.csv":["signal","side"],
    "v45_signal_regime.csv":["signal","regime"],
}.items():
    agg(d,cols).to_csv(OUT/name,index=False)

# ============================================================
# 6. EXIT PAR SIGNAL
# ============================================================
x=d.groupby(["signal","exit"],dropna=False).agg(
    trades=("net","size"),
    mean_net=("net","mean"),
    median_net=("net","median"),
    win_rate=("win","mean"),
    mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean"),
    mean_duration=("duration","mean")
).reset_index()

x.to_csv(OUT/"v45_signal_exit.csv",index=False)

# ============================================================
# 7. EXIT PAR REGIME
# ============================================================
x=d.groupby(["regime","exit"],dropna=False).agg(
    trades=("net","size"),
    mean_net=("net","mean"),
    win_rate=("win","mean"),
    mean_mfe=("mfe","mean"),
    mean_mae=("mae","mean")
).reset_index()

x.to_csv(OUT/"v45_regime_exit.csv",index=False)

# ============================================================
# 8. RAPPORT
# ============================================================
r=[]
r += [
"# SCALP LAB V4.5 — TRADE FORENSICS DEEP ANALYSIS",
"",
"- Source : `results/v44_trades_oos.csv`",
"- FINAL HOLDOUT : EXCLU",
"- Aucun nouveau signal.",
"- Aucun nouveau indicateur.",
"- Aucun changement de stratégie.",
"",
"## Global",
"",
f"- Trades : {len(d)}",
f"- Mean net/trade : {pct(d.net.mean())}",
f"- Median net : {pct(d.net.median())}",
f"- Win rate : {d.win.mean()*100:.2f}%",
f"- Mean gross : {pct(d.gross.mean())}",
f"- Mean MFE : {pct(d.mfe.mean())}",
f"- Mean MAE : {pct(d.mae.mean())}",
f"- Mean duration : {d.duration.mean():.2f} bars",
"",
"## Par côté",
""
]

for k,gp in d.groupby("side"):
    r.append(
        f"- {k}: n={len(gp)}, mean={pct(gp.net.mean())}, "
        f"win={gp.win.mean()*100:.2f}%, "
        f"MFE={pct(gp.mfe.mean())}, MAE={pct(gp.mae.mean())}"
    )

r += ["","## Sorties",""]

for k,gp in d.groupby("exit"):
    r.append(
        f"- {k}: n={len(gp)}, mean={pct(gp.net.mean())}, "
        f"win={gp.win.mean()*100:.2f}%, "
        f"MFE={pct(gp.mfe.mean())}, MAE={pct(gp.mae.mean())}"
    )

r += [
"",
"## MFE",
"",
"Les buckets MFE permettent de mesurer jusqu'où les trades "
"allaient réellement avant leur sortie.",
"",
"## Missed TP",
"",
f"- Trades avec MFE >= 1.50% mais sortie != TP : {len(miss)}",
"",
"## Durée",
"",
"Les résultats par durée permettent de vérifier si les pertes "
"se concentrent sur les trades trop courts ou trop longs.",
"",
"## Règle",
"",
"V4.5 est exclusivement descriptif : aucune optimisation "
"des paramètres n'est effectuée et le FINAL HOLDOUT reste verrouillé.",
]

(OUT/"summary_v45.md").write_text("\n".join(r)+"\n",encoding="utf-8")

print("")
print("========================================")
print("V4.5 TERMINÉ")
print("TRADES",len(d))
print("MISSED_TP",len(miss))
print("MEAN",pct(d.net.mean()))
print("WIN",f"{d.win.mean()*100:.2f}%")
print("MFE",pct(d.mfe.mean()))
print("MAE",pct(d.mae.mean()))
print("========================================")
