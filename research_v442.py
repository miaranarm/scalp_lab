import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
N=[12,24,48]; H=[1,3,6,12]; Z=[.5,1,1.5,2]; M=["MOM","CONTRA"]
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
def ev(d,n,h,z,mode,fee):
 r=d.close.pct_change(); zz=r/r.rolling(n).std(); sg=np.where(zz>=z,1,np.where(zz<=-z,-1,0)); sg=-sg if mode=="CONTRA" else sg
 x=pd.Series(sg,index=d.index)*d.close.shift(-h).div(d.close).sub(1); x=x[sg!=0].dropna()-fee
 return (float(x.mean()),len(x),float(x.sum())) if len(x) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(n,h,z,m):ev(tr,n,h,z,m,F[s])[2] for n in N for h in H for z in Z for m in M}; n,h,z,m=max(sc,key=sc.get)
  S.append([s,iv,n,h,z,m,sc[(n,h,z,m)],*ev(te,n,h,z,m,F[s]),*ev(ho,n,h,z,m,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","lookback","horizon","z","mode","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v442_holdout.csv",index=False); (O/"summary_v442.md").write_text("# V4.42 — RETURN SHOCK MOMENTUM / CONTRARIAN\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))