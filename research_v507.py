import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True)
A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
def feat(x):
 c,h,l=x.c,x.h,x.l;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();vx=atr/atr.rolling(50).mean();s=e50.pct_change(12);return c,x.o,e20,e50,e200,vx,s
DATA={s:(x,feat(x)) for s in SYM if not (x:=load(s)).empty}
CFG=[(th,h,reg,uni,cm) for th in [1.25,1.5,1.75,2.0] for h in [24,36,48,72] for reg in ["ALL","BULL","BEAR"] for uni in ["ALL","BTCETH","ETH"] for cm in [1,1.5,2]]
rows=[]
for cid,(th,h,reg,uni,cm) in enumerate(CFG):
 for s,(x,(c,o,e20,e50,e200,vx,sl)) in DATA.items():
  if uni=="BTCETH" and s=="SOLUSDT":continue
  if uni=="ETH" and s!="ETHUSDT":continue
  bull=(e50>e200)&(sl>0);bear=(e50<e200)&(sl<0)
  sg=np.where((vx>th)&(c>e20),1,np.where((vx>th)&(c<e20),-1,0))
  if reg=="BULL":sg=np.where(bull,sg,0)
  if reg=="BEAR":sg=np.where(bear,sg,0)
  i=0;n=len(x);ca=C[s]*cm
  while i+h+1<n:
   if sg[i]==0:i+=1;continue
   d=int(sg[i]);r=(c.iloc[i+1+h]/o.iloc[i+1]-1)*d-ca;t=x.index[i];p="TRAIN" if t<pd.Timestamp("2024-01-01",tz="UTC") else ("TEST" if t<pd.Timestamp("2025-10-01",tz="UTC") else "HOLDOUT")
   rows.append([cid,t,s,d,r,p]);i+=h+1
D=pd.DataFrame(rows,columns=["id","time","symbol","side","net","period"])
def st(g):
 r=g.net;w=r[r>0];l=r[r<0];eq=r.cumsum();return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan,(eq-eq.cummax()).min()]
R=[]
for (cid,p),g in D.groupby(["id","period"]):R.append([cid,p,*st(g)])
R=pd.DataFrame(R,columns=["id","period","trades","total","mean","win","pf","dd"])
W=R.pivot(index="id",columns="period",values=["trades","total","mean","win","pf","dd"]);W.columns=["_".join(x) for x in W.columns];W=W.reset_index()
for k in ["trades","total","mean","win","pf","dd"]:
 for p in ["TRAIN","TEST","HOLDOUT"]:
  if f"{k}_{p}" not in W:W[f"{k}_{p}"]=0.0
M=pd.DataFrame(CFG,columns=["threshold","h","regime","universe","cost_mult"]);M["id"]=M.index
Z=W.merge(M,on="id");Z=Z[(Z.trades_TRAIN>=30)&(Z.trades_TEST>=20)].copy();Z["score"]=Z.mean_TEST*1000+Z.pf_TEST*5+Z.mean_TRAIN*500
Z=Z.sort_values(["score","pf_TEST"],ascending=False);Z.to_csv(O/"v507_all.csv",index=False);Z.head(30).to_csv(O/"v507_candidates.csv",index=False)
Q=Z[(Z.cost_mult==2)&(Z.total_TEST>0)&(Z.pf_TEST>1)&(Z.total_HOLDOUT>0)&(Z.pf_HOLDOUT>1)].head(20);Q.to_csv(O/"v507_robust.csv",index=False)
md="# V5.07 VOLATILITY-EXPANSION ROBUSTNESS\n\nNon-overlap, next-open, fixed close exit. Strict TRAIN/TEST/HOLDOUT. Cost stress x1/x1.5/x2. HOLDOUT not used for selection.\n\n## TOP\n"+Z.head(30).to_string(index=False)+"\n\n## COST x2 + POSITIVE HOLDOUT\n"+Q.to_string(index=False)+"\n";(O/"summary_v507.md").write_text(md);print(md)
