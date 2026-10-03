import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
N=[12,24,48,96]; H=[1,3,6,12]; C=[0,.0005,.001,.002,.003]
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC"); OUT=Path("results"); OUT.mkdir(exist_ok=True)

def load(s):
 rows=[]
 for m in pd.date_range(START.replace(day=1),END.replace(day=1),freq="MS",tz="UTC"):
  us=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"] if m<END.replace(day=1) else [f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip" for d in pd.date_range(m,END,freq="D")]
  for u in us:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     q=[]
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000,low_memory=False):
      x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True); x["price"]=pd.to_numeric(x.price,errors="coerce")
      x=x.dropna(subset=["t","price"]); x=x[(x.t>=START)&(x.t<END)]
      if len(x): x["bar"]=x.t.dt.floor("5min"); q.append(x.groupby("bar").price.agg(open="first",high="max",low="min",close="last"))
    if q: rows.append(pd.concat(q).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}))
    os.remove(p)
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not rows: raise RuntimeError("no data")
 return pd.concat(rows).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}).sort_index().reset_index(names="t")

def ev(d,n,h,c,fee):
 ema=d.close.ewm(span=n,adjust=False).mean(); z=(d.close-ema)/d.close.rolling(n).std()
 sig=np.where((d.close>ema)&(z>1),1,np.where((d.close<ema)&(z<-1),-1,0))
 conf=sig[:-1]*((d.close.iloc[1:].to_numpy()/d.close.iloc[:-1].to_numpy())-1)
 ent=np.where((sig[:-1]!=0)&(conf*sig[:-1]>=c))[0]+1
 if not len(ent): return np.nan,0,np.nan
 ent=ent[ent+h<len(d)]; x=sig[ent]*(d.close.iloc[ent+h].to_numpy()/d.close.iloc[ent].to_numpy()-1)-fee
 return float(x.mean()),len(x),float(x.sum())

S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(n,h,c):ev(tr,n,h,c,F[s])[2] for n in N for h in H for c in C}; n,h,c=max(sc,key=sc.get)
  S.append([s,iv,n,h,c,sc[(n,h,c)],*ev(te,n,h,c,F[s]),*ev(ho,n,h,c,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","lookback","horizon","confirm","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(OUT/"v441_holdout.csv",index=False); (OUT/"summary_v441.md").write_text("# V4.41 — CONFIRMED ENTRY\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))