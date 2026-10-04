import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
S=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};N=[24,48,96];R=[20,30,40];Z=[1,2];H=[6,12,24,36];MIN=40;A=pd.Timestamp("2026-04-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");O=Path("results");O.mkdir(exist_ok=True)
def load(s):
 q=[]
 for m in pd.date_range(A.replace(day=1),B.replace(day=1),freq="MS",tz="UTC"):
  us=[f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"] if m<B.replace(day=1) else [f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip" for d in pd.date_range(m,B,freq="D")]
  for u in us:
   p="/tmp/"+u.rsplit("/",1)[-1]
   try:
    urllib.request.urlretrieve(u,p)
    with zipfile.ZipFile(p) as z:
     for x in pd.read_csv(z.open(z.namelist()[0]),header=None,names=["i","p","q","a","b","t","m"],chunksize=500000):
      x.t=pd.to_datetime(pd.to_numeric(x.t,errors="coerce"),unit="ms",utc=True);x.p=pd.to_numeric(x.p,errors="coerce");x=x.dropna(subset=["t","p"]);x=x[(x.t>=A)&(x.t<B)]
      if len(x):q.append(x.groupby(x.t.dt.floor("5min")).p.last())
    Path(p).unlink(missing_ok=True)
   except:pass
 return pd.concat(q).groupby(level=0).last().sort_index().rename("close").to_frame().reset_index(names="t")
def ev(d,n,r,z,h,c):
 x=d.set_index("t").resample("15min").last().dropna();ret=x.close.pct_change();v=ret.rolling(n).std();ma=x.close.rolling(n).mean();score=(x.close-ma)/v;trend=x.close.ewm(span=96,adjust=False).mean();sg=np.where((score<=-z)&(x.close>trend),1,np.where((score>=z)&(x.close<trend),-1,0));tr=[];i=n
 while i+h<len(x):
  if not sg[i]:i+=1;continue
  j=i+h;tr.append(sg[i]*(x.close.iloc[j]/x.close.iloc[i]-1)-c);i=j
 q=np.array(tr);return (q.mean(),len(q),q.sum()) if len(q) else (np.nan,0,np.nan)
out=[]
for s in S:
 d=load(s);tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")];te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))];ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")];sc={(n,r,z,h):ev(tr,n,r,z,h,C[s]) for n in N for r in R for z in Z for h in H};sc={p:v for p,v in sc.items() if v[1]>=MIN};p=max(sc,key=lambda p:sc[p][2]);a=ev(te,*p,C[s]);b=ev(ho,*p,C[s]);out.append([s,*p,sc[p][2],*a,*b])
df=pd.DataFrame(out,columns="symbol n rsi_window z horizon train_total test_mean test_trades test_total holdout_mean holdout_trades holdout_total".split());df.to_csv(O/"v452_holdout.csv",index=False);(O/"summary_v452.md").write_text("# V4.52 — RSI/Z-SCORE MEAN REVERSION + TREND\n\n"+df.to_string(index=False));print(df.to_string(index=False))