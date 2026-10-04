import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
CFG=[(1.5,48,"BULL","ALL"),(1.75,48,"BULL","ALL"),(1.5,48,"BULL","BTCETH"),(1.75,48,"BULL","BTCETH")]
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
def one(x,th,h,reg,uni,cm):
 c,o=x.c,x.o;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);vx=tr.rolling(14).mean()/tr.rolling(14).mean().rolling(50).mean();s=e50.pct_change(12);bull=(e50>e200)&(s>0);bear=(e50<e200)&(s<0);sg=np.where((vx>th)&(c>e20),1,np.where((vx>th)&(c<e20),-1,0));sg=np.where(bull,sg,0) if reg=="BULL" else np.where(bear,sg,0)
 out=[];i=0;n=len(x)
 while i+h+1<n:
  if sg[i]==0:i+=1;continue
  d=int(sg[i]);r=(c.iloc[i+1+h]/o.iloc[i+1]-1)*d-C[uni if uni in C else "BTCUSDT"]*cm
  # cost corrected per symbol below by rebuilding with symbol outside
  out.append([x.index[i],d,r]);i+=h+1
 return out
all=[]
for cid,(th,h,reg,uni) in enumerate(CFG):
 for s in SYM:
  if uni=="BTCETH" and s=="SOLUSDT":continue
  x=load(s)
  if x.empty:continue
  c,o=x.c,x.o;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);vx=tr.rolling(14).mean()/tr.rolling(14).mean().rolling(50).mean();sl=e50.pct_change(12);bull=(e50>e200)&(sl>0);sg=np.where((vx>th)&(c>e20),1,np.where((vx>th)&(c<e20),-1,0));sg=np.where(bull,sg,0);i=0;n=len(x)
  while i+h+1<n:
   if sg[i]==0:i+=1;continue
   d=int(sg[i]);entry=o.iloc[i+1];raw=(c.iloc[i+1+h]/entry-1)*d
   for cm in [2,3]:
    net=raw-C[s]*cm;t=x.index[i];p="TRAIN" if t<pd.Timestamp("2024-01-01",tz="UTC") else ("TEST" if t<pd.Timestamp("2025-10-01",tz="UTC") else "HOLDOUT");all.append([cid,t,s,net,p,cm])
   i+=h+1
D=pd.DataFrame(all,columns=["id","time","symbol","net","period","cost_mult"])
def metrics(g):
 r=g.net;w=r[r>0];l=r[r<0];eq=r.cumsum();dd=(eq-eq.cummax()).min();streak=cur=0
 for z in r:
  cur=cur+1 if z<0 else 0;streak=max(streak,cur)
 return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan,dd,streak]
rows=[]
for (cid,cm,p),g in D.groupby(["id","cost_mult","period"]):rows.append([cid,cm,p,*metrics(g)])
S=pd.DataFrame(rows,columns=["id","cost","period","trades","total","mean","win","pf","dd","loss_streak"])
ann=[]
for (cid,cm,y),g in D.assign(year=D.time.dt.year).groupby(["id","cost_mult","year"]):ann.append([cid,cm,y,*metrics(g)])
A1=pd.DataFrame(ann,columns=["id","cost","year","trades","total","mean","win","pf","dd","loss_streak"])
boot=[]
rng=np.random.default_rng(20261004)
for cid in range(len(CFG)):
 for cm in [2,3]:
  r=D[(D.id==cid)&(D.cost_mult==cm)&(D.period=="HOLDOUT")].net.values
  if len(r)<20:continue
  means=np.array([rng.choice(r,len(r),replace=True).mean() for _ in range(10000)])
  boot.append([cid,cm,len(r),r.mean(),np.quantile(means,.025),np.quantile(means,.975),(r.sum()>0)])
B1=pd.DataFrame(boot,columns=["id","cost","n","holdout_mean","boot_p025","boot_p975","positive_total"])
S.to_csv(O/"v508_periods.csv",index=False);A1.to_csv(O/"v508_years.csv",index=False);B1.to_csv(O/"v508_bootstrap.csv",index=False)
md="# V5.08 ROBUSTNESS AUDIT\n\nTop V507 candidates; cost x2/x3; annual stability; max loss streak; 10k bootstrap of HOLDOUT mean.\n\n## PERIODS\n"+S.to_string(index=False)+"\n\n## YEARS\n"+A1.to_string(index=False)+"\n\n## BOOTSTRAP\n"+B1.to_string(index=False)+"\n";(O/"summary_v508.md").write_text(md);print(md)
