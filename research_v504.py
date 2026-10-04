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
   with zipfile.ZipFile(io.BytesIO(z)) as f:
    q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=[0,1,2,3,4,5]))
  except: pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates();x=x.apply(pd.to_numeric,errors="coerce").dropna();x=x.sort_values(x.columns[0])
 x=x.iloc[:,:6];x.columns=["t","o","h","l","c","v"]
 x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t").apply(pd.to_numeric,errors="coerce").dropna()

def feat(x):
 c,h,l=x.c,x.h,x.l
 e20=c.ewm(span=20).mean();e30=c.ewm(span=30).mean();e50=c.ewm(span=50).mean()
 e100=c.ewm(span=100).mean();e200=c.ewm(span=200).mean()
 tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
 atr=tr.rolling(14).mean();slope=e50.pct_change(12)
 return dict(c=c,h=h,l=l,e20=e20,e30=e30,e50=e50,e100=e100,e200=e200,atr=atr,slope=slope)

def signals(f,fast,slow,short_slope):
 c=f["c"];ef=f[fast];es=f[slow];sl=f["slope"]
 bull=(ef>es)&(sl>short_slope);bear=(ef<es)&(sl<-short_slope)
 long=bull&(c<f["e20"])&(c>ef)
 short=bear&(c>f["e20"])&(c<ef)
 return np.where(long,1,np.where(short,-1,0))

def trades(x,f,sig,h,tp,sl):
 out=[];n=len(x);c=x.c.values;hi=x.h.values;lo=x.l.values;atr=f["atr"].values
 i=0
 while i<n:
  if sig[i]==0 or i+h>=n or not np.isfinite(atr[i]) or atr[i]<=0: i+=1; continue
  d=int(sig[i]);entry=c[i];a=atr[i];pt=tp*a/entry;ps=sl*a/entry
  ret=0;exit_k=h;reason="time"
  for k in range(1,h+1):
   up=(hi[i+k]/entry-1)*d;dn=(lo[i+k]/entry-1)*d
   if up>=pt and dn<=-ps: ret=-ps;exit_k=k;reason="both";break
   if up>=pt: ret=pt;exit_k=k;reason="tp";break
   if dn<=-ps: ret=-ps;exit_k=k;reason="sl";break
  else: ret=(c[i+h]/entry-1)*d
  out.append([x.index[i],d,ret,exit_k,reason,((hi[i+1:i+h+1]/entry-1)*d).max(),((lo[i+1:i+h+1]/entry-1)*d).min()])
  i+=max(1,exit_k)
 return out

def stat(g):
 r=g.net;w=r[r>0];l=r[r<0]
 return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan,(r.cumsum()-r.cumsum().cummax()).min()]

DATA={}
for s in SYM:
 x=load(s)
 if not x.empty:DATA[s]=(x,feat(x))

CFG=[]
for fast in ["e50","e100"]:
 for slow in ["e100","e200"]:
  if fast==slow:continue
  for slope in [0,.0005,.001]:
   for h in [8,12,24]:
    for tp,sl in [(0.5,.5),(.75,.5),(1,.5),(.75,.75),(1,1),(1.5,1)]:
     for universe in ["ALL","BTCETH"]:
      for regime in ["ALL","BULL"]:
       CFG.append((fast,slow,slope,h,tp,sl,universe,regime))
rows=[];detail=[]
for ci,(fast,slow,slope,h,tp,sl,universe,regime) in enumerate(CFG):
 for s,(x,f) in DATA.items():
  if universe=="BTCETH" and s=="SOLUSDT":continue
  sg=signals(f,fast,slow,slope)
  if regime=="BULL":
   sg=np.where((sg==1)&(f["e50"]>f["e200"])&(f["slope"]>slope),1,0)
  for e in trades(x,f,sg,h,tp,sl):
   t,d,gross,ek,reason,mfe,mae=e;cost=C[s];net=gross-cost
   period="TRAIN" if t<pd.Timestamp("2024-01-01",tz="UTC") else ("TEST" if t<pd.Timestamp("2025-10-01",tz="UTC") else "HOLDOUT")
   rows.append([ci,fast,slow,slope,h,tp,sl,universe,regime,s,t,d,gross,net,ek,reason,mfe,mae,period])

D=pd.DataFrame(rows,columns=["id","fast","slow","slope","h","tp","sl","universe","regime","symbol","time","side","gross","net","bars","reason","mfe","mae","period"])
R=[]
for (ci,p),g in D.groupby(["id","period"]):
 q=stat(g);R.append([ci,p,*q])
R=pd.DataFrame(R,columns=["id","period","trades","total","mean","win","pf","dd"])
meta=pd.DataFrame(CFG,columns=["fast","slow","slope","h","tp","sl","universe","regime"]);meta["id"]=meta.index
wide=R.pivot(index="id",columns="period",values=["trades","total","mean","win","pf","dd"])
wide.columns=["_".join(x) for x in wide.columns];wide=wide.reset_index()
for col in ["trades","total","mean","win","pf","dd"]:
 for p in ["TRAIN","TEST","HOLDOUT"]:
  if f"{col}_{p}" not in wide: wide[f"{col}_{p}"]=0.0
wide=wide.merge(meta,on="id")
# Selection: train PF + mean, enough trades, then test confirmation; holdout untouched.
z=wide[(wide.trades_TRAIN>=25)&(wide.trades_TEST>=15)].copy()
z["score"]=z.pf_TRAIN.fillna(0)*z.mean_TRAIN.fillna(-9)*1000
z=z.sort_values(["score","pf_TRAIN"],ascending=False)
top=z.head(15)
top.to_csv(O/"v504_candidates.csv",index=False)
best=top.iloc[0] if len(top) else None
if best is not None:
 bid=int(best.id);bd=D[D.id==bid]
 out=bd.groupby("period").apply(lambda g:pd.Series(dict(trades=len(g),total=g.net.sum(),mean=g.net.mean(),win=(g.net>0).mean(),pf=(g.net[g.net>0].sum()/abs(g.net[g.net<0].sum())) if (g.net<0).any() else np.nan,dd=(g.net.cumsum()-g.net.cumsum().cummax()).min()))).reset_index()
 out.to_csv(O/"v504_selected.csv",index=False)
else: out=pd.DataFrame()
md="# V5.04 PULLBACK ROBUSTNESS\n\nStrict non-overlap, TP/SL path, TRAIN < 2024-01, TEST 2024-01→2025-09, untouched HOLDOUT from 2025-10. Costs included.\n\n## TOP CANDIDATES\n"+top.to_string(index=False)+"\n\n## SELECTED\n"+out.to_string(index=False)+"\n"
(O/"summary_v504.md").write_text(md);print("DATA_ROWS", {s:len(v[0]) for s,v in DATA.items()});print("TRADES",len(D));print(md)
