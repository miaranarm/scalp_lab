import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
S=["SOLUSDT"];C=.0016;A=pd.Timestamp("2026-04-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True)
def load():
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  us=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{m:%Y-%m}.zip"] if m<B.replace(day=1) else [f"https://data.binance.vision/data/futures/um/daily/aggTrades/SOLUSDT/SOLUSDT-aggTrades-{d:%Y-%m-%d}.zip" for d in pd.date_range(m,B,freq="D")]
  for u in us:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=list("iabctm")+["q"],chunksize=500000):
      x["t"]=pd.to_datetime(pd.to_numeric(x["t"],errors="coerce"),unit="ms",utc=True);x["p"]=pd.to_numeric(x["p"],errors="coerce");x=x.dropna(subset=["t","p"])
      if len(x):q.append(x.groupby(x.t.dt.floor("5min")).p.last())
    Path(p).unlink(missing_ok=True)
   except Exception as e: print("MISS",u.split("/")[-1],type(e).__name__)
 return pd.concat(q).groupby(level=0).last().rename("close").reset_index().rename(columns={"index":"t"})
def ev(d):
 x=d.set_index("t").resample("15min").last().dropna();a=x.close.ewm(span=8,adjust=False).mean();b=x.close.ewm(span=34,adjust=False).mean();r=x.close.resample("1h").last().dropna();e=r.ewm(span=48,adjust=False).mean();g=np.sign(e.diff()).reindex(x.index,method="ffill").fillna(0).to_numpy();sg=np.where(np.sign(a-b)*g>0,np.sign(a-b),0);tr=[];i=1
 while i+36<len(x):
  if not sg[i]:i+=1;continue
  j=i+36;tr.append(sg[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-C);i=j
 q=np.array(tr);return [float(q.sum()),len(q),float(q.mean())] if len(q) else [np.nan,0,np.nan]
d=load();rows=[]
for m in pd.date_range(A,B-pd.Timedelta(days=1),freq="MS",tz="UTC"):
 z=d[(d.t>=m)&(d.t<m+pd.offsets.MonthBegin(1))];r=ev(z);rows.append([m.strftime("%Y-%m"),*r])
df=pd.DataFrame(rows,columns=["month","net_total","trades","mean"]);df.to_csv(O/"v453_holdout.csv",index=False);(O/"summary_v453.md").write_text("# V4.53 — SOL 15m EMA 8/34 MONTHLY OOS\n\n"+df.to_string(index=False));print(df.to_string(index=False))\n# trigger\n