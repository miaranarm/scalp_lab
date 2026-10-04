import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC");CUT=pd.Timestamp("2026-08-20",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};H=4
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1];urllib.request.urlretrieve(u,p)
  with zipfile.ZipFile(p) as z:
   x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,2,3,4]);x.columns=["t","h","l","c"];q.append(x)
  Path(p).unlink(missing_ok=True)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),**{k:lambda x,k=k:x[k].astype(float) for k in "hlc"}).drop_duplicates("t").sort_values("t")
def trades(d):
 x=d.set_index("t");atr=(x.h-x.l).rolling(24).mean();r=x.c.pct_change();s=np.where(r>2*atr/x.c.shift(1),-1,np.where(r<-2*atr/x.c.shift(1),1,0));a=[];i=24
 while i+H+1<len(x):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(x.c.iloc[ex]/x.c.iloc[en]-1));i=ex
 return np.array(a)
rows=[];allg=[]
for s in SYM:
 z=trades(load(s).set_index("t") if False else load(s)[lambda x:x.t>=CUT]);allg.extend(z)
 for mult in [1,1.25,1.5,2]:
  rows.append([s,mult,z.sum()-len(z)*C[s]*mult,len(z)])
df=pd.DataFrame(rows,columns=["symbol","cost_mult","net","trades"]);g=df.groupby("cost_mult").net.sum()
rng=np.random.default_rng(20261004);a=np.array(allg);base=np.mean(a)-np.mean([C[s] for s in SYM]);mc=np.array([rng.choice(a,len(a),replace=True).sum()-len(a)*np.mean([C[s] for s in SYM]) for _ in range(5000)])
(O/"v478_stress.csv").write_text(df.to_csv(index=False));(O/"summary_v478.md").write_text("# V4.78 — HOLDOUT COST STRESS + MC\n\n"+df.to_string(index=False)+f"\n\nTOTAL_BY_MULT\n{g}\n\nMC_P_POSITIVE {(mc>0).mean():.4f}\nMC_P05 {np.percentile(mc,5):.6f}\nMC_MEDIAN {np.median(mc):.6f}\nMC_P95 {np.percentile(mc,95):.6f}");print(df.to_string(index=False),"\n",g,"\nMC P>0",(mc>0).mean(),"P05",np.percentile(mc,5),"MED",np.median(mc))