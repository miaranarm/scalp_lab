import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC");H0=pd.Timestamp("2026-07-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0008,"ETHUSDT":.0009,"SOLUSDT":.0012}
CFG=[(fam,tp,sl,mh,side,cost) for fam in ["PullbackATR","BreakoutATR"] for tp in [1.0,1.5,2.0] for sl in [1.0,1.5] for mh in [8,12,24] for side in [1,-1] for cost in [1.5,2.0]]
FOLDS=pd.date_range("2023-01-01","2026-01-01",freq="3MS",tz="UTC")

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip";z=urllib.request.urlopen(u,timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates();x=x.apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")

def feat(x):
 c,h,l,v=x.c,x.h,x.l,x.v;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();hi=h.shift(1).rolling(20).max();lo=l.shift(1).rolling(20).min();r=(c.diff().clip(lower=0).rolling(14).mean()/(-c.diff().clip(upper=0)).rolling(14).mean());rsi=100-100/(1+r);vs=v/v.rolling(32).mean();h1=x.resample("1h").c.last();e1=h1.ewm(span=50).mean();e2=h1.ewm(span=200).mean();s=e1.pct_change(12);bull=((e1>e2)&(s>0)).reindex(c.index,method="ffill");bear=((e1<e2)&(s<0)).reindex(c.index,method="ffill");return locals()

def sigs(f):
 c,e20,e50=f["c"],f["e20"],f["e50"];return {"PullbackATR":np.where(f["bull"]&(c<e20)&(c>e50)&(f["rsi"]<55),1,np.where(f["bear"]&(c>e20)&(c<e50)&(f["rsi"]>45),-1,0)),"BreakoutATR":np.where((c>f["hi"])&(f["vs"]>1.2)&f["bull"],1,np.where((c<f["lo"])&(f["vs"]>1.2)&f["bear"],-1,0))}

def run(x,f,sig,sym,fam,tp,sl,mh,side):
 out=[];last=-mh
 for i in np.flatnonzero(sig==side):
  if i<=last or i+1>=len(x):continue
  en=x.o.iloc[i+1];a=f["atr"].iloc[i];entry=i+1;hit=None
  if not np.isfinite(a) or a<=0 or entry+mh>=len(x):continue
  for j in range(entry,entry+mh+1):
   hi,lo=x.h.iloc[j],x.l.iloc[j]
   if side==1:
    if lo<=en-sl*a:hit=-sl*a/en;break
    if hi>=en+tp*a:hit=tp*a/en;break
   else:
    if hi>=en+sl*a:hit=-sl*a/en;break
    if lo<=en-tp*a:hit=tp*a/en;break
  if hit is None:hit=(x.c.iloc[entry+mh]/en-1)*side
  out.append([x.index[i],sym,fam,tp,sl,mh,side,hit]);last=j
 return out

E=[]
for s in SYM:
 x=load(s)
 if x.empty:continue
 f=feat(x)
 for fam,sg in sigs(f).items():
  for tp,sl,mh in [(a,b,c) for a in [1,1.5,2] for b in [1,1.5] for c in [8,12,24]]:
   for side in [1,-1]:E+=run(x,f,sg,s,fam,tp,sl,mh,side)
E=pd.DataFrame(E,columns=["time","symbol","family","tp","sl","mh","side","gross"]);E.time=pd.to_datetime(E.time,utc=True)

def stat(g):
 if len(g)==0:return (0,0,0,0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan

rows=[];seen=set()
for cost in [1.5,2.0]:
 T=E.copy();T["net"]=T.gross-T.symbol.map(C)*cost
 for te in FOLDS:
  tr0=te-pd.DateOffset(months=12);tr=T[(T.time>=tr0)&(T.time<te)]
  for fam in ["PullbackATR","BreakoutATR"]:
   for tp in [1,1.5,2]:
    for sl in [1,1.5]:
     for mh in [8,12,24]:
      for side in [1,-1]:
       g=tr[tr.family.eq(fam)&(tr.tp==tp)&(tr.sl==sl)&(tr.mh==mh)&(tr.side==side)]
       if len(g)<25:continue
       p=[]
       for a,b in [(tr0,tr0+pd.DateOffset(months=4)),(tr0+pd.DateOffset(months=4),tr0+pd.DateOffset(months=8)),(tr0+pd.DateOffset(months=8),te)]:
        q=g[(g.time>=a)&(g.time<b)]
        if len(q):p.append(stat(q))
       if len(p)==3 and sum(x[2]>0 for x in p)>=2:rows.append([cost,te,fam,tp,sl,mh,side,*stat(g),np.median([x[2] for x in p])])
R=pd.DataFrame(rows,columns=["cost","fold","family","tp","sl","mh","side","trades","total","mean","win","pf","med_slice_mean"]);sel=[];oo=[]
for cost in [1.5,2.0]:
 for te in FOLDS:
  q=R[(R.cost==cost)&(R.fold==te)];q=q[(q.pf>=1.05)&(q.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False)
  if q.empty:continue
  z=q.iloc[0];sel.append(z.tolist());m=(E.time>=te)&(E.time<te+pd.DateOffset(months=3))&E.family.eq(z.family)&(E.tp==z.tp)&(E.sl==z.sl)&(E.mh==z.mh)&E.side.eq(z.side);x=E[m].copy();x["cost"]=cost;x["net"]=x.gross-x.symbol.map(C)*cost;oo.append(x)
OOS=pd.concat(oo,ignore_index=True) if oo else pd.DataFrame()

pre=E[E.time<H0].copy();best=[]
for cost in [1.5,2.0]:
 P=pre.copy();P["net"]=P.gross-P.symbol.map(C)*cost
 for fam in ["PullbackATR","BreakoutATR"]:
  for tp in [1,1.5,2]:
   for sl in [1,1.5]:
    for mh in [8,12,24]:
     for side in [1,-1]:
      g=P[P.family.eq(fam)&(P.tp==tp)&(P.sl==sl)&(P.mh==mh)&P.side.eq(side)]
      if len(g)<40:continue
      p=[]
      for a,b in [(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2024-01-01",tz="UTC")),(pd.Timestamp("2024-01-01",tz="UTC"),pd.Timestamp("2025-01-01",tz="UTC")),(pd.Timestamp("2025-01-01",tz="UTC"),H0)]:
       q=g[(g.time>=a)&(g.time<b)]
       if len(q)>=10:p.append(stat(q))
      if len(p)==3 and sum(x[2]>0 for x in p)>=2:best.append([cost,fam,tp,sl,mh,side,*stat(g),np.median([x[2] for x in p])])
B=pd.DataFrame(best,columns=["cost","family","tp","sl","mh","side","trades","total","mean","win","pf","med_slice_mean"]);B=B[(B.pf>=1.05)&(B.med_slice_mean>0)].sort_values(["med_slice_mean","pf","trades"],ascending=False) if len(B) else B
if len(B):
 z=B.iloc[0];m=(E.time>=H0)&E.family.eq(z.family)&(E.tp==z.tp)&(E.sl==z.sl)&(E.mh==z.mh)&E.side.eq(z.side);hold=E[m].copy();hold["cost"]=z.cost;hold["net"]=hold.gross-hold.symbol.map(C)*z.cost
else:z=None;hold=pd.DataFrame()
pd.DataFrame(sel,columns=R.columns).to_csv(O/"v516_selection.csv",index=False);R.to_csv(O/"v516_candidates.csv",index=False);OOS.to_csv(O/"v516_oos.csv",index=False);B.to_csv(O/"v516_final_selection.csv",index=False);hold.to_csv(O/"v516_holdout.csv",index=False)
md="# V5.16 15m ATR EXIT META OOS\n\nStrict 12m TRAIN → 3m TEST; next-open entry; non-overlap; 1h regime; ATR TP/SL; costs 1.5x/2x. Final holdout 2026-07→2026-10 untouched.\n\n## OOS\n"+str(stat(OOS))+"\n\n## HOLDOUT\n"+str(stat(hold))+("\nChampion: "+str(z.to_dict()) if z is not None else "\nNO CHAMPION")+"\n"
(O/"summary_v516.md").write_text(md);print(md)
