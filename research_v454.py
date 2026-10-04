import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
A=pd.Timestamp("2026-04-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True)
def load():
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  us=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{m:%Y-%m}.zip"] if m<B.replace(day=1) else [f"https://data.binance.vision/data/futures/um/daily/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{d:%Y-%m-%d}.zip" for d in pd.date_range(m,B,freq="D")]
  for u in us:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["i","p","q","a","b","t","m"],chunksize=500000):
      x["t"]=pd.to_datetime(pd.to_numeric(x["t"],errors="coerce"),unit="ms",utc=True);x["p"]=pd.to_numeric(x["p"],errors="coerce");x=x.dropna(subset=["t","p"])
      if len(x):q.append(x.groupby(x.t.dt.floor("5min")).p.last())
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",u.split("/")[-1],type(e).__name__)
 return pd.concat(q).groupby(level=0).last().rename("close").reset_index().rename(columns={"index":"t"})
def ev(d,h,c):
 x=d.set_index("t").resample("15min").last().dropna();a=x.close.ewm(span=8,adjust=False).mean();b=x.close.ewm(span=34,adjust=False).mean();r=x.close.resample("1h").last().dropna();g=np.sign(r.ewm(span=48,adjust=False).mean().diff()).reindex(x.index,method="ffill").fillna(0).to_numpy();s=np.where(np.sign(a-b)*g>0,np.sign(a-b),0);q=[];i=1
 while i+h<len(x):
  if not s[i]:i+=1;continue
  j=i+h;q.append(s[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-c);i=j
 z=np.array(q);return float(z.sum()),len(z),float(z.mean()),float(z[z>0].sum()) if len(z) else np.nan
d=load();out=[]
for c in [.0016,.002,.0025]:
 for h in [24,36,48]:
  r=ev(d,h,c);out.append([c,h,*r])
df=pd.DataFrame(out,columns=["cost","horizon","net_total","trades","mean","gross_winners"]);df.to_csv(O/"v454_holdout.csv",index=False);(O/"summary_v454.md").write_text("# V4.54 — SOL EMA 8/34 COST STRESS\n\n"+df.to_string(index=False));print(df.to_string(index=False))