import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
N=[24,48,96]; K=[1,1.5,2]; H=[3,6,12]; MIN=40
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
      if len(x): x["b"]=x.t.dt.floor("5min"); q.append(x.groupby("b").agg(close=("price","last"),high=("price","max"),low=("price","min"),vol=("qty","sum")))
    if q:R.append(pd.concat(q).groupby(level=0).agg({"close":"last","high":"max","low":"min","vol":"sum"}))
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",os.path.basename(u),type(e).__name__)
 if not R: raise RuntimeError("no data")
 return pd.concat(R).groupby(level=0).agg({"close":"last","high":"max","low":"min","vol":"sum"}).sort_index().reset_index(names="t")
def ev(d,n,k,h,cost):
 x=d.set_index("t").resample("15min").agg({"close":"last","high":"max","low":"min","vol":"sum"}).dropna()
 up=x.high.shift(1).rolling(n).max(); dn=x.low.shift(1).rolling(n).min(); vr=x.vol/x.vol.rolling(n).median()
 sg=np.where((x.close>up)&(vr>=k),1,np.where((x.close<dn)&(vr>=k),-1,0))
 tr=[]; i=n
 while i+h<len(x):
  if sg[i]==0:i+=1;continue
  j=i+h; tr.append(sg[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-cost); i=j
 q=np.array(tr); return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d=load(s); tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
 sc={(n,k,h):ev(tr,n,k,h,F[s]) for n in N for k in K for h in H}; sc={p:r for p,r in sc.items() if r[1]>=MIN}
 if not sc: raise RuntimeError(f"no train candidate {s}")
 p=max(sc,key=lambda p:sc[p][2]); a=ev(te,*p,F[s]); b=ev(ho,*p,F[s]); S.append([s,*p,sc[p][2],*a,*b])
df=pd.DataFrame(S,columns=["symbol","lookback","vol_ratio","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
df.to_csv(O/"v450_holdout.csv",index=False); (O/"summary_v450.md").write_text("# V4.50 — VOLUME CONFIRMED BREAKOUT\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))