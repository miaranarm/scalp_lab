import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True)
A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   z=urllib.request.urlopen(u,timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=[0,1,2,3,4,5]))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna()
 x=x.sort_values(x.columns[0]);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t")
def feat(x):
 c=x.c;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e100=c.ewm(span=100).mean();e200=c.ewm(span=200).mean();s=e50.pct_change(12)
 return {"c":c,"o":x.o,"e20":e20,"e50":e50,"e100":e100,"e200":e200,"s":s}
def sig(f,fast,slow,slope):
 c=f["c"];ef=f[fast];es=f[slow];s=f["s"]
 bull=(ef>es)&(s>slope);bear=(ef<es)&(s<-slope)
 long=bull&(c<f["e20"])&(c>ef);short=bear&(c>f["e20"])&(c<ef)
 return np.where(long,1,np.where(short,-1,0))
def run(x,f,sg,h):
 out=[];i=0;n=len(x);o=x.o.values;c=x.c.values
 while i+h+1<n:
  if sg[i]==0:i+=1;continue
  d=int(sg[i]);entry=o[i+1]
  ret=(c[i+1+h]/entry-1)*d-CURC
  out.append([x.index[i],d,ret])
  i+=h+1
 return out
CFG=[]
for fast,slow in [("e50","e200"),("e50","e100"),("e20","e50")]:
 for slope in [0,.0005,.001]:
  for h in [8,12,24,48]:
   for uni in ["ALL","BTCETH","ETH"]:
    for reg in ["ALL","BULL"]:
     CFG.append((fast,slow,slope,h,uni,reg))
DATA={s:(x,feat(x)) for s in SYM if not (x:=load(s)).empty}
rows=[]
for cid,(fast,slow,slope,h,uni,reg) in enumerate(CFG):
 for s,(x,f) in DATA.items():
  if uni=="BTCETH" and s=="SOLUSDT":continue
  if uni=="ETH" and s!="ETHUSDT":continue
  global CURC;CURC=C[s]
  sg=sig(f,fast,slow,slope)
  if reg=="BULL":sg=np.where((sg==1)&(f["e50"]>f["e200"])&(f["s"]>slope),1,0)
  for t,d,r in run(x,f,sg,h):
   p="TRAIN" if t<pd.Timestamp("2024-01-01",tz="UTC") else ("TEST" if t<pd.Timestamp("2025-10-01",tz="UTC") else "HOLDOUT")
   rows.append([cid,t,s,d,r,p])
D=pd.DataFrame(rows,columns=["id","time","symbol","side","net","period"])
def st(g):
 r=g.net;w=r[r>0];l=r[r<0];eq=r.cumsum();dd=(eq-eq.cummax()).min()
 return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan,dd]
R=[]
for (cid,p),g in D.groupby(["id","period"]):R.append([cid,p,*st(g)])
R=pd.DataFrame(R,columns=["id","period","trades","total","mean","win","pf","dd"])
W=R.pivot(index="id",columns="period",values=["trades","total","mean","win","pf","dd"]);W.columns=["_".join(x) for x in W.columns];W=W.reset_index()
for k in ["trades","total","mean","win","pf","dd"]:
 for p in ["TRAIN","TEST","HOLDOUT"]:
  if f"{k}_{p}" not in W:W[f"{k}_{p}"]=0.0
M=pd.DataFrame(CFG,columns=["fast","slow","slope","h","universe","regime"]);M["id"]=M.index
Z=W[(W.trades_TRAIN>=20)&(W.trades_TEST>=10)].merge(M,on="id")
Z["score"]=Z.mean_TRAIN*1000+Z.mean_TEST*2000+Z.pf_TRAIN+Z.pf_TEST
Z=Z.sort_values(["score","pf_TEST"],ascending=False).head(20)
Z.to_csv(O/"v505_candidates.csv",index=False)
if len(Z):
 b=int(Z.iloc[0].id);S=R[R.id==b];S.to_csv(O/"v505_selected.csv",index=False)
else:S=pd.DataFrame()
md="# V5.05 PULLBACK OOS AUDIT\n\nNon-overlap, next-open entry, fixed close exit, costs included. TRAIN < 2024-01; TEST 2024-01→2025-09; untouched HOLDOUT from 2025-10.\n\n## TOP\n"+Z.to_string(index=False)+"\n\n## SELECTED\n"+S.to_string(index=False)+"\n"
(O/"summary_v505.md").write_text(md);print(md)
