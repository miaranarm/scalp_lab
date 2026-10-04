import io,zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];K=[5,10,15];H=8;C=.002
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    q.append(pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,4],names=["t","close"]))
   Path(p).unlink(missing_ok=True)
  except Exception as e:print("MISS",s,m,type(e).__name__)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True)).drop_duplicates("t").sort_values("t")
def ev(d,k):
 c=d.set_index("t").close.astype(float);r=c.diff();up=r.clip(lower=0);dn=-r.clip(upper=0);rs=up.ewm(alpha=.5,adjust=False).mean()/dn.ewm(alpha=.5,adjust=False).mean();z=100-100/(1+rs)
 s=np.where(z<k,1,np.where(z>100-k,-1,0));a=[];i=0
 while i+H+1<len(c):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H
  if ex>=len(c):break
  a.append(s[i]*(c.iloc[ex]/c.iloc[en]-1)-C);i=ex
 x=np.array(a);return (float(x.sum()) if len(x) else np.nan,len(x))
D={s:load(s) for s in SYM};rows=[]
for s,d in D.items():
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
  p=max(((k,ev(tr,k)[0]) for k in K),key=lambda x:x[1])[0];r,n=ev(te,p);rows.append([s,m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(rows,columns=["symbol","month","selected_rsi","oos_total","trades"]);df.to_csv(O/"v459_oos.csv",index=False)
g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum()
(O/"summary_v459.md").write_text("# V4.59 — RSI(2) MULTI-MARKET WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}")
print(df.to_string(index=False),"\nBY_SYMBOL",g,"\nTOTAL",s,"POS_MONTHS",(w>0).sum(),"/",len(w))
