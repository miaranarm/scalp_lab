import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];L=[4,8,16];H=8;C=.004
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,4]);x.columns=["t","close"];q.append(x)
   Path(p).unlink(missing_ok=True)
  except Exception as e:print("MISS",s,m,type(e).__name__)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),close=lambda x:x.close.astype(float)).drop_duplicates("t").sort_values("t")
D={s:load(s).set_index("t").close for s in SYM};X=pd.concat(D,axis=1).dropna();rows=[]
def ev(d,l):
 r=d.pct_change(l);a=[];i=l
 while i+H+1<len(d):
  z=r.iloc[i];lo=z.idxmin();hi=z.idxmax()
  if lo==hi:i+=1;continue
  en=i+1;ex=en+H;a.append((d.iloc[ex][hi]/d.iloc[en][hi]-d.iloc[ex][lo]/d.iloc[en][lo])-C);i=ex
 q=np.array(a);return float(q.sum()) if len(q) else np.nan,len(q)
for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
 tr=X[(X.index>=m-pd.DateOffset(months=3))&(X.index<m)];te=X[(X.index>=m)&(X.index<m+pd.DateOffset(months=1))]
 p=max(((l,ev(tr,l)[0]) for l in L),key=lambda x:x[1])[0];r,n=ev(te,p);rows.append([m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(rows,columns=["month","selected_lookback","oos_total","trades"]);df.to_csv(O/"v462_oos.csv",index=False);s=df.oos_total.sum()
(O/"summary_v462.md").write_text("# V4.62 — CROSS-SECTIONAL MOMENTUM WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nTOTAL {s:.6f} POS_MONTHS {(df.oos_total>0).sum()}/{len(df)}")
print(df.to_string(index=False),"\nTOTAL",s,"POS_MONTHS",(df.oos_total>0).sum(),"/",len(df))