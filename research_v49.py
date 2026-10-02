from pathlib import Path
import pandas as pd
import numpy as np

OUT=Path("results")
SRC=OUT/"v48_trade_paths.csv"
d=pd.read_csv(SRC)

need=["symbol","interval","signal","regime","side","exit_reason",
      "path_class","net","mfe","mae","duration_bars",
      "tp50_before_sl50","sl50_before_tp50",
      "tp50_time","tp75_time","tp100_time",
      "sl50_time","sl75_time","sl100_time"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["net","mfe","mae","duration_bars"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

for c in ["tp50_before_sl50","sl50_before_tp50"]:
    d[c]=d[c].astype(bool)

def pct(x):
    return f"{100*x:.3f}%"

def agg(cols):
    return d.groupby(cols,observed=True).agg(
        trades=("net","size"),
        mean_net=("net","mean"),
        median_net=("net","median"),
        win_rate=("net",lambda x:(x>0).mean()),
        mean_mfe=("mfe","mean"),
        mean_mae=("mae","mean"),
        mean_duration=("duration_bars","mean"),
        tp=("exit_reason",lambda x:(x=="TP").sum()),
        sl=("exit_reason",lambda x:(x=="SL").sum()),
        time=("exit_reason",lambda x:(x=="TIME").sum()),
        tp50_first=("tp50_before_sl50","sum"),
        sl50_first=("sl50_before_tp50","sum")
    ).reset_index()

def save(cols,name):
    x=agg(cols)
    x.to_csv(OUT/name,index=False)
    return x

print("V4.9 | PATH x EDGE FORENSICS")
print("TRADES",len(d))

# 1. Classes globales
p=save(["path_class"],"v49_path_edge.csv")

# 2. Sortie x chemin
e=save(["exit_reason","path_class"],"v49_exit_path_edge.csv")

# 3. Signal x chemin
s=save(["signal","path_class"],"v49_signal_path_edge.csv")

# 4. Marché x chemin
m=save(["symbol","interval","path_class"],"v49_market_path_edge.csv")

# 5. Régime x chemin
r=save(["regime","path_class"],"v49_regime_path_edge.csv")

# 6. Signal x régime x chemin
sr=save(["signal","regime","path_class"],
        "v49_signal_regime_path.csv")

# 7. Côté x chemin
side=save(["side","path_class"],"v49_side_path_edge.csv")

# Classe économique simplifiée
d["edge_class"]=np.select([
    (d.path_class=="FAVORABLE_PATH")&(d.net>0),
    (d.path_class=="FAVORABLE_PATH")&(d.net<=0),
    (d.path_class=="EARLY_FAVORABLE")&(d.net>0),
    (d.path_class=="EARLY_ADVERSE")&(d.net>0),
    (d.path_class=="EARLY_ADVERSE")&(d.net<=0)
],[
    "FAVORABLE_WIN",
    "FAVORABLE_LOSS",
    "EARLY_FAVORABLE_WIN",
    "EARLY_ADVERSE_WIN",
    "EARLY_ADVERSE_LOSS"
],"OTHER")

ec=agg(["edge_class"])
ec.to_csv(OUT/"v49_edge_class.csv",index=False)

# Global
g={
    "trades":len(d),
    "mean_net":d.net.mean(),
    "median_net":d.net.median(),
    "win_rate":(d.net>0).mean(),
    "mean_mfe":d.mfe.mean(),
    "mean_mae":d.mae.mean(),
    "tp50_first":int(d.tp50_before_sl50.sum()),
    "sl50_first":int(d.sl50_before_tp50.sum()),
    "tp50_first_pct":d.tp50_before_sl50.mean(),
    "sl50_first_pct":d.sl50_before_tp50.mean()
}
pd.DataFrame([g]).to_csv(OUT/"v49_global.csv",index=False)

# Résumé
lines=[
"# SCALP LAB V4.9 — PATH × EDGE FORENSICS",
"",
f"- Trades OOS : {len(d)}",
"- FINAL HOLDOUT : exclu",
"- Source : V4.8 trade paths",
"- Stratégie V4.4 : inchangée",
"- Aucun nouveau paramètre testé.",
"",
"## Global",
"",
f"- mean net/trade : {pct(d.net.mean())}",
f"- median net : {pct(d.net.median())}",
f"- win rate : {d.net.gt(0).mean():.2%}",
f"- mean MFE : {pct(d.mfe.mean())}",
f"- mean MAE : {pct(d.mae.mean())}",
f"- TP50 avant SL50 : {d.tp50_before_sl50.sum()} ({d.tp50_before_sl50.mean():.2%})",
f"- SL50 avant TP50 : {d.sl50_before_tp50.sum()} ({d.sl50_before_tp50.mean():.2%})",
"",
"## Path classes",
"",
p.to_string(index=False),
"",
"## Exit × Path",
"",
e.to_string(index=False),
"",
"## Signal × Path",
"",
s.to_string(index=False),
"",
"## Market × Path",
"",
m.to_string(index=False),
"",
"## Regime × Path",
"",
r.to_string(index=False),
"",
"## Edge classes",
"",
ec.to_string(index=False),
"",
"## Méthode",
"",
"- Analyse strictement OOS.",
"- FINAL HOLDOUT exclu.",
"- Aucun recalcul de signal.",
"- Aucun paramètre modifié.",
"- Aucune nouvelle stratégie testée.",
"- Les trajectoires viennent de V4.8.",
"- L'objectif est d'isoler la source de l'edge et des pertes."
]

(OUT/"summary_v49.md").write_text("\n".join(lines),encoding="utf-8")

print("===== V4.9 =====")
print("TRADES",len(d))
print("MEAN_NET",pct(d.net.mean()))
print("WIN_RATE",f"{d.net.gt(0).mean():.2%}")
print("TP50_FIRST",int(d.tp50_before_sl50.sum()))
print("SL50_FIRST",int(d.sl50_before_tp50.sum()))
print("V4.9 TERMINÉ")
