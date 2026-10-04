import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd

R=Path("results");R.mkdir(exist_ok=True)
A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
H0=pd.Timestamp("2026-04-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0008,"ETHUSDT":.0009,"SOLUSDT":.0012}
FOLDS=pd.date_range("2022-01-01","2025-10-01",freq="6MS",tz="UTC")
FAMS=["Pullback","Breakout","Momentum","MeanReversion"]
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except: pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates()
 x=x.apply(pd.to_numeric,errors="coerce").dropna().sort_values(0)
 x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t")
def stat(g):
 if len(g)==0:return (0,0.,0.,0.,np.nan)
 r=g.net;w=r[r>0];l=r[r<0]
 return len(r),float(r.sum()),float(r.mean()),float((r>0).mean()),float(w.sum()/abs(l.sum())) if len(l) else np.nan
def events(x,s):
 c,h,l,v=x.c,x.h,x.l,x.v
 e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean()
 tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
 atr=tr.rolling(14).mean();hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min()
 vs=v/v.rolling(32).mean();roc=c.pct_change(8);mid=c.rolling(20).mean();sd=c.rolling(20).std()
 z=(c-mid)/(2*sd);bull=(e50>e200)&(e50.pct_change(12)>0);bear=(e50<e200)&(e50.pct_change(12)<0)
 sig={
 "Pullback":np.where(bull&(c<e20)&(c>e50),1,np.where(bear&(c>e20)&(c<e50),-1,0)),
 "Breakout":np.where((c>hi)&(vs>1.1),1,np.where((c<lo)&(vs>1.1),-1,0)),
 "Momentum":np.where(roc>.01,1,np.where(roc<-.01,-1,0)),
 "MeanReversion":np.where(z<-1,1,np.where(z>1,-1,0))}
 out=[];H=[4,8,12,24];TP=[.75,1,1.5,2];SL=[.75,1,1.5,2]
 for fam,sg in sig.items():
  for tp in TP:
   for sl in SL:
    for mh in H:
     for side in (1,-1):
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
       out.append([x.index[i],s,fam,tp,sl,mh,side,float(ret)])
       last=i+mh
 return out

E=[]
for s in SYM:
 x=load(s)
 if not x.empty:E+=events(x,s)
E=pd.DataFrame(E,columns=["time","symbol","family","tp","sl","mh","side","gross"])
E.time=pd.to_datetime(E.time,utc=True)

def choose(T,tr0,te):
 rows=[]
 for fam in FAMS:
  for tp in [.75,1,1.5,2]:
   for sl in [.75,1,1.5,2]:
    for mh in [4,8,12,24]:
     for side in (1,-1):
      g=T[(T.family==fam)&(T.tp==tp)&(T.sl==sl)&(T.mh==mh)&(T.side==side)]
      if len(g)<20:continue
      ps=[stat(g[(g.time>=a)&(g.time<b)]) for a,b in [(tr0,tr0+pd.DateOffset(months=6)),(tr0+pd.DateOffset(months=6),tr0+pd.DateOffset(months=12)),(tr0+pd.DateOffset(months=12),te)]]
      if all(p[0]>=3 for p in ps) and sum(p[2]>0 for p in ps)>=2:
       rows.append([fam,tp,sl,mh,side,*stat(g),np.median([p[2] for p in ps])])
 if not rows:return None
 r=pd.DataFrame(rows,columns=["family","tp","sl","mh","side","trades","total","mean","win","pf","med"])
 r=r.sort_values(["med","pf","trades"],ascending=False)
 return r.iloc[0] if len(r) else None

COST=2.0;sel=[];oos=[]
for te in FOLDS:
 tr0=te-pd.DateOffset(months=18);T=E[(E.time>=tr0)&(E.time<te)].copy();T["net"]=T.gross-T.symbol.map(C)*COST
 z=choose(T,tr0,te)
 if z is None:continue
 sel.append([te,*z.tolist()])
 a,b=te,te+pd.DateOffset(months=6)
 m=(E.time>=a)&(E.time<b)&(E.family==z.family)&(E.tp==z.tp)&(E.sl==z.sl)&(E.mh==z.mh)&(E.side==z.side)
 q=E[m].copy();q["net"]=q.gross-q.symbol.map(C)*COST;q["fold"]=te;oos.append(q)

O=pd.concat(oos,ignore_index=True) if oos else pd.DataFrame()
S=pd.DataFrame(sel,columns=["fold","family","tp","sl","mh","side","trades","train_total","train_mean","train_win","train_pf","med_slice_mean"])
S.to_csv(R/"v520_selection.csv",index=False);O.to_csv(R/"v520_oos.csv",index=False)

P=E[E.time<H0].copy();P["net"]=P.gross-P.symbol.map(C)*COST
z=choose(P,pd.Timestamp("2022-01-01",tz="UTC"),H0)
if z is not None:
 m=(E.time>=H0)&(E.family==z.family)&(E.tp==z.tp)&(E.sl==z.sl)&(E.mh==z.mh)&(E.side==z.side)
 hold=E[m].copy();hold["net"]=hold.gross-hold.symbol.map(C)*COST
else:hold=pd.DataFrame()
if z is not None: pd.DataFrame([z.tolist()],columns=["family","tp","sl","mh","side","trades","total","mean","win","pf","med"]).to_csv(R/"v520_final_selection.csv",index=False)
hold.to_csv(R/"v520_holdout.csv",index=False)
md="# V5.20 ROBUST 15m META\n\n18m TRAIN -> 6m OOS, one cost scenario (2x), non-overlap, next-open entry, ATR exits. Final holdout 2026-04->2026-10 is never used for selection.\n\n## OOS\n"+str(stat(O))+"\n\n## HOLDOUT\n"+str(stat(hold))+"\n"
if z is not None and float(z.med)>0 and float(z.pf)>=1.0: md+="\n## CHAMPION\n"+str(z.to_dict())+"\n"
else: md+="\n## NO ROBUST CHAMPION\nTop candidate did not clear median-slice mean > 0 and PF >= 1.0.\n"
else: md+="\nNO CANDIDATE\n"
(R/"summary_v520.md").write_text(md);print(md)
