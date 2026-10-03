import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
N=[24,48,96]; K=[1.5,2,2.5,3]; H=[3,6,12,24]
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC"); O=Path("results"); O.mkdir(exist_ok=True)
def load(s):
 R=[]
 for m in pd.date_range(START.replace(day=1),END.replace(day=1),freq="MS",tz="UTC"):
  U=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"] if m<END.replace(day=1) else [f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip" for d in pd.date_range(m,END,freq="D")]
  for u in U:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     q=[]
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000,low_memory=False):
      x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True); x["price"]=pd.to_numeric(x.price,errors="coerce"); x["qty"]=pd.to_numeric(x.qty,errors="coerce"); x=x.dropna(subset=["t","price","qty"]); x=x[(x.t>=START)&(x.t<END)]
      if len(x): x["b"]=x.t.dt.floor("5min"); q.append(x.groupby("b").agg(close=("price","last"),pv=("price",lambda z:float((z*x.loc[z.index,"qty"]).sum())),vol=("qty","sum")))
    if q:R.append(pd.concat(q).groupby(level=0).agg({"close":"last","pv":"sum","vol":"sum"}))
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not R: raise RuntimeError("no data")
 return pd.concat(R).groupby(level=0).agg({"close":"last","pv":"sum","vol":"sum"}).sort_index().reset_index(names="t")
def ev(d,n,k,h,fee):
 x=d.set_index("t").resample("15min").agg({"close":"last","pv":"sum","vol":"sum"}).dropna(); v=x.pv.rolling(n).sum()/x.vol.rolling(n).sum(); z=(x.close-v)/x.close.rolling(n).std(); sg=np.where(z>=k,-1,np.where(z<=-k,1,0))
 tr=[]; i=n
 while i+h<len(x):
  if sg[i]==0:i+=1;continue
  j=i+h; tr.append(sg[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-fee); i=j
 q=np.array(tr); return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["15m"]:
  d=d0; tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(n,k,h):ev(tr,n,k,h,F[s])[2] for n in N for k in K for h in H}; n,k,h=max(sc,key=sc.get)
  S.append([s,iv,n,k,h,sc[(n,k,h)],*ev(te,n,k,h,F[s]),*ev(ho,n,k,h,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","lookback","k","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v448_holdout.csv",index=False); (O/"summary_v448.md").write_text("# V4.48 — VWAP MEAN REVERSION\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))