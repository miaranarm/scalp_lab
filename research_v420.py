import pandas as pd
from pathlib import Path
P=Path("results");d=pd.read_csv(P/"v44_trades_oos.csv")
for c in ["net","train_mean","train_pf","fold_test_mean","fold_random_mean","fold_edge_random"]:d[c]=pd.to_numeric(d[c],errors="coerce")
def A(g):
 return pd.Series({"n":len(g),"net":g.net.mean(),"train":g.train_mean.mean(),"test":g.fold_test_mean.mean(),"random":g.fold_random_mean.mean(),"edge_random":g.fold_edge_random.mean(),"win":(g.net>0).mean(),"pf":g.net[g.net>0].sum()/abs(g.net[g.net<0].sum()) if (g.net<0).any() else float("inf")})
S=d.groupby(["candidate","signal"]).apply(A,include_groups=False).reset_index()
S=S.sort_values(["net"],ascending=False);S.to_csv(P/"v420_candidate.csv",index=False)
F=d.groupby(["candidate","signal","fold"]).apply(A,include_groups=False).reset_index()
F.to_csv(P/"v420_candidate_fold.csv",index=False)
Q=F.groupby(["candidate","signal"]).agg(folds=("fold","nunique"),positive=("net",lambda x:(x>0).sum()),median_net=("net","median"),worst_net=("net","min"),median_edge=("edge_random","median"),worst_edge=("edge_random","min")).reset_index()
Q=Q.merge(S[["candidate","signal","n","net","test","random","edge_random"]],on=["candidate","signal"])
Q.to_csv(P/"v420_stability.csv",index=False)
o=["# V4.20 — CANDIDATE / OOS STABILITY","","Aucun tuning. Holdout exclu.","","## CANDIDATE",S.to_string(index=False),"","## CANDIDATE × FOLD",F.to_string(index=False),"","## STABILITY",Q.to_string(index=False)]
(P/"summary_v420.md").write_text("\n".join(o),encoding="utf8");print("\n".join(o));print("V4.20 TERMINÉ")