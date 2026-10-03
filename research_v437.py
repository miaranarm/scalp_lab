import zipfile,urllib.request,numpy as np,pandas as pd,os
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};START=pd.Timestamp("2026-04-01",tz="UTC");END=pd.Timestamp("2026-10-03",tz="UTC");N=[6,12,24,48];H=[1,3,6,12];OUT=Path("results");OUT.mkdir(exist_ok=True)
def load(s):
 R=[]
 m=START.replace(day=1)
 while m<=END:
  ds=[m] if m!=END.replace(day=1) else pd.date_range(m,END.normalize(),freq="D",tz="UTC")
  for d in ds:
   u=f"https://data.binance.vision/data/futures/um/{'monthly/aggTrades' if m!=END.replace(day=1) else 'daily/aggTrades'}/{s}/{s}-aggTrades-{d:%Y-%m if m!=END.replace(day=1) else '%Y-%m-%d'}.zip";p="/tmp/a.zip"
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     A=[]
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["id","price","qty","f","l","t","maker"],chunksize=500000):
      x["t"]=pd.to_datetime(x.t,unit="ms",utc=True,errors="coerce");x["price"]=pd.to_numeric(x.price,errors="coerce");x=x.dropna(subset=["t","price"]);x=x[(x.t>=START)&(x.t<END)];x["b"]=x.t.dt.floor("5min");A.append(x.groupby("b").agg(o=("price","first"),hi=("price","max"),lo=("price","min"),c=("price","last")))
    if A:R.append(pd.concat(A).groupby(level=0).agg({"o":"first","hi":"max","lo":"min","c":"last"}))
   except:pass
  m+=pd.offsets.MonthBegin(1)
 d=pd.concat(R).groupby(level=0).agg({"o":"first","hi":"max","lo":"min","c":"last"}).sort_index().reset_index(names="t");return d
def ev(d,n,h,fee):
 up=d.hi.shift(1).rolling(n).max();dn=d.lo.shift(1).rolling(n).min();sg=np.where(d.c>up,1,np.where(d.c<dn,-1,0));r=d.c.shift(-h)/d.c-1;x=(pd.Series(sg,index=d.index)*r-fee)[sg!=0].dropna();return(float(x.mean()),len(x),float(x.sum())) if len(x) else(np.nan,0,np.nan)
S=[]
for s in SYM:
 d0=load(s)
 for iv in["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"o":"first","hi":"max","lo":"min","c":"last"}).dropna().reset_index();tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")];te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))];ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")];sc={(n,h):ev(tr,n,h,F[s])[2] for n in N for h in H};n,h=max(sc,key=sc.get);a=ev(te,n,h,F[s]);b=ev(ho,n,h,F[s]);S.append([s,iv,n,h,sc[(n,h)],*a,*b])
s=pd.DataFrame(S,columns=["symbol","interval","lookback","horizon","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"]);s.to_csv(OUT/"v437_holdout.csv",index=False);Path(OUT/"summary_v437.md").write_text("# V4.37 — DONCHIAN CLOSE BREAKOUT\n\n"+s.to_string(index=False)+"\n");print(s.to_string(index=False))