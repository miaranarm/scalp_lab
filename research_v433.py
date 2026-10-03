import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC"); TH=[.20,.30,.40]; H=[1,3,6]
OUT=Path("results"); OUT.mkdir(exist_ok=True)
def months(a,b):
 x=pd.Timestamp(a.year,a.month,1,tz="UTC")
 while x<=b: yield x; x+=pd.offsets.MonthBegin(1)
def load(s):
 rows=[]
 for m in months(START,END):
  n=f"{s}-aggTrades-{m:%Y-%m}.zip"; p=f"/tmp/{n}"; u=f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{n}"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    a=[]
    for d in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000):
     d["t"]=pd.to_datetime(pd.to_numeric(d.t),unit="ms",utc=True); d["price"]=pd.to_numeric(d.price); d["qty"]=pd.to_numeric(d.qty); d["maker"]=pd.to_numeric(d.maker).astype(bool)
     d=d[(d.t>=START)&(d.t<END)]
     if len(d):
      d["bar5"]=d.t.dt.floor("5min"); d["buy"]=np.where(~d.maker,d.qty,0.); d["sell"]=np.where(d.maker,d.qty,0.)
      a.append(d.groupby("bar5").agg(buy=("buy","sum"),sell=("sell","sum"),trades=("id","count"),close=("price","last")))
   rows.append(pd.concat(a).groupby(level=0).agg({"buy":"sum","sell":"sum","trades":"sum","close":"last"})); os.remove(p); print("OK",n)
  except Exception as e: print("MISS",n,type(e).__name__)
 if not rows: raise RuntimeError(f"No data for {s}")
 d=pd.concat(rows).groupby(level=0).agg({"buy":"sum","sell":"sum","trades":"sum","close":"last"}).sort_index(); d["imb"]=(d.buy-d.sell)/(d.buy+d.sell).replace(0,np.nan)
 return d.reset_index(names="t")
def ev(d,th,h,fee):
 sig=np.where(d.imb>th,-1,np.where(d.imb<-th,1,0)); r=d.close.shift(-h)/d.close-1; x=pd.Series(sig)*r-fee; x=x[sig!=0].dropna()
 return (float(x.mean()),len(x),float(x.sum())) if len(x) else (np.nan,0,np.nan)
R=[]; S=[]
for s in SYM:
 d5=load(s)
 for iv in ["5m","15m"]:
  d=d5.copy()
  if iv=="15m":
   d=d.set_index("t").resample("15min").agg({"buy":"sum","sell":"sum","trades":"sum","close":"last"}).dropna().reset_index(); d["imb"]=(d.buy-d.sell)/(d.buy+d.sell).replace(0,np.nan)
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  scores={(t,h):ev(tr,t,h,F[s])[2] for t in TH for h in H}; t,h=max(scores,key=scores.get); tm=ev(te,t,h,F[s]); hm=ev(ho,t,h,F[s]); S.append([s,iv,t,h,scores[(t,h)],*tm,*hm])
  for name,x in [("TRAIN",tr),("TEST",te),("HOLDOUT",ho)]:
   for tt in TH:
    for hh in H: R.append([s,iv,name,tt,hh,*ev(x,tt,hh,F[s])])
q=pd.DataFrame(R,columns=["symbol","interval","period","threshold","horizon","mean","trades","total"]); s=pd.DataFrame(S,columns=["symbol","interval","threshold","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
q.to_csv(OUT/"v433_microstructure_matrix.csv",index=False); s.to_csv(OUT/"v433_holdout.csv",index=False)
Path(OUT/"summary_v433.md").write_text("# V4.33 — MICROSTRUCTURE / AGGRESSOR IMBALANCE\n\n"+s.to_string(index=False)+"\n",encoding="utf8"); print(s.to_string(index=False))