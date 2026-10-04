import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True);K=[.001,.002,.003,.005]
def load():
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  u=f"https://data.binance.vision/data/futures/um/monthly/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{m:%Y-%m}.zip" if m<B.replace(day=1) else None
  if not u: continue
  p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["i","p","q","a","b","t","m"],chunksize=500000):
     x["t"]=pd.to_datetime(pd.to_numeric(x["t"],errors="coerce"),unit="ms",utc=True);x["p"]=pd.to_numeric(x["p"],errors="coerce");x=x.dropna(subset=["t","p"])
     if len(x):q.append(x.groupby(x.t.dt.floor("5min")).p.last())
   Path(p).unlink(missing_ok=True)
  except Exception as e: print("MISS",m,type(e).__name__)
 return pd.concat(q).groupby(level=0).last().rename("close").reset_index().rename(columns={"index":"t"})
def ev(d,k):
 x=d.set_index("t").resample("15min").last().dropna();a=x.close.ewm(span=8,adjust=False).mean();b=x.close.ewm(span=34,adjust=False).mean();sp=(a/b-1).abs();r=x.close.resample("1h").last().dropna();g=np.sign(r.ewm(span=48,adjust=False).mean().diff()).reindex(x.index,method="ffill").fillna(0).to_numpy();s=np.where((np.sign(a-b)*g>0)&(sp>=k),np.sign(a-b),0);q=[];i=1
 while i+48<len(x):
  if not s[i]:i+=1;continue
  j=i+48;q.append(s[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-.002);i=j
 z=np.array(q);return float(z.sum()) if len(z) else np.nan,len(z)
d=load();ms=pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC");out=[]
for m in ms:
 tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
 sc=[(k,ev(tr,k)[0]) for k in K];p=max(sc,key=lambda z:z[1])[0];r,n=ev(te,p);out.append([m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(out,columns=["month","selected_spread","oos_total","trades"]);df.to_csv(O/"v457_holdout.csv",index=False);(O/"summary_v457.md").write_text("# V4.57 — SOL 3M WALK FORWARD\n\n"+df.to_string(index=False)+"\n\nTOTAL "+str(df.oos_total.sum())+" POS_MONTHS "+str((df.oos_total>0).sum())+"/"+str(len(df)));print(df.to_string(index=False),"\nTOTAL",df.oos_total.sum())