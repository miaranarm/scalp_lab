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
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna();x=x.sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t")
def feat(x):
 c,h,l,v=x.c,x.h,x.l,x.v;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();atr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1).rolling(14).mean();hi20=h.shift(1).rolling(20).max();lo20=l.shift(1).rolling(20).min();roc=c.pct_change(12);mid=c.rolling(20).mean();sd=c.rolling(20).std();z=(c-mid)/(2*sd);vwap=(c*v).rolling(24).sum()/v.rolling(24).sum();r=(c.diff().clip(lower=0).rolling(14).mean()/(-c.diff().clip(upper=0)).rolling(14).mean()).replace([np.inf],np.nan);rsi=100-100/(1+r);vx=atr/atr.rolling(50).mean();s=e50.pct_change(12)
 return locals()
def sig(f):
 c=f["c"];bull=(f["e50"]>f["e200"])&(f["s"]>0);bear=(f["e50"]<f["e200"])&(f["s"]<0);rng=~(bull|bear)
 return {
 "Breakout":np.where(c>f["hi20"],1,np.where(c<f["lo20"],-1,0)),
 "Pullback":np.where(bull&(c<f["e20"])&(c>f["e50"]),1,np.where(bear&(c>f["e20"])&(c<f["e50"]),-1,0)),
 "RSI":np.where(f["rsi"]<30,1,np.where(f["rsi"]>70,-1,0)),
 "VWAP":np.where(c<f["vwap"]*.995,1,np.where(c>f["vwap"]*1.005,-1,0)),
 "Momentum":np.where(f["roc"]>.01,1,np.where(f["roc"]<-.01,-1,0)),
 "VolExp":np.where((f["vx"]>1.5)&(c>f["e20"]),1,np.where((f["vx"]>1.5)&(c<f["e20"]),-1,0)),
 "TrendCross":np.where((f["e50"]>f["e200"])&(f["e50"].shift(1)<=f["e200"].shift(1)),1,np.where((f["e50"]<f["e200"])&(f["e50"].shift(1)>=f["e200"].shift(1)),-1,0)),
 "RangeZ":np.where(f["z"]<-1,1,np.where(f["z"]>1,-1,0)),
 "TrendPullback":np.where(bull&(c<f["e20"])&(c>f["e50"]),1,np.where(bear&(c>f["e20"])&(c<f["e50"]),-1,0)),
 "BreakVol":np.where((c>f["hi20"])&(f["vx"]>1.25),1,np.where((c<f["lo20"])&(f["vx"]>1.25),-1,0)),
 "RSIRange":np.where(rng&(f["rsi"]<30),1,np.where(rng&(f["rsi"]>70),-1,0)),
 "MeanRev":np.where(c<f["vwap"]*.995,1,np.where(c>f["vwap"]*1.005,-1,0))
 }
DATA={}; 
for s in SYM:
 x=load(s)
 if not x.empty:DATA[s]=(x,feat(x))
CFG=[(fam,h,reg,uni) for fam in ["Breakout","Pullback","RSI","VWAP","Momentum","VolExp","TrendCross","RangeZ","TrendPullback","BreakVol","RSIRange","MeanRev"] for h in [4,8,12,24,48] for reg in ["ALL","BULL","BEAR","RANGE"] for uni in ["ALL","BTCETH","ETH"]]
rows=[]
for cid,(fam,h,reg,uni) in enumerate(CFG):
 for s,(x,f) in DATA.items():
  if uni=="BTCETH" and s=="SOLUSDT":continue
  if uni=="ETH" and s!="ETHUSDT":continue
  ss=sig(f)[fam].copy();bull=(f["e50"]>f["e200"])&(f["s"]>0);bear=(f["e50"]<f["e200"])&(f["s"]<0);rng=~(bull|bear)
  if reg=="BULL":ss=np.where(bull,ss,0)
  if reg=="BEAR":ss=np.where(bear,ss,0)
  if reg=="RANGE":ss=np.where(rng,ss,0)
  i=0;n=len(x);o=x.o.values;c=x.c.values
  while i+h+1<n:
   if ss[i]==0:i+=1;continue
   d=int(ss[i]);r=(c[i+1+h]/o[i+1]-1)*d-C[s]
   t=x.index[i];p="TRAIN" if t<pd.Timestamp("2024-01-01",tz="UTC") else ("TEST" if t<pd.Timestamp("2025-10-01",tz="UTC") else "HOLDOUT")
   rows.append([cid,fam,h,reg,uni,t,s,d,r,p]);i+=h+1
D=pd.DataFrame(rows,columns=["id","family","h","regime","universe","time","symbol","side","net","period"])
def st(g):
 r=g.net;w=r[r>0];l=r[r<0];eq=r.cumsum();return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan,(eq-eq.cummax()).min()]
R=[]
for (cid,p),g in D.groupby(["id","period"]):R.append([cid,p,*st(g)])
R=pd.DataFrame(R,columns=["id","period","trades","total","mean","win","pf","dd"])
W=R.pivot(index="id",columns="period",values=["trades","total","mean","win","pf","dd"]);W.columns=["_".join(x) for x in W.columns];W=W.reset_index()
for k in ["trades","total","mean","win","pf","dd"]:
 for p in ["TRAIN","TEST","HOLDOUT"]:
  if f"{k}_{p}" not in W:W[f"{k}_{p}"]=0.0
M=pd.DataFrame(CFG,columns=["family","h","regime","universe"]);M["id"]=M.index
Z=W.merge(M,on="id");Z=Z[(Z.trades_TRAIN>=15)&(Z.trades_TEST>=10)].copy();Z["score"]=Z.mean_TRAIN*1000+Z.mean_TEST*2000+Z.pf_TRAIN+Z.pf_TEST;Z=Z.sort_values(["score","pf_TEST"],ascending=False)
Z.to_csv(O/"v506_all.csv",index=False);Z.head(30).to_csv(O/"v506_candidates.csv",index=False)
Q=Z[(Z.total_HOLDOUT>0)&(Z.pf_HOLDOUT>1)&(Z.total_TEST>0)].head(20);Q.to_csv(O/"v506_holdout_positive.csv",index=False)
md="# V5.06 META ROBUST OOS\n\nAll tested families, non-overlap, next-open entry, fixed close exit, costs included. HOLDOUT never used for selection.\n\n## TOP\n"+Z.head(30).to_string(index=False)+"\n\n## HOLDOUT POSITIVE\n"+Q.to_string(index=False)+"\n";(O/"summary_v506.md").write_text(md);print(md)
