import os,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
FAST,SLOW,H=8,34,36; COST=[.0012,.0016,.0020,.0024]
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
def sim(d,cost):
 x=d.set_index("t").resample("15min").agg({"close":"last"}).dropna(); a=x.close.ewm(span=FAST,adjust=False).mean(); b=x.close.ewm(span=SLOW,adjust=False).mean()
 h1=x.close.resample("1h").last().dropna(); e=h1.ewm(span=48,adjust=False).mean(); rg=np.sign(e.diff()).reindex(x.index,method="ffill").fillna(0).to_numpy(); sg=np.sign(a-b).to_numpy(); sg=np.where(sg*rg>0,sg,0)
 tr=[]; i=1
 while i+H<len(x):
  if sg[i]==0:i+=1; continue
  j=i+H; ret=sg[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-cost; tr.append(ret); i=j
 q=np.array(tr); return (float(q.mean()),len(q),float(q.sum())) if len(q) else (np.nan,0,np.nan)
S=[]
for s in SYM:
 d=load(s)
 for label,lo,hi in [("TEST","2026-07-01","2026-09-01"),("HOLDOUT","2026-09-01","2026-10-03")]:
  z=d[(d.t>=pd.Timestamp(lo,tz="UTC"))&(d.t<pd.Timestamp(hi,tz="UTC"))]
  for c in COST:
   m,n,t=sim(z,c); S.append([s,label,c,m,n,t])
df=pd.DataFrame(S,columns=["symbol","period","cost","mean_trade","trades","total"]); df.to_csv(O/"v446_execution.csv",index=False)
(O/"summary_v446.md").write_text("# V4.46 — NON-OVERLAPPING EXECUTION CONFIRMATION\n\n"+df.to_string(index=False)+"\n"); print(df.to_string(index=False))