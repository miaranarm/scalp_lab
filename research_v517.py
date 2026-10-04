import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC");H0=pd.Timestamp("2026-07-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};FAMS=["Pullback","Breakout_VolExp","Momentum","TrendFollowing","VolatilityExpansion","RangeTrading"];HS=[6,12,24]
FOLDS=pd.date_range("2023-01-01","2026-01-01",freq="3MS",tz="UTC")
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates();x=x.apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
def feat(x):
 c,h,l,v=x.c,x.h,x.l,x.v;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min();roc=c.pct_change(12);vs=v/v.rolling(20).mean();z=(c-c.rolling(20).mean())/(2*c.rolling(20).std());s=e50.pct_change(12);bull=(e50>e200)&(s>0);bear=(e50<e200)&(s<0);return locals()
def signals(f):
 c,e20,e50,e200=f["c"],f["e20"],f["e50"],f["e200"]
 return {"Pullback":np.where((e50>e200)&(c<e20)&(c>e50),1,np.where((e50<e200)&(c>e20)&(c<e50),-1,0)),"Breakout_VolExp":np.where((c>f["hi"])&(f["vs"]>1.25),1,np.where((c<f["lo"])&(f["vs"]>1.25),-1,0)),"Momentum":np.where(f["roc"]>.01,1,np.where(f["roc"]<-.01,-1,0)),"TrendFollowing":np.where((e50>e200)&(e50.shift(1)<=e200.shift(1)),1,np.where((e50<e200)&(e50.shift(1)>=e200.shift(1)),-1,0)),"VolatilityExpansion":np.where((f["atr"]/f["atr"].rolling(50).mean()>1.5)&(c>e20),1,np.where((f["atr"]/f["atr"].rolling(50).mean()>1.5)&(c<e20),-1,0)),"RangeTrading":np.where(f["z"]<-1,1,np.where(f["z"]>1,-1,0))}
def events(x,sg,sym,fam,h):
 out=[];last=-h
 for i in np.flatnonzero(sg):
  if i<=last or i+1+h>=len(x):continue
  side=int(sg[i]);en=x.o.iloc[i+1];gross=(x.c.iloc[i+1+h]/en-1)*side;out.append([x.index[i],sym,fam,h,side,gross]);last=i+h
 return out
def stat(g):
 if len(g)==0:return(0,0,0,0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan
E=[]
for s in SYM:
 x=load(s)
 if x.empty:continue
 f=feat(x)
 for fam,sg in signals(f).items():
  for h in HS:E+=events(x,sg,s,fam,h)
E=pd.DataFrame(E,columns=["time","symbol","family","h","side","gross"]);E.time=pd.to_datetime(E.time,utc=True)
R=[];OOS=[]
for cost in [1.5,2.0]:
 T=E.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for te in FOLDS:
  tr0=te-pd.DateOffset(months=6);tr=T[(T.time>=tr0)&(T.time<te)]
  cand=[]
  for fam in FAMS:
   for h in HS:
    for side in [1,-1]:
     g=tr[tr.family.eq(fam)&(tr.h==h)&(tr.side==side)]
     if len(g)<20:continue
     p=[]
     for a,b in [(tr0,tr0+pd.DateOffset(months=2)),(tr0+pd.DateOffset(months=2),tr0+pd.DateOffset(months=4)),(tr0+pd.DateOffset(months=4),te)]:
      q=g[(g.time>=a)&(g.time<b)]
      if len(q):p.append(stat(q))
     if len(p)==3 and sum(x[2]>0 for x in p)>=2:
      cand.append([cost,te,fam,h,side,*stat(g),np.median([x[2] for x in p])])
  R+=cand
  if cand:
   z=max([x for x in cand if x[8]>0 and x[9]>=1.0],key=lambda x:(x[10],x[9],x[5]),default=None)
   if z:
    m=(E.time>=te)&(E.time<te+pd.DateOffset(months=3))&E.family.eq(z[2])&(E.h==z[3])&E.side.eq(z[4]);oo=E[m].copy();oo["cost"]=cost;oo["net"]=oo.gross-oo.symbol.map(C)*cost;OOS.append(oo)
R=pd.DataFrame(R,columns=["cost","fold","family","h","side","trades","total","mean","win","pf","med_slice_mean"]);OOS=pd.concat(OOS,ignore_index=True) if OOS else pd.DataFrame()
P=E[E.time<H0].copy();best=[]
for cost in [1.5,2.0]:
 T=P.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for fam in FAMS:
  for h in HS:
   for side in [1,-1]:
    g=T[T.family.eq(fam)&(T.h==h)&T.side.eq(side)]
    if len(g)<30:continue
    p=[]
    for a,b in [(pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-03-01",tz="UTC")),(pd.Timestamp("2025-03-01",tz="UTC"),pd.Timestamp("2025-05-01",tz="UTC")),(pd.Timestamp("2025-05-01",tz="UTC"),H0)]:
     q=g[(g.time>=a)&(g.time<b)]
     if len(q)>=8:p.append(stat(q))
    if len(p)==3 and sum(x[2]>0 for x in p)>=2:best.append([cost,fam,h,side,*stat(g),np.median([x[2] for x in p])])
Bst=pd.DataFrame(best,columns=["cost","family","h","side","trades","total","mean","win","pf","med_slice_mean"]);Bst=Bst[(Bst.pf>=1.0)&(Bst.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False) if len(Bst) else Bst
if len(Bst):
 z=Bst.iloc[0];m=(E.time>=H0)&E.family.eq(z.family)&(E.h==z.h)&E.side.eq(z.side);hold=E[m].copy();hold["cost"]=z.cost;hold["net"]=hold.gross-hold.symbol.map(C)*z.cost
else:z=None;hold=pd.DataFrame()
pd.DataFrame(R).to_csv(O/"v517_candidates.csv",index=False);OOS.to_csv(O/"v517_oos.csv",index=False);Bst.to_csv(O/"v517_final_selection.csv",index=False);hold.to_csv(O/"v517_holdout.csv",index=False)
md="# V5.17 ADAPTIVE 1h META OOS\n\n6m TRAIN → 3m TEST, non-overlap, horizons 6/12/24h, costs 1.5x/2x. Final holdout 2026-07→2026-10 untouched.\n\n## OOS\n"+str(stat(OOS))+"\n\n## HOLDOUT\n"+str(stat(hold))+("\nChampion: "+str(z.to_dict()) if z is not None else "\nNO CHAMPION")+"\n"
(O/"summary_v517.md").write_text(md);print(md)
