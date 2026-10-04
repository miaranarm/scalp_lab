import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC");H0=pd.Timestamp("2026-07-01",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0008,"ETHUSDT":.0009,"SOLUSDT":.0012};FOLDS=pd.date_range("2023-01-01","2026-01-01",freq="3MS",tz="UTC")
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates();x=x.apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
def stat(g):
 if len(g)==0:return(0,0,0,0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan
def run(x,sym):
 c,h,l,v=x.c,x.h,x.l,x.v;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min();vs=v/v.rolling(32).mean();r=(c.diff().clip(lower=0).rolling(14).mean()/(-c.diff().clip(upper=0)).rolling(14).mean());rsi=100-100/(1+r);bull=(e50>e200)&(e50.pct_change(12)>0);bear=(e50<e200)&(e50.pct_change(12)<0)
 sig={"Pullback":np.where(bull&(c<e20)&(c>e50)&(rsi<60),1,np.where(bear&(c>e20)&(c<e50)&(rsi>40),-1,0)),"Breakout":np.where((c>hi)&(vs>1.1),1,np.where((c<lo)&(vs>1.1),-1,0))}
 out=[]
 for fam,sg in sig.items():
  for tp in [0.75,1,1.5,2]:
   for sl in [0.75,1,1.5,2]:
    for mh in [4,8,12,24]:
     for side in [1,-1]:
      last=-mh
      for i in np.flatnonzero(sg==side):
       if i<=last or i+mh+1>=len(x) or not np.isfinite(atr.iloc[i]):continue
       en=x.o.iloc[i+1];a=atr.iloc[i];ret=None
       for j in range(i+1,i+mh+2):
        if side==1:
         if x.l.iloc[j]<=en-sl*a:ret=-sl*a/en;break
         if x.h.iloc[j]>=en+tp*a:ret=tp*a/en;break
        else:
         if x.h.iloc[j]>=en+sl*a:ret=-sl*a/en;break
         if x.l.iloc[j]<=en-tp*a:ret=tp*a/en;break
       if ret is None:ret=(x.c.iloc[i+mh+1]/en-1)*side
       out.append([x.index[i],sym,fam,tp,sl,mh,side,ret]);last=i+mh
 return out
E=[]
for s in SYM:
 x=load(s)
 if not x.empty:E+=run(x,s)
E=pd.DataFrame(E,columns=["time","symbol","family","tp","sl","mh","side","gross"]);E.time=pd.to_datetime(E.time,utc=True)
R=[];OOS=[]
for cost in [1.5,2.0]:
 T=E.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for te in FOLDS:
  tr0=te-pd.DateOffset(months=12);tr=T[(T.time>=tr0)&(T.time<te)];cand=[]
  for fam in ["Pullback","Breakout"]:
   for tp in [.75,1,1.5,2]:
    for sl in [.75,1,1.5,2]:
     for mh in [4,8,12,24]:
      for side in [1,-1]:
       g=tr[tr.family.eq(fam)&(tr.tp==tp)&(tr.sl==sl)&(tr.mh==mh)&tr.side.eq(side)]
       if len(g)<20:continue
       p=[stat(g[(g.time>=a)&(g.time<b)]) for a,b in [(tr0,tr0+pd.DateOffset(months=4)),(tr0+pd.DateOffset(months=4),tr0+pd.DateOffset(months=8)),(tr0+pd.DateOffset(months=8),te)]]
       med=np.median([q[2] for q in p]);R.append([cost,te,fam,tp,sl,mh,side,*stat(g),med])
       if np.isfinite(g.net.mean()) and stat(g)[4]>=1.0 and med>0:cand.append(R[-1])
  if cand:
   z=max(cand,key=lambda x:(x[-1],x[-2],x[7]));m=(E.time>=te)&(E.time<te+pd.DateOffset(months=3))&E.family.eq(z[2])&(E.tp==z[3])&(E.sl==z[4])&(E.mh==z[5])&E.side.eq(z[6]);oo=E[m].copy();oo["cost"]=cost;oo["net"]=oo.gross-oo.symbol.map(C)*cost;OOS.append(oo)
OOS=pd.concat(OOS,ignore_index=True) if OOS else pd.DataFrame();R=pd.DataFrame(R,columns=["cost","fold","family","tp","sl","mh","side","trades","total","mean","win","pf","med_slice_mean"])
P=E[E.time<H0].copy();best=[]
for cost in [1.5,2.0]:
 T=P.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for fam in ["Pullback","Breakout"]:
  for tp in [.75,1,1.5,2]:
   for sl in [.75,1,1.5,2]:
    for mh in [4,8,12,24]:
     for side in [1,-1]:
      g=T[T.family.eq(fam)&(T.tp==tp)&(T.sl==sl)&(T.mh==mh)&T.side.eq(side)]
      if len(g)<40:continue
      p=[stat(g[(g.time>=a)&(g.time<b)]) for a,b in [(pd.Timestamp("2024-01-01",tz="UTC"),pd.Timestamp("2025-01-01",tz="UTC")),(pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2026-01-01",tz="UTC")),(pd.Timestamp("2026-01-01",tz="UTC"),H0)]];med=np.median([q[2] for q in p])
      if stat(g)[4]>=1.0 and med>0:best.append([cost,fam,tp,sl,mh,side,*stat(g),med])
Bst=pd.DataFrame(best,columns=["cost","family","tp","sl","mh","side","trades","total","mean","win","pf","med_slice_mean"]);Bst=Bst.sort_values(["med_slice_mean","pf","trades"],ascending=False) if len(Bst) else Bst
if len(Bst):
 z=Bst.iloc[0];m=(E.time>=H0)&E.family.eq(z.family)&(E.tp==z.tp)&(E.sl==z.sl)&(E.mh==z.mh)&E.side.eq(z.side);hold=E[m].copy();hold["cost"]=z.cost;hold["net"]=hold.gross-hold.symbol.map(C)*z.cost
else:z=None;hold=pd.DataFrame()
R.to_csv(O/"v518_candidates.csv",index=False);OOS.to_csv(O/"v518_oos.csv",index=False);Bst.to_csv(O/"v518_final_selection.csv",index=False);hold.to_csv(O/"v518_holdout.csv",index=False)
md="# V5.18 ATR DISCOVERY\n\n12m TRAIN → 3m TEST, non-overlap, next-open entry, ATR exits. Discovery filter is deliberately broader; final holdout remains untouched.\n\n## OOS\n"+str(stat(OOS))+"\n\n## HOLDOUT\n"+str(stat(hold))+("\nChampion: "+str(z.to_dict()) if z is not None else "\nNO CHAMPION")+"\n";(O/"summary_v518.md").write_text(md);print(md)
