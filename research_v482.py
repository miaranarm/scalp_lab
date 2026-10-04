import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};K=[(1.5,1.2),(1.5,1.5),(1.5,2),(2,1.2),(2,1.5),(2,2),(2.5,1.2),(2.5,1.5),(2.5,2)];H=4
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1];urllib.request.urlretrieve(u,p)
  with zipfile.ZipFile(p) as z:
   x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,2,3,4,5]);x.columns=["t","h","l","c","v"];q.append(x)
  Path(p).unlink(missing_ok=True)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),**{k:lambda x,k=k:x[k].astype(float) for k in "hlcv"}).drop_duplicates("t").sort_values("t")
def ev(d,k,c):
 x=d.set_index("t");atr=(x.h-x.l).rolling(24).mean();r=x.c.pct_change();vr=x.v/x.v.rolling(24).median();s=np.where((r>k[0]*atr/x.c.shift(1))&(vr>k[1]),-1,np.where((r<-k[0]*atr/x.c.shift(1))&(vr>k[1]),1,0));a=[];i=24
 while i+H+1<len(x):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(x.c.iloc[ex]/x.c.iloc[en]-1)-c);i=ex
 return np.array(a)
rows=[]
for s in SYM:
 d=load(s)
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
  scores=[(k,ev(tr,k,C[s]).sum()) for k in K];p=max(scores,key=lambda z:z[1])[0];z=ev(te,p,C[s]);rows.append([s,m.strftime("%Y-%m"),p[0],p[1],z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","shock","vol","oos_total","trades"]);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();t=df.oos_total.sum()
df.to_csv(O/"v482_oos.csv",index=False);(O/"summary_v482.md").write_text("# V4.82 — SHOCK + VOLUME WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {t:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}")
print(df.to_string(index=False),"\nTOTAL",t)
