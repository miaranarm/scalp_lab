import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];N=[48,72,120,168];H=[12,24,48];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,2,3,4]);x.columns=["t","h","l","c"];q.append(x)
  except Exception as e:print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 for c in ["h","l","c"]:x[c]=pd.to_numeric(x[c],errors="coerce")
 return x.dropna()
def ev(x,n,h,c):
 hi=x.h.rolling(n).max().shift(1);lo=x.l.rolling(n).min().shift(1);s=np.where(x.c>hi,1,np.where(x.c<lo,-1,0));z=[];i=n
 while i+h<len(x):
  if s.iloc[i] if hasattr(s,"iloc") else s[i]:
   q=int(s[i]);z.append(q*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(z)
D={s:load(s) for s in SYM};rows=[]
for s in SYM:
 x=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=x[(x.t>=m-pd.DateOffset(months=3))&(x.t<m)];te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))]
  n,h=max(((a,b,ev(tr,a,b,C[s]).sum()) for a in N for b in H),key=lambda q:q[2])[:2]
  z=ev(te,n,h,C[s]);rows.append([s,m.strftime("%Y-%m"),n,h,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","breakout_h","hold_h","oos_total","trades"]);bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v490_oos.csv",index=False);(O/"summary_v490.md").write_text("# V4.90 — LONG HORIZON BREAKOUT\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(bm>0).sum()}/{len(bm)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((bm>0).sum()),"/",len(bm),"TRADES",df.trades.sum())