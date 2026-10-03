from pathlib import Path
import pandas as pd,numpy as np
O=Path("results");T=O/"v44_trades_oos.csv";R=O/"v414_replay.csv"
print("V4.17 | TRUE SURVIVORSHIP AUDIT");o=pd.read_csv(T);r=pd.read_csv(R)
K=["symbol","interval","fold","signal","regime","profile","side"]
for c in K+["entry_time"]:
 if c not in o:raise SystemExit("v44 COLONNE ABSENTE: "+c)
for c in ["mode","net"]+K:
 if c not in r:raise SystemExit("v414 COLONNE ABSENTE: "+c)
o["entry_time"]=pd.to_datetime(o.entry_time,utc=True,errors="coerce")
if o.entry_time.isna().any():raise SystemExit("entry_time invalide")
o["_rank"]=o.groupby(K).cumcount();o["trade_id"]=[f"T{i:05d}" for i in range(len(o))]
orig=r[r["mode"]=="ORIGINAL"].copy();orig["_rank"]=orig.groupby(K).cumcount()
orig=orig.merge(o[K+["_rank","trade_id","entry_time"]],on=K+["_rank"],how="left",validate="one_to_one")
if orig.trade_id.isna().any():raise SystemExit("ORIGINAL non apparié")
orig=orig[["trade_id"]+K+["entry_time","net"]].rename(columns={"net":"original_net"});print("ORIGINAL",len(orig))
MODES=["B1_ALL","GAP0","GAP10","GAP25","GAP50"];A=[]
for mode in MODES:
 q=r[r["mode"]==mode].copy();q["_rank"]=q.groupby(K).cumcount()
 q=q.merge(o[K+["_rank","trade_id"]],on=K+["_rank"],how="left",validate="many_to_one")
 if q.trade_id.isna().any():raise SystemExit(f"{mode}: trade non apparié")
 q=q.merge(orig[["trade_id","original_net"]],on="trade_id",how="left",validate="one_to_one");q["mode"]=mode;A.append(q)
b=pd.concat(A,ignore_index=True)
rows=[]
for mode,q in b.groupby("mode"):
 ids=set(q.trade_id);rr=orig[orig.trade_id.isin(ids)];xx=orig[~orig.trade_id.isin(ids)];n=len(orig)
 sel=(rr.original_net.sum()-orig.original_net.sum())/n;ent=(q.net.sum()-rr.original_net.sum())/n
 rows.append({"mode":mode,"original_n":n,"retained_n":len(rr),"excluded_n":len(xx),"retained_pct":len(rr)/n,"excluded_pct":len(xx)/n,"all_original_mean":orig.original_net.mean(),"retained_original_mean":rr.original_net.mean(),"excluded_original_mean":xx.original_net.mean(),"retained_b1_mean":q.net.mean(),"selection_contribution":sel,"entry_contribution":ent,"total_contribution":sel+ent,"excluded_win":(xx.original_net>0).mean(),"excluded_loss_pct":(xx.original_net<0).mean(),"retained_original_win":(rr.original_net>0).mean(),"retained_b1_win":(q.net>0).mean()})
S=pd.DataFrame(rows);S.to_csv(O/"v417_survivorship.csv",index=False)
def table(cols,name):
 rows=[];virtual={"mode"}
 for key,q in b.groupby(cols):
  key=key if isinstance(key,tuple) else (key,);mask=np.ones(len(orig),bool)
  for c,v in zip(cols,key):
   if c not in virtual:mask&=orig[c].eq(v)
  base=orig[mask];ids=set(q.trade_id);rr=base[base.trade_id.isin(ids)];xx=base[~base.trade_id.isin(ids)]
  rows.append(dict(zip(cols,key))|{"original_n":len(base),"retained_n":len(rr),"excluded_n":len(xx),"retained_pct":len(rr)/len(base) if len(base) else np.nan,"original_mean":base.original_net.mean(),"retained_original_mean":rr.original_net.mean(),"excluded_original_mean":xx.original_net.mean() if len(xx) else np.nan,"b1_mean":q.net.mean(),"selection_contribution":(rr.original_net.sum()-base.original_net.sum())/len(base) if len(base) else np.nan,"entry_contribution":(q.net.sum()-rr.original_net.sum())/len(base) if len(base) else np.nan})
 z=pd.DataFrame(rows);z.to_csv(O/f"v417_{name}.csv",index=False);return z
Sg=table(["mode","signal"],"signal");G=table(["mode","regime"],"regime")
F=[];M=[]
for (mode,fold),q in b.groupby(["mode","fold"]):
 base=orig[orig.fold==fold];ids=set(q.trade_id);rr=base[base.trade_id.isin(ids)];xx=base[~base.trade_id.isin(ids)]
 F.append({"mode":mode,"fold":fold,"original_n":len(base),"retained_n":len(rr),"excluded_n":len(xx),"retained_pct":len(rr)/len(base),"original_mean":base.original_net.mean(),"retained_original_mean":rr.original_net.mean(),"excluded_original_mean":xx.original_net.mean() if len(xx) else np.nan,"b1_mean":q.net.mean(),"selection_contribution":(rr.original_net.sum()-base.original_net.sum())/len(base),"entry_contribution":(q.net.sum()-rr.original_net.sum())/len(base)})
for (mode,sym,it),q in b.groupby(["mode","symbol","interval"]):
 base=orig[(orig.symbol==sym)&(orig.interval==it)];ids=set(q.trade_id);rr=base[base.trade_id.isin(ids)];xx=base[~base.trade_id.isin(ids)]
 M.append({"mode":mode,"symbol":sym,"interval":it,"original_n":len(base),"retained_n":len(rr),"excluded_n":len(xx),"retained_pct":len(rr)/len(base),"original_mean":base.original_net.mean(),"retained_original_mean":rr.original_net.mean(),"excluded_original_mean":xx.original_net.mean() if len(xx) else np.nan,"b1_mean":q.net.mean(),"selection_contribution":(rr.original_net.sum()-base.original_net.sum())/len(base),"entry_contribution":(q.net.sum()-rr.original_net.sum())/len(base)})
F=pd.DataFrame(F);M=pd.DataFrame(M);F.to_csv(O/"v417_fold.csv",index=False);M.to_csv(O/"v417_market.csv",index=False)
audit=[]
for mode,q in b.groupby("mode"):
 qm=q.set_index("trade_id")
 for _,z in orig.iterrows():
  tid=z.trade_id;h=qm.loc[tid] if tid in qm.index else None
  audit.append({"trade_id":tid,"mode":mode,"symbol":z.symbol,"interval":z.interval,"fold":z.fold,"signal":z.signal,"regime":z.regime,"profile":z.profile,"side":z.side,"entry_time":z.entry_time,"original_net":z.original_net,"status":"RETAINED" if h is not None else "EXCLUDED","b1_net":float(h.net) if h is not None else np.nan,"delta_net":float(h.net)-float(z.original_net) if h is not None else np.nan})
AD=pd.DataFrame(audit);AD.to_csv(O/"v417_trade_audit.csv",index=False)
out=["# SCALP LAB V4.17 — TRUE SURVIVORSHIP AUDIT","",f"Original trades : {len(orig)}","Holdout : exclu","","## GLOBAL",S.to_string(index=False),"","## FOLD",F.to_string(index=False),"","## MARKET / INTERVAL",M.to_string(index=False),"","## SIGNAL",Sg.to_string(index=False),"","## REGIME",G.to_string(index=False),"","## METHODE","- selection_contribution = effet du rejet.","- entry_contribution = effet du changement d'entrée B1.","- total_contribution = selection + entry.","- Aucun nouveau signal/holdout/optimisation.","","V4.17 TERMINÉ"]
(O/"summary_v417.md").write_text("\n".join(out),encoding="utf-8")
print("\n===== V4.17 GLOBAL =====");print(S.to_string(index=False));print("\nV4.17 TERMINÉ")
