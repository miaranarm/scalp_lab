import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
TH=[.3,.4,.5,.6]; P=[2,3,4]; H=[1,3,6]; C=[0,1]
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
      x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True); x["price"]=pd.to_numeric(x.price,errors="coerce"); x["qty"]=pd.to_numeric(x.qty,errors="coerce")
      x=x.dropna(subset=["t","price","qty"]); x=x[(x.t>=START)&(x.t<END)]
      if len(x):
       x["b"]=x.t.dt.floor("5min"); x["sv"]=np.where(x.maker,-x.qty,x.qty)
       q.append(x.groupby("b").agg(close=("price","last"),sv=("sv","sum"),vol=("qty","sum")))
    if q:R.append(pd.concat(q).groupby(level=0).agg({"close":"last","sv":"sum","vol":"sum"}))
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not R: raise RuntimeError("no data")
 return pd.concat(R).groupby(level=0).agg({"close":"last","sv":"sum","vol":"sum"}).sort_index().reset_index(names="t")
def ev(d,th,p,h,c,fee):
 x=d.copy(); x["imb"]=x.sv/x.vol; z=x.imb.rolling(p).apply(lambda a: 1 if (np.all(a>=th)) else (-1 if np.all(a<=-th) else 0),raw=True)
 if c: z=np.where(z*x.close.pct_change()>0,z,0)
 r=z*x.close.shift(-h).div(x.close).sub(1); q=pd.Series(r,index=x.index)[z!=0].dropna()-fee
 return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"close":"last","sv":"sum","vol":"sum"}).dropna().reset_index()
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  sc={(th,p,h,c):ev(tr,th,p,h,c,F[s])[2] for th in TH for p in P for h in H for c in C}; th,p,h,c=max(sc,key=sc.get)
  S.append([s,iv,th,p,h,c,sc[(th,p,h,c)],*ev(te,th,p,h,c,F[s]),*ev(ho,th,p,h,c,F[s])])
df=pd.DataFrame(S,columns=["symbol","interval","threshold","persistence","horizon","confirm","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v444_holdout.csv",index=False); (O/"summary_v444.md").write_text("# V4.44 — ORDER-FLOW PERSISTENCE\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))