import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];H=8;C=.002
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
def ev(d):
 x=d.set_index("t");rows=[]
 for day,g in x.groupby(x.index.floor("D")):
  if len(g)<12:continue
  op=g.iloc[:4];hi=op.h.max();lo=op.l.min();rest=g.iloc[4:]
  for i in range(len(rest)-1):
   r=rest.iloc[i];s=1 if r.c>hi else -1 if r.c<lo else 0
   if not s:continue
   en=i+1;ex=min(i+H,len(rest)-1);rows.append(s*(rest.c.iloc[ex]/rest.c.iloc[en]-1)-C);break
 q=np.array(rows);return float(q.sum()) if len(q) else np.nan,len(q)
rows=[]
for s in SYM:
 d=load(s)
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))];r,n=ev(te);rows.append([s,m.strftime("%Y-%m"),r,n])
df=pd.DataFrame(rows,columns=["symbol","month","oos_total","trades"]);df.to_csv(O/"v465_oos.csv",index=False);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum();(O/"summary_v465.md").write_text("# V4.65 — DAILY OPENING RANGE BREAKOUT\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}");print(df.to_string(index=False),"\nTOTAL",s)