import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];K=4;HS=[4,8,12];C=.002
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,1,2,3,4]);x.columns=["t","o","h","l","c"];q.append(x)
   Path(p).unlink(missing_ok=True)
  except Exception as e:print("MISS",s,m,type(e).__name__)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),**{k:lambda x,k=k:x[k].astype(float) for k in "ohlc"}).drop_duplicates("t").sort_values("t")
def ev(d,H):
 x=d.set_index("t");a=[]
 for day,g in x.groupby(x.index.floor("D")):
  if len(g)<K+H+2:continue
  hi=g.h.iloc[:K].max();lo=g.l.iloc[:K].min();pg=x[(x.index<day)&(x.index>=day-pd.Timedelta(days=1))]
  if len(pg)<12:continue
  bias=1 if pg.c.iloc[-1]>pg.c.iloc[0] else -1;r=g.iloc[K:]
  for i in range(len(r)-H-1):
   raw=1 if r.c.iloc[i]>hi else -1 if r.c.iloc[i]<lo else 0;s=raw if raw==bias else 0
   if s:
    en=i+1;ex=en+H;a.append(s*(r.c.iloc[ex]/r.c.iloc[en]-1)-C);break
 q=np.array(a);return float(q.sum()) if len(q) else np.nan,len(q)
rows=[]
for s in SYM:
 d=load(s)
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
  p=max(((h,ev(tr,h)[0]) for h in HS),key=lambda x:x[1])[0];r,n=ev(te,p);rows.append([s,m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(rows,columns=["symbol","month","selected_hold_h","oos_total","trades"]);df.to_csv(O/"v468_oos.csv",index=False);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum();(O/"summary_v468.md").write_text("# V4.68 — ORB BIAS HOLD WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}");print(df.to_string(index=False),"\nTOTAL",s)