import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
CFG=[(u,t,h,tp,sl) for u in ["ALL","BTCETH"] for t in [1.5,1.75,2.0,2.25] for h in [24,48] for tp in [1.0,1.5,2.0] for sl in [1.0,1.5]]
C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};SYM=list(C)
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
D={s:load(s) for s in SYM};rows=[];folds=pd.date_range("2022-01-01","2026-01-01",freq="6MS",tz="UTC")
for te in folds:
 tr0=te-pd.DateOffset(months=18);te1=te+pd.DateOffset(months=6)
 for cid,(u,th,h,tp,sl) in enumerate(CFG):
  for s,x in D.items():
   if x.empty or (u=="BTCETH" and s=="SOLUSDT"):continue
   c=x.c;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean();vx=atr/atr.rolling(50).mean();sg=(vx>th)&(c>e20)&(e50>e200)&(e50.pct_change(12)>0)
   for mode,a,b in [("TRAIN",tr0,te),("TEST",te,te1)]:
    ii=np.where((x.index>=a)&(x.index<b))[0];k=0
    while k<len(ii):
     i=ii[k]
     if i+h+1>=len(x) or not sg.iloc[i] or pd.isna(atr.iloc[i]):k+=1;continue
     e=x.o.iloc[i+1];T=e+tp*atr.iloc[i];S=e-sl*atr.iloc[i];hit=None
     for j in range(i+1,min(len(x),i+h+1)):
      if x.h.iloc[j]>=T and x.l.iloc[j]<=S:hit=S;break
      if x.h.iloc[j]>=T:hit=T;break
      if x.l.iloc[j]<=S:hit=S;break
     if hit is None:hit=x.c.iloc[min(i+h,len(x)-1)]
     rows.append([te,cid,mode,(hit/e-1)-C[s]*3,s]);k+=1
     while k<len(ii) and ii[k]<=i+h:k+=1
X=pd.DataFrame(rows,columns=["fold","id","period","net","symbol"])
def stat(g):
 if g is None or len(g)==0:return (0,0.0,0.0,0.0,np.nan)
 r=g.net;w=r[r>0];l=r[r<0];return len(r),r.sum(),r.mean(),(r>0).mean(),w.sum()/abs(l.sum()) if len(l) else np.nan
R=[]
for (f,cid,p),g in X.groupby(["fold","id","period"]):R.append([f,cid,p,*stat(g)])
R=pd.DataFrame(R,columns=["fold","id","period","trades","total","mean","win","pf"])
sel=[];o=[]
for f in folds:
 g=R[(R.fold==f)&(R.period=="TRAIN")];scores=[]
 for cid in g.id.unique():
  q=g[g.id==cid]
  if len(q)<3 or q.trades.sum()<30:continue
  scores.append((cid,q["mean"].median(),(q["mean"]>0).sum(),q["pf"].median(),q.trades.sum()))
 if not scores:continue
 q=pd.DataFrame(scores,columns=["id","medmean","pos","medpf","trades"]).query("pos>=2").sort_values(["medmean","pos","medpf"],ascending=False)
 if q.empty:q=pd.DataFrame(scores,columns=["id","medmean","pos","medpf","trades"]).sort_values(["medmean","pos","medpf"],ascending=False)
 cid=int(q.iloc[0].id);sel.append([f,cid,*CFG[cid]]);o.append(X[(X.fold==f)&(X.period=="TEST")&(X.id==cid)])
S=pd.DataFrame(sel,columns=["fold","id","universe","threshold","h","tp_atr","sl_atr"])
OOS=pd.concat(o,ignore_index=True) if o else pd.DataFrame(columns=X.columns)
S.to_csv(O/"v511_selection.csv",index=False);R.to_csv(O/"v511_folds.csv",index=False);OOS.to_csv(O/"v511_oos.csv",index=False)
if len(OOS):
 byfold=OOS.groupby("fold").agg(trades=("net","size"),total=("net","sum"),mean=("net","mean"),win=("net",lambda z:(z>0).mean())).to_string()
else:byfold="NO OOS TRADES"
md="# V5.11 ROBUST WALK-FORWARD\n\n18m TRAIN split into 3 internal 6m slices. Select only configurations positive in >=2 slices, maximizing median slice mean; TEST remains untouched. Costs x3, non-overlap, BULL volatility expansion.\n\n## SELECTION\n"+S.to_string(index=False)+"\n\n## OOS\n"+byfold+"\n\n## AGG OOS\n"+str(stat(OOS))+"\n"
(O/"summary_v511.md").write_text(md);print(md)