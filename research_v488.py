import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];LB=[6,12,24,48,72];H=[4,8,12,24];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,4]);x.columns=["t","c"];q.append(x)
  except Exception as e:print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True);x.c=pd.to_numeric(x.c,errors="coerce");return x.dropna()
def ev(x,lb,h,c):
 r=x.c.pct_change(lb).shift(1);z=[];i=lb+1
 while i+h<len(x):
  s=1 if r.iloc[i]>0 else -1
  z.append(s*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
 return np.array(z)
D={s:load(s) for s in SYM};rows=[]
for s in SYM:
 x=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=x[(x.t>=m-pd.DateOffset(months=3))&(x.t<m)];te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))]
  lb,h=max(((a,b,ev(tr,a,b,C[s]).sum()) for a in LB for b in H),key=lambda q:q[2])[:2]
  z=ev(te,lb,h,C[s]);rows.append([s,m.strftime("%Y-%m"),lb,h,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","lookback","hold_h","oos_total","trades"]);bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v488_oos.csv",index=False);(O/"summary_v488.md").write_text("# V4.88 — TIME-SERIES MOMENTUM\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(bm>0).sum()}/{len(bm)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((bm>0).sum()),"/",len(bm),"TRADES",df.trades.sum())