import pandas as pd,numpy as np
from pathlib import Path
P=Path("results");d=pd.read_csv(P/"v44_trades_oos.csv");d["net"]=pd.to_numeric(d.net)
def stat(x):
 a=x.net.to_numpy(); n=len(a); rng=np.random.default_rng(20261003)
 bs=np.mean(rng.choice(a,(5000,n),replace=True),1) if n else np.array([np.nan])
 return pd.Series({"n":n,"mean":a.mean(),"median":np.median(a),"win":(a>0).mean(),"ci_lo":np.quantile(bs,.025),"ci_hi":np.quantile(bs,.975)})
rows=[]
for sig,g in d.groupby("signal"):
 z=stat(g);z["signal"]=sig;rows.append(z)
S=pd.DataFrame(rows).sort_values("mean",ascending=False);S.to_csv(P/"v419_signal_ci.csv",index=False)
F=d.groupby(["signal","fold"]).apply(lambda x:stat(x),include_groups=False).reset_index()
F.to_csv(P/"v419_signal_fold.csv",index=False)
Q=F.groupby("signal").agg(folds=("fold","nunique"),positive_folds=("mean",lambda x:(x>0).sum()),median_fold=("mean","median"),worst_fold=("mean","min")).reset_index()
Q=Q.merge(S[["signal","n","mean","ci_lo","ci_hi"]],on="signal");Q.to_csv(P/"v419_stability.csv",index=False)
o=["# V4.19 — STABILITY / CONFIDENCE AUDIT","","Aucun tuning. Aucun holdout utilisé pour sélectionner.","","## SIGNAL CI",S.to_string(index=False),"","## SIGNAL × FOLD",F.to_string(index=False),"","## STABILITY",Q.to_string(index=False)]
(P/"summary_v419.md").write_text("\n".join(o),encoding="utf8");print("\n".join(o));print("V4.19 TERMINÉ")