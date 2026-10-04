import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd

O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0008,"ETHUSDT":.0009,"SOLUSDT":.0012}
FAMS=["Pullback","Breakout","MeanReversion","Momentum","VWAP"];HS=[4,8,12];COSTS=[1.5,2.0]
FOLDS=pd.date_range("2023-01-01","2026-01-01",freq="3MS",tz="UTC");H0=pd.Timestamp("2026-07-01",tz="UTC")

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip";z=urllib.request.urlopen(u,timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates();x=x.apply(pd.to_numeric,errors="coerce").dropna();x=x.sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t")

def feat(x):
 c,h,l,v=x.c,x.h,x.l,x.v; e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean()
 tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean()
 hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min();roc=c.pct_change(8);vs=v/v.rolling(32).mean()
 z=(c-c.rolling(32).mean())/(2*c.rolling(32).std());rvw=(c*v).rolling(32).sum()/v.rolling(32).sum()
 h1=x.resample("1h").agg({"c":"last"});he50=h1.c.ewm(span=50).mean();he200=h1.c.ewm(span=200).mean();hr=he50.pct_change(12)
 bull=((he50>he200)&(hr>0)).reindex(c.index,method="ffill");bear=((he50<he200)&(hr<0)).reindex(c.index,method="ffill");return locals()

def signals(f):
 c,e20,e50=f["c"],f["e20"],f["e50"]
 return {"Pullback":np.where((f["bull"])&(c<e20)&(c>e50),1,np.where((f["bear"])&(c>e20)&(c<e50),-1,0)),
 "Breakout":np.where((c>f["hi"])&(f["vs"]>1.2),1,np.where((c<f["lo"])&(f["vs"]>1.2),-1,0)),
 "MeanReversion":np.where((f["z"]<-1.5)&(~f["bull"]),1,np.where((f["z"]>1.5)&(~f["bear"]),-1,0)),
 "Momentum":np.where((f["roc"]>.008)&(f["vs"]>1),1,np.where((f["roc"]<-.008)&(f["vs"]>1),-1,0)),
 "VWAP":np.where((c>f["rvw"])&(c.shift(1)<=f["rvw"].shift(1))&f["bull"],1,np.where((c<f["rvw"])&(c.shift(1)>=f["rvw"].shift(1))&f["bear"],-1,0))}

def events(x,f,sig,sym,fam,H):
 out=[];last=-H
 for i in np.flatnonzero(sig):
  if i<=last or i+H>=len(x):continue
  side=int(sig[i]);entry=x.o.iloc[i+1];gross=(x.c.iloc[i+H]/entry-1)*side
  out.append([x.index[i],sym,fam,H,side,gross]);last=i+H
 return out

def stat(g):
 if len(g)==0:return (0,0,0,0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan

E=[]
for s in SYM:
 x=load(s)
 if x.empty:continue
 f=feat(x)
 for fam,sg in signals(f).items():
  for h in HS:E+=events(x,f,sg,s,fam,h)
E=pd.DataFrame(E,columns=["time","symbol","family","h","side","gross"]);E.time=pd.to_datetime(E.time,utc=True)

rows=[]
for cost in COSTS:
 T=E.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for te in FOLDS:
  tr0=te-pd.DateOffset(months=12);tr=T[(T.time>=tr0)&(T.time<te)]
  for fam in FAMS:
   for h in HS:
    for side in [1,-1]:
     g=tr[tr.family.eq(fam)&tr.h.eq(h)&tr.side.eq(side)]
     if len(g)<25:continue
     parts=[]
     for a,b in [(tr0,tr0+pd.DateOffset(months=4)),(tr0+pd.DateOffset(months=4),tr0+pd.DateOffset(months=8)),(tr0+pd.DateOffset(months=8),te)]:
      q=g[(g.time>=a)&(g.time<b)]
      if len(q):parts.append(stat(q))
     if len(parts)==3 and sum(p[2]>0 for p in parts)>=2:rows.append([cost,te,fam,h,side,*stat(g),np.median([p[2] for p in parts])])
R=pd.DataFrame(rows,columns=["cost","fold","family","h","side","trades","total","mean","win","pf","med_slice_mean"]);sel=[];oo=[]
for cost in COSTS:
 for te in FOLDS:
  q=R[(R.cost==cost)&(R.fold==te)];q=q[(q.pf>=1.05)&(q.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False)
  if q.empty:continue
  z=q.iloc[0];sel.append(z.tolist());m=(E.time>=te)&(E.time<te+pd.DateOffset(months=3))&E.family.eq(z.family)&E.h.eq(z.h)&E.side.eq(z.side)
  x=E[m].copy();x["cost"]=cost;x["net"]=x.gross-x.symbol.map(C)*cost;oo.append(x)
OOS=pd.concat(oo,ignore_index=True) if oo else pd.DataFrame()

pre=E[E.time<H0].copy();best=[]
for cost in COSTS:
 P=pre.copy();P["net"]=P.gross-P.symbol.map(C)*cost
 for fam in FAMS:
  for h in HS:
   for side in [1,-1]:
    g=P[P.family.eq(fam)&P.h.eq(h)&P.side.eq(side)]
    if len(g)<50:continue
    parts=[]
    for a,b in [(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2024-01-01",tz="UTC")),(pd.Timestamp("2024-01-01",tz="UTC"),pd.Timestamp("2025-01-01",tz="UTC")),(pd.Timestamp("2025-01-01",tz="UTC"),H0)]:
     q=g[(g.time>=a)&(g.time<b)]
     if len(q)>=10:parts.append(stat(q))
    if len(parts)==3 and sum(p[2]>0 for p in parts)>=2:best.append([cost,fam,h,side,*stat(g),np.median([p[2] for p in parts])])
B=pd.DataFrame(best,columns=["cost","family","h","side","trades","total","mean","win","pf","med_slice_mean"]);B=B[(B.pf>=1.05)&(B.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False) if len(B) else B
if len(B):
 z=B.iloc[0];m=(E.time>=H0)&E.family.eq(z.family)&E.h.eq(z.h)&E.side.eq(z.side);hold=E[m].copy();hold["cost"]=z.cost;hold["net"]=hold.gross-hold.symbol.map(C)*z.cost
else:z=None;hold=pd.DataFrame()

pd.DataFrame(sel,columns=R.columns).to_csv(O/"v514_selection.csv",index=False);R.to_csv(O/"v514_candidates.csv",index=False);OOS.to_csv(O/"v514_oos.csv",index=False);B.to_csv(O/"v514_final_selection.csv",index=False);hold.to_csv(O/"v514_holdout.csv",index=False)
md="# V5.14 15m SCALP META OOS\n\nStrict 12m TRAIN → 3m TEST, next-open entry, non-overlap, 1h regime, horizons 1h/2h/3h, costs 1.5x/2x. Final holdout 2026-07→2026-10 untouched.\n\n## OOS\n"+str(stat(OOS))+"\n\n## HOLDOUT\n"+str(stat(hold))+("\nChampion: "+str(z.to_dict()) if z is not None else "\nNO CHAMPION")+"\n"
(O/"summary_v514.md").write_text(md);print(md)
