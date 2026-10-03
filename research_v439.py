import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}; N=[12,24,48,96]; H=[1,3,6,12]
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC"); TH=[.20,.30,.40]; H=[1,3,6]
OUT=Path("results"); OUT.mkdir(exist_ok=True)

def sources(s):
 m=pd.Timestamp(START.year,START.month,1,tz="UTC")
 while m<=END:
  if m.month==END.month and m.year==END.year:
   d=m
   while d<=END.normalize():
    yield f"{s}-aggTrades-{d:%Y-%m-%d}.zip",f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip"
    d+=pd.Timedelta(days=1)
  else:
   yield f"{s}-aggTrades-{m:%Y-%m}.zip",f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"
  m+=pd.offsets.MonthBegin(1)

def load(s):
 rows=[]
 for n,u in sources(s):
  p=f"/tmp/{n}"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    a=[]
    for d in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000):
     d["t"]=pd.to_datetime(pd.to_numeric(d.t,errors="coerce"),unit="ms",utc=True)
     d["price"]=pd.to_numeric(d.price,errors="coerce"); d["qty"]=pd.to_numeric(d.qty,errors="coerce"); d["maker"]=pd.to_numeric(d.maker,errors="coerce")
     d=d.dropna(subset=["t","price","qty","maker"]); d["maker"]=d.maker.astype(bool); d=d[(d.t>=START)&(d.t<END)]
     if len(d):
      d["bar5"]=d.t.dt.floor("5min")
      a.append(d.groupby("bar5").agg(open=("price","first"),high=("price","max"),low=("price","min"),close=("price","last")))
   if a: rows.append(pd.concat(a).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}))
   os.remove(p); print("OK",n)
  except Exception as e: print("MISS",n,type(e).__name__)
 if not rows: raise RuntimeError(f"No usable aggTrades data for {s}")
 d=pd.concat(rows).groupby(level=0).agg({"open":"first","high":"max","low":"min","close":"last"}).sort_index()
 return d.reset_index(names="t")

def ev(d,n,h,fee):
 ema=d.close.ewm(span=n,adjust=False).mean(); z=(d.close-ema)/d.close.rolling(n).std(); sig=np.where((d.close>ema)&(z>1),1,np.where((d.close<ema)&(z<-1),-1,0))
 r=d.close.shift(-h)/d.close-1; x=(pd.Series(sig,index=d.index)*r-fee)[sig!=0].dropna()
 return (float(x.mean()),len(x),float(x.sum())) if len(x) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
  c1=pd.Timestamp("2026-07-01",tz="UTC"); c2=pd.Timestamp("2026-09-01",tz="UTC")
  tr=d[d.t<c1]; te=d[(d.t>=c1)&(d.t<c2)]; ho=d[d.t>=c2]
  sc={(n,h):ev(tr,n,h,F[s])[2] for n in N for h in H}; n,h=max(sc,key=sc.get); a=ev(te,n,h,F[s]); b=ev(ho,n,h,F[s]); S.append([s,iv,n,h,sc[(n,h)],*a,*b])
s=pd.DataFrame(S,columns=["symbol","interval","lookback","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
s.to_csv(OUT/"v439_holdout.csv",index=False); Path(OUT/"summary_v437.md").write_text("# V4.39 — EMA ZSCORE TREND — DONCHIAN CLOSE BREAKOUT\n\n"+s.to_string(index=False)+"\n"); print(s.to_string(index=False))