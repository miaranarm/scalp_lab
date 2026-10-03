import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}; N=[12,24,48]; Z=[.5,1,1.5]; E=[24,48,96]; H=[1,3,6]
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
   except: pass
 return pd.concat(R).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}).sort_index().reset_index(names="t")
def ev(d,n,z,e,h,fee):
 x=d.set_index("t"); h1=x.close.resample("1h").last().dropna(); ema=h1.ewm(span=e,adjust=False).mean(); sl=ema.pct_change()
 reg=(sl>0).astype(int)-(sl<0).astype(int); reg=reg.reindex(x.index,method="ffill").to_numpy()
 ema2=x.close.ewm(span=n,adjust=False).mean(); zz=(x.close-ema2)/x.close.rolling(n).std(); sg=np.where(zz>=z,1,np.where(zz<=-z,-1,0)); sg=np.where(sg*reg>0,sg,0)
 r=sg*x.close.shift(-h).div(x.close).sub(1); q=pd.Series(r,index=x.index)[sg!=0].dropna()-fee
 return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(n,z,e,h):ev(tr,n,z,e,h,F[s])[2] for n in N for z in Z for e in E for h in H}; n,z,e,h=max(sc,key=sc.get)
  S.append([s,iv,n,z,e,h,sc[(n,z,e,h)],*ev(te,n,z,e,h,F[s]),*ev(ho,n,z,e,h,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","lookback","z","regime_ema","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v443_holdout.csv",index=False); (O/"summary_v443.md").write_text("# V4.43 — 1H TREND FILTER\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))