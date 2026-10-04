import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd

O=Path("results");O.mkdir(exist_ok=True)
A=pd.Timestamp("2019-09-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
FAMS=["Pullback","Breakout_VolExp","Momentum","TrendFollowing","VolatilityExpansion","RangeTrading"];COSTS=[1.5,2.0];H=12
FOLDS=pd.date_range("2022-01-01","2025-10-01",freq="6MS",tz="UTC")

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t").apply(pd.to_numeric,errors="coerce").dropna()

def feat(x):
 c,h,l=x.c,x.h,x.l;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean()
 tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean()
 hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min();roc=c.pct_change(12)
 r=(c.diff().clip(lower=0).rolling(14).mean()/(-c.diff().clip(upper=0)).rolling(14).mean()).replace([np.inf],np.nan)
 rsi=100-100/(1+r);mid=c.rolling(20).mean();sd=c.rolling(20).std();z=(c-mid)/(2*sd);vx=atr/atr.rolling(50).mean();slope=e50.pct_change(12)
 bull=(e50>e200)&(slope>0);bear=(e50<e200)&(slope<0);return locals()

def signals(f):
 c,e20,e50,e200=f["c"],f["e20"],f["e50"],f["e200"]
 return {"Pullback":np.where((e50>e200)&(c<e20)&(c>e50),1,np.where((e50<e200)&(c>e20)&(c<e50),-1,0)),
 "Breakout_VolExp":np.where((c>f["hi"])&(f["vx"]>1.25),1,np.where((c<f["lo"])&(f["vx"]>1.25),-1,0)),
 "Momentum":np.where(f["roc"]>.01,1,np.where(f["roc"]<-.01,-1,0)),
 "TrendFollowing":np.where((e50>e200)&(e50.shift(1)<=e200.shift(1)),1,np.where((e50<e200)&(e50.shift(1)>=e200.shift(1)),-1,0)),
 "VolatilityExpansion":np.where((f["vx"]>1.5)&(c>e20),1,np.where((f["vx"]>1.5)&(c<e20),-1,0)),
 "RangeTrading":np.where(f["z"]<-1,1,np.where(f["z"]>1,-1,0))}

def regime(f,i):return "bull" if bool(f["bull"].iloc[i]) else ("bear" if bool(f["bear"].iloc[i]) else "range")
def events(x,f,sig,sym,fam):
 out=[];n=len(x)
 for i in np.flatnonzero(sig):
  if i+H>=n:continue
  side=int(sig[i]);entry=x.o.iloc[i+1];gross=(x.c.iloc[i+H]/entry-1)*side;out.append([x.index[i],sym,fam,side,regime(f,i),gross])
 return out
def stat(g):
 if len(g)==0:return (0,0,0,0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan

D={s:load(s) for s in SYM};E=[]
for s,x in D.items():
 if x.empty:continue
 f=feat(x)
 for fam,sg in signals(f).items():E+=events(x,f,sg,s,fam)
E=pd.DataFrame(E,columns=["time","symbol","family","side","regime","gross"]);E.time=pd.to_datetime(E.time,utc=True)

rows=[]
for cost in COSTS:
 T=E.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for te in FOLDS:
  tr0=te-pd.DateOffset(months=18);tr=T[(T.time>=tr0)&(T.time<te)]
  for fam in FAMS:
   for reg in ["bull","bear","range","ALL"]:
    for side in [1,-1,0]:
     g=tr[tr.family.eq(fam)&((tr.regime.eq(reg)) if reg!="ALL" else True)&((tr.side.eq(side)) if side else True)]
     if len(g)<40:continue
     parts=[]
     for a,b in [(tr0,tr0+pd.DateOffset(months=6)),(tr0+pd.DateOffset(months=6),tr0+pd.DateOffset(months=12)),(tr0+pd.DateOffset(months=12),te)]:
      q=g[(g.time>=a)&(g.time<b)]
      if len(q):parts.append(stat(q))
     if len(parts)==3 and sum(p[2]>0 for p in parts)>=2:rows.append([cost,te,fam,reg,side,*stat(g),np.median([p[2] for p in parts])])
R=pd.DataFrame(rows,columns=["cost","fold","family","regime","side","trades","total","mean","win","pf","med_slice_mean"])
sel=[];oos=[]
for cost in COSTS:
 for te in FOLDS:
  q=R[(R.cost==cost)&(R.fold==te)];q=q[(q.pf>=1.05)&(q.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False)
  if q.empty:continue
  z=q.iloc[0];sel.append(z.tolist());a=te;b=te+pd.DateOffset(months=6)
  m=(E.time>=a)&(E.time<b)&E.family.eq(z.family)&((E.regime.eq(z.regime)) if z.regime!="ALL" else True)&((E.side.eq(z.side)) if z.side else True)
  oo=E[m].copy();oo["cost"]=cost;oo["net"]=oo.gross-oo.symbol.map(C)*cost;oos.append(oo)
OOS=pd.concat(oos,ignore_index=True) if oos else pd.DataFrame()
pd.DataFrame(sel,columns=R.columns).to_csv(O/"v512_selection.csv",index=False);R.to_csv(O/"v512_candidates.csv",index=False);OOS.to_csv(O/"v512_oos.csv",index=False)

H0=pd.Timestamp("2026-04-01",tz="UTC");pre=E[E.time<H0].copy();best=[]
for cost in COSTS:
 P=pre.copy();P["net"]=P.gross-P.symbol.map(C)*cost
 for fam in FAMS:
  for reg in ["bull","bear","range","ALL"]:
   for side in [1,-1,0]:
    g=P[g.family.eq(fam)&((g.regime.eq(reg)) if reg!="ALL" else True)&((g.side.eq(side)) if side else True)] if False else P[P.family.eq(fam)&((P.regime.eq(reg)) if reg!="ALL" else True)&((P.side.eq(side)) if side else True)]
    if len(g)<60:continue
    parts=[]
    for a,b in [(pd.Timestamp("2021-10-01",tz="UTC"),pd.Timestamp("2022-10-01",tz="UTC")),(pd.Timestamp("2022-10-01",tz="UTC"),pd.Timestamp("2023-10-01",tz="UTC")),(pd.Timestamp("2023-10-01",tz="UTC"),pd.Timestamp("2024-04-01",tz="UTC")),(pd.Timestamp("2024-04-01",tz="UTC"),H0)]:
     q=g[(g.time>=a)&(g.time<b)]
     if len(q)>=10:parts.append(stat(q))
    if len(parts)>=3 and sum(p[2]>0 for p in parts)>=2:best.append([cost,fam,reg,side,*stat(g),np.median([p[2] for p in parts])])
B=pd.DataFrame(best,columns=["cost","family","regime","side","trades","total","mean","win","pf","med_slice_mean"])
B=B[(B.pf>=1.05)&(B.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False) if len(B) else B
if len(B):
 z=B.iloc[0];m=(E.time>=H0)&E.family.eq(z.family)&((E.regime.eq(z.regime)) if z.regime!="ALL" else True)&((E.side.eq(z.side)) if z.side else True);hold=E[m].copy();hold["cost"]=z.cost;hold["net"]=hold.gross-hold.symbol.map(C)*z.cost
else:z=None;hold=pd.DataFrame()
B.to_csv(O/"v512_final_selection.csv",index=False);hold.to_csv(O/"v512_holdout.csv",index=False)
md="# V5.12 META OOS — FAMILY × REGIME\n\nStrict 18m TRAIN → 6m TEST; next-open entry; fixed 12h outcome; costs 1.5x/2x. Final holdout 2026-04→2026-10 is never used for selection.\n\n## OOS\n"+str(stat(OOS))+"\n\n## HOLDOUT\n"+str(stat(hold))+("\nChampion: "+str(z.to_dict()) if z is not None else "\nNO CHAMPION")+"\n"
(O/"summary_v512.md").write_text(md);print(md)
