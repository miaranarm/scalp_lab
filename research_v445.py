import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
P=[(8,34),(12,48),(20,80)]; H=[6,12,24,36]; T=[0,1]
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
      x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True); x["price"]=pd.to_numeric(x.price,errors="coerce"); x=x.dropna(subset=["t","price"]); x=x[(x.t>=START)&(x.t<END)]
      if len(x): x["b"]=x.t.dt.floor("5min"); q.append(x.groupby("b").price.agg(open="first",high="max",low="min",close="last"))
    if q:R.append(pd.concat(q).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}))
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not R: raise RuntimeError("no data")
 return pd.concat(R).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}).sort_index().reset_index(names="t")
def ev(d,fast,slow,h,trend,fee):
 x=d.set_index("t"); a=x.close.ewm(span=fast,adjust=False).mean(); b=x.close.ewm(span=slow,adjust=False).mean()
 sg=np.sign(a-b).to_numpy()
 if trend:
  h1=x.close.resample("1h").last().dropna(); e=h1.ewm(span=48,adjust=False).mean(); rg=np.sign(e.diff()).reindex(x.index,method="ffill").fillna(0).to_numpy(); sg=np.where(sg*rg>0,sg,0)
 r=sg*x.close.shift(-h).div(x.close).sub(1); q=pd.Series(r,index=x.index)[sg!=0].dropna()-fee
 return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(f,sl,h,t):ev(tr,f,sl,h,t,F[s])[2] for f,sl in P for h in H for t in T}; f,sl,h,t=max(sc,key=sc.get)
  S.append([s,iv,f,sl,h,t,sc[(f,sl,h,t)],*ev(te,f,sl,h,t,F[s]),*ev(ho,f,sl,h,t,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","fast","slow","horizon","trend_filter","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v445_holdout.csv",index=False); (O/"summary_v445.md").write_text("# V4.45 — LOW-TURNOVER EMA CROSS\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))