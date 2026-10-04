import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
CFG=[(th,h,tp,sl) for th in [1.5,1.75,2.0] for h in [24,48] for tp in [1.0,1.5,2.0] for sl in [1.0,1.5]]
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
def events(x):
 c,h,l=x.c,x.h,x.l;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();vx=atr/atr.rolling(50).mean();s=e50.pct_change(12);bull=(e50>e200)&(s>0);sig=np.where((vx>1.5)&(c>e20)&bull,1,0);return x,atr.values,sig
def eval_events(x,atr,sig,th,h,tp,sl,cost_mult):
 c=x.c.values;o=x.o.values;hi=x.h.values;lo=x.l.values;n=len(x);out=[];i=0
 # threshold-specific signal
 while i+h+1<n:
  if sig[i]<1 or atr[i]<=0 or np.isnan(atr[i]):i+=1;continue
  # reject unless actual vx threshold
  # signal array is base; recompute threshold via stored normalized unavailable, so caller supplies filtered sig
  e=o[i+1];a=atr[i];T=e+tp*a;S=e-sl*a;hit=None
  for j in range(i+1,min(n,i+1+h+1)):
   if hi[j]>=T and lo[j]<=S: hit=S;break
   if hi[j]>=T: hit=T;break
   if lo[j]<=S: hit=S;break
  if hit is None:hit=c[min(i+h,n-1)]
  out.append([x.index[i],hit/e-1-CUR*cost_mult]);i+=h+1
 return out
DATA={s:load(s) for s in SYM};rows=[]
folds=pd.date_range("2022-01-01","2026-01-01",freq="6MS",tz="UTC")
for te in folds:
 train0=te-pd.DateOffset(months=18);test1=te+pd.DateOffset(months=6)
 for cid,(th,h,tp,sl) in enumerate(CFG):
  rs=[]
  for s,x in DATA.items():
   if x.empty:continue
   c=x.c;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();vx=atr/atr.rolling(50).mean();slope=e50.pct_change(12);sg=np.where((vx>th)&(c>e20)&(e50>e200)&(slope>0),1,0);CUR=C[s]
   for mode,a,b in [("TRAIN",train0,te),("TEST",te,test1)]:
    mask=(x.index>=a)&(x.index<b);ii=np.where(mask)[0]
    if len(ii)<50:continue
    k=0
    while k<len(ii):
     i=ii[k]
     if i+h+1>=len(x) or sg[i]==0 or np.isnan(atr.iloc[i]): k+=1; continue
     e=x.o.iloc[i+1];T=e+tp*atr.iloc[i];S=e-sl*atr.iloc[i];hit=None
     for j in range(i+1,min(len(x),i+1+h+1)):
      if x.h.iloc[j]>=T and x.l.iloc[j]<=S:hit=S;break
      if x.h.iloc[j]>=T:hit=T;break
      if x.l.iloc[j]<=S:hit=S;break
     if hit is None:hit=x.c.iloc[min(i+h,len(x)-1)]
     rs.append([te,cid,mode,(hit/e-1)-CUR*3,s])
     k+=1
     while k<len(ii) and ii[k]<=i+h: k+=1
  rows+=rs
D=pd.DataFrame(rows,columns=["fold","id","period","net","symbol"])
def stat(g):
 r=g.net;w=r[r>0];l=r[r<0];return [len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan]
R=[]
for (f,cid,p),g in D.groupby(["fold","id","period"]):R.append([f,cid,p,*stat(g)])
R=pd.DataFrame(R,columns=["fold","id","period","trades","total","mean","win","pf"])
sel=[];oos=[]
for f,g in R.groupby("fold"):
 tr=g[g.period=="TRAIN"].query("trades>=20").sort_values(["mean","pf"],ascending=False)
 if tr.empty:continue
 best=int(tr.iloc[0].id);sel.append([f,best,*CFG[best]])
 z=g[(g.id==best)&(g.period=="TEST")];oos.append(z)
S=pd.DataFrame(sel,columns=["fold","id","threshold","h","tp_atr","sl_atr"]);Q=pd.concat(oos,ignore_index=True) if oos else pd.DataFrame()
SEL=D.merge(S[["fold","id"]],on=["fold","id"],how="inner");OOS=SEL[SEL.period=="TEST"].copy()
S.to_csv(O/"v510_selection.csv",index=False);R.to_csv(O/"v510_folds.csv",index=False);OOS.to_csv(O/"v510_oos.csv",index=False)
md="# V5.10 STRICT WALK-FORWARD\n\n18-month TRAIN selects threshold/horizon/ATR TP-SL; next 6-month TEST is untouched. Costs x3. Non-overlap. Long-only BULL volatility expansion.\n\n## SELECTION\n"+S.to_string(index=False)+"\n\n## OOS\n"+Q.to_string(index=False)+"\n\n## AGG OOS\n"+(str(stat(OOS)) if len(OOS) else "none")+"\n";(O/"summary_v510.md").write_text(md);print(md)
