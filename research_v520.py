import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd

R=Path("results");R.mkdir(exist_ok=True)
A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC");H0=pd.Timestamp("2026-04-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];COSTS={"BTCUSDT":.0008,"ETHUSDT":.0009,"SOLUSDT":.0012}
FOLDS=pd.date_range("2022-01-01","2025-10-01",freq="6MS",tz="UTC")
FAST=[10,20,30];MID=[40,50];SLOW=[200];TOL=[0,.002];VOL=[0,1.0,1.2];ROC=[0,.001,.002]
TP=[.75,1,1.5];SL=[.75,1,1.5];MH=[4,8,12,24];COST=2.0

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except: pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0)
 x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t")

def stat(g):
 if len(g)==0:return (0,0.,0.,0.,np.nan)
 r=g.net;w=r[r>0];l=r[r<0]
 return len(r),float(r.sum()),float(r.mean()),float((r>0).mean()),float(w.sum()/abs(l.sum())) if len(l) else np.nan

def events(x,s):
 c,h,l,v=x.c,x.h,x.l,x.v
 out=[]
 for fast in FAST:
  ef=c.ewm(span=fast).mean()
  for mid in MID:
   em=c.ewm(span=mid).mean()
   for slow in SLOW:
    es=c.ewm(span=slow).mean(); vs=v/v.rolling(32).mean(); roc=c.pct_change(8)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean()
    bull=(em>es)&(em.pct_change(12)>0)&(ef>em)
    for tol in TOL:
     pull=(l<=ef*(1+tol))&(c>ef)&(c>em)
     for vm in VOL:
      for rc in ROC:
       sig=bull&pull&(vs>=vm)&(roc>=rc)
       for i in np.flatnonzero(sig):
        if i+25>=len(x) or not np.isfinite(atr.iloc[i]):continue
        out.append([x.index[i],s,fast,mid,slow,tol,vm,rc,float(atr.iloc[i]),float(x.o.iloc[i+1])])
 return out

E=[]
for s in SYM:
 x=load(s)
 if not x.empty:E+=events(x,s)
E=pd.DataFrame(E,columns=["time","symbol","fast","mid","slow","tol","volmin","rocmin","atr","entry"])
E.time=pd.to_datetime(E.time,utc=True)

def simulate(g,tp,sl,mh):
 rows=[]
 for r in g.itertuples():
  i=int(r.entry)
  if i<=0:continue
  # entry price and future candles are looked up from the symbol frame in precomputed map
  rows.append(r)
 return rows

# Re-load frames once and simulate each signal configuration without overlap.
FR={s:load(s) for s in SYM}
def trades(T,tp,sl,mh):
 out=[]
 for s,g in T.groupby("symbol"):
  x=FR[s]
  last=-mh
  for r in g.itertuples():
   i=x.index.get_indexer([r.time])[0]
   if i<=last or i+mh+1>=len(x):continue
   en=x.o.iloc[i+1];a=r.atr;ret=None
   for j in range(i+1,i+mh+2):
    if x.l.iloc[j]<=en-sl*a:ret=-sl*a/en;break
    if x.h.iloc[j]>=en+tp*a:ret=tp*a/en;break
   if ret is None:ret=x.c.iloc[i+mh+1]/en-1
   out.append([r.time,s,r.fast,r.mid,r.slow,r.tol,r.volmin,r.rocmin,tp,sl,mh,1,ret])
   last=i+mh
 return pd.DataFrame(out,columns=["time","symbol","fast","mid","slow","tol","volmin","rocmin","tp","sl","mh","side","gross"])

ALL=[]
for tp in TP:
 for sl in SL:
  for mh in MH: ALL.append(trades(E,tp,sl,mh))
E2=pd.concat(ALL,ignore_index=True) if ALL else pd.DataFrame(columns=["time","symbol","fast","mid","slow","tol","volmin","rocmin","tp","sl","mh","side","gross"])
E2["net"]=E2.gross-E2.symbol.map(COSTS)*COST

def choose(T,tr0,te):
 rows=[]
 a0=tr0;a1=tr0+pd.DateOffset(months=6);a2=tr0+pd.DateOffset(months=12)
 for key,g in T.groupby(["fast","mid","slow","tol","volmin","rocmin","tp","sl","mh"]):
  if len(g)<20:continue
  ps=[stat(g[(g.time>=a0)&(g.time<a1)]),stat(g[(g.time>=a1)&(g.time<a2)]),stat(g[(g.time>=a2)&(g.time<te)])]
  if all(p[0]>=3 for p in ps) and sum(p[2]>0 for p in ps)>=2:
   rows.append([*key,*stat(g),np.median([p[2] for p in ps]),min(p[2] for p in ps)])
 if not rows:return None
 r=pd.DataFrame(rows,columns=["fast","mid","slow","tol","volmin","rocmin","tp","sl","mh","trades","total","mean","win","pf","med","worst_slice"])
 r["score"]=r.med+r.worst_slice
 return r.sort_values(["score","med","pf","trades"],ascending=False).iloc[0]

sel=[];oos=[]
for te in FOLDS:
 tr0=te-pd.DateOffset(months=18);T=E2[(E2.time>=tr0)&(E2.time<te)]
 z=choose(T,tr0,te)
 if z is None:continue
 sel.append([te,*z.tolist()])
 a,b=te,te+pd.DateOffset(months=6)
 q=E2[(E2.time>=a)&(E2.time<b)&(E2.fast==z.fast)&(E2.mid==z.mid)&(E2.slow==z.slow)&(E2.tol==z.tol)&(E2.volmin==z.volmin)&(E2.rocmin==z.rocmin)&(E2.tp==z.tp)&(E2.sl==z.sl)&(E2.mh==z.mh)].copy()
 q["fold"]=te;oos.append(q)
O=pd.concat(oos,ignore_index=True) if oos else pd.DataFrame(columns=E2.columns)
S=pd.DataFrame(sel,columns=["fold","fast","mid","slow","tol","volmin","rocmin","tp","sl","mh","trades","train_total","train_mean","train_win","train_pf","med_slice_mean","worst_slice_mean","score"])
S.to_csv(R/"v520_selection.csv",index=False);O.to_csv(R/"v520_oos.csv",index=False)

P=E2[E2.time<H0]
z=choose(P,pd.Timestamp("2022-01-01",tz="UTC"),H0)
hold=pd.DataFrame(columns=E2.columns)
if z is not None:
 m=(E2.time>=H0)&(E2.fast==z.fast)&(E2.mid==z.mid)&(E2.slow==z.slow)&(E2.tol==z.tol)&(E2.volmin==z.volmin)&(E2.rocmin==z.rocmin)&(E2.tp==z.tp)&(E2.sl==z.sl)&(E2.mh==z.mh)
 hold=E2[m].copy()
pd.DataFrame([z.tolist()] if z is not None else [],columns=["fast","mid","slow","tol","volmin","rocmin","tp","sl","mh","trades","total","mean","win","pf","med","worst_slice","score"]).to_csv(R/"v520_final_selection.csv",index=False)
hold.to_csv(R/"v520_holdout.csv",index=False)

md="# V5.20 PULLBACK / TREND-PULLBACK\n\n18m TRAIN -> 6m OOS; long-only bullish EMA trend; pullback to fast EMA with re-entry; volume/ROC confirmations; 2x execution costs; non-overlap; next-open entry; ATR exits. Final holdout 2026-04->2026-10 is never used for selection.\n\n## OOS\n"+str(stat(O))+"\n\n## HOLDOUT\n"+str(stat(hold))+"\n"
if z is not None: md+="\n## FINAL TRAINED CANDIDATE\n"+str(z.to_dict())+"\n"
if len(O) and stat(O)[1]>0 and stat(O)[4]>=1: md+="\n## OOS POSITIVE\n"
else: md+="\n## NO OOS EDGE YET\n"
(R/"summary_v520.md").write_text(md);print(md)
