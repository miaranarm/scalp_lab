import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True)
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
def ev(d,k):
 x=d.set_index("t").resample("15min").last().dropna();a=x.close.ewm(span=8,adjust=False).mean();b=x.close.ewm(span=34,adjust=False).mean();sp=(a/b-1).abs();r=x.close.resample("1h").last().dropna();g=np.sign(r.ewm(span=48,adjust=False).mean().diff()).reindex(x.index,method="ffill").fillna(0).to_numpy();s=np.where((np.sign(a-b)*g>0)&(sp>=k),np.sign(a-b),0);q=[];i=1
 while i+48<len(x):
  if not s[i]:i+=1;continue
  j=i+48;q.append(s[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-.002);i=j
 z=np.array(q);return [float(z.sum()),len(z),float(z.mean())] if len(z) else [np.nan,0,np.nan]
d=load();cuts=[pd.Timestamp("2026-06-01",tz="UTC"),pd.Timestamp("2026-09-01",tz="UTC")]
tr=d[d.t<cuts[0]];te=d[(d.t>=cuts[0])&(d.t<cuts[1])];ho=d[d.t>=cuts[1]];rows=[]
for k in [.001,.002,.003,.005]:
 a,b,c=ev(tr,k),ev(te,k),ev(ho,k);rows.append([k,*a,*b,*c])
df=pd.DataFrame(rows,columns="spread train_total train_trades train_mean test_total test_trades test_mean holdout_total holdout_trades holdout_mean".split());p=df.loc[df.train_total.idxmax()];df.to_csv(O/"v456_holdout.csv",index=False);(O/"summary_v456.md").write_text("# V4.56 — SOL EMA SPREAD TRAIN TEST HOLDOUT\n\n"+df.to_string(index=False)+"\n\nSELECTED "+str(p.spread));print(df.to_string(index=False),"\nSELECTED",p.spread)