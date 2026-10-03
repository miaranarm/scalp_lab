import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path

SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
N=[12,24,48,96]; H=[1,3,6,12]; A=[.001,.002,.003,.004]
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC")
OUT=Path("results"); OUT.mkdir(exist_ok=True)

def load(s):
 rows=[]; m=START.normalize().replace(day=1)
 while m<=END:
  if m.month==END.month and m.year==END.year:
   ds=pd.date_range(m,END.normalize(),freq="D",tz="UTC")
   for d in ds: yieldfrom=1
  else: yieldfrom=0
  m+=pd.offsets.MonthBegin(1)
 for m in pd.date_range(START.normalize().replace(day=1),END.normalize().replace(day=1),freq="MS",tz="UTC"):
  if m.year==END.year and m.month==END.month:
   dates=pd.date_range(m,END.normalize(),freq="D",tz="UTC")
   urls=[f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip" for d in dates]
  else:
   urls=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"]
  for u in urls:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     q=[]
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000,low_memory=False):
      x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True)
      x["price"]=pd.to_numeric(x.price,errors="coerce")
      x=x.dropna(subset=["t","price"]); x=x[(x.t>=START)&(x.t<END)]
      if len(x):
       x["bar"]=x.t.dt.floor("5min")
       q.append(x.groupby("bar").price.agg(open="first",high="max",low="min",close="last"))
    if q: rows.append(pd.concat(q).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}))
    os.remove(p); print("OK",os.path.basename(u))
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not rows: raise RuntimeError("no data")
 return pd.concat(rows).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}).sort_index().reset_index(names="t")

def ev(d,n,h,a,fee):
 ema=d.close.ewm(span=n,adjust=False).mean(); z=(d.close-ema)/d.close.rolling(n).std()
 sig=np.where((d.close>ema)&(z>1),1,np.where((d.close<ema)&(z<-1),-1,0))
 r1=sig*(d.close.shift(-1)/d.close-1)
 rh=sig*(d.close.shift(-h)/d.close-1)
 stop=np.where(r1<=-a,r1,rh)
 x=pd.Series(stop,index=d.index)[sig!=0].dropna()-fee
 return (float(x.mean()),len(x),float(x.sum())) if len(x) else (np.nan,0,np.nan)

S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(n,h,a):ev(tr,n,h,a,F[s])[2] for n in N for h in H for a in A}; n,h,a=max(sc,key=sc.get)
  S.append([s,iv,n,h,a,sc[(n,h,a)],*ev(te,n,h,a,F[s]),*ev(ho,n,h,a,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","lookback","horizon","adverse_stop","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(OUT/"v440_holdout.csv",index=False)
(OUT/"summary_v440.md").write_text("# V4.40 — EMA ZSCORE + EARLY ADVERSE EXIT\n\n"+df.to_string(index=False)+"\n")
print(df.to_string(index=False))