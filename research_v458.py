import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True)
K=[1.5,2.0,2.5,3.0];H=8;C=.002
def load():
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1): continue
  u=f"https://data.binance.vision/data/futures/um/monthly/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["i","p","q","a","b","t","m"],chunksize=500000):
     x["t"]=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True);x["p"]=pd.to_numeric(x.p,errors="coerce");x["q"]=pd.to_numeric(x.q,errors="coerce")
     x=x.dropna(subset=["t","p","q"]);x["pv"]=x.p*x.q;q.append(x.groupby(x.t.dt.floor("5min")).agg(close=("p","last"),vol=("q","sum"),pv=("pv","sum")))
   Path(p).unlink(missing_ok=True)
  except Exception as e: print("MISS",m,type(e).__name__)
 return pd.concat(q).groupby(level=0).agg({"close":"last","vol":"sum","pv":"sum"}).reset_index().rename(columns={"t":"t"})
def ev(d,k):
 x=d.set_index("t").resample("15min").agg({"close":"last","vol":"sum","pv":"sum"}).dropna()
 v=x.pv.rolling(48).sum()/x.vol.rolling(48).sum();r=np.log(x.close/v);z=(r-r.rolling(96).mean())/r.rolling(96).std()
 s=np.where(z>k,-1,np.where(z<-k,1,0));q=[];i=0
 while i+H+1<len(x):
  if not s[i]: i+=1;continue
  en=i+1;ex=en+H;q.append(s[i]*(x.close.iloc[ex]/x.close.iloc[en]-1)-C);i=ex
  i=max(i,en)
 a=np.array(q);return (float(a.sum()) if len(a) else np.nan,len(a))
d=load();ms=pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC");out=[]
for m in ms:
 tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
 p=max(((k,ev(tr,k)[0]) for k in K),key=lambda x:x[1])[0];r,n=ev(te,p);out.append([m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(out,columns=["month","selected_z","oos_total","trades"]);df.to_csv(O/"v458_holdout.csv",index=False)
(O/"summary_v458.md").write_text("# V4.58 — SOL 15m VWAP MEAN REVERSION\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum()} POS_MONTHS {(df.oos_total>0).sum()}/{len(df)}")
print(df.to_string(index=False),"\nTOTAL",df.oos_total.sum())
