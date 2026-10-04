import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True)
A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];TH=[.00005,.0001,.0002,.0003,.0005]
C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1): continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/k.zip"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,4]);x.columns=["t","c"];q.append(x)
  except Exception as e: print("KLINE_MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 q=pd.concat(q).drop_duplicates("t").sort_values("t");q.t=pd.to_datetime(q.t,unit="ms",utc=True);q.c=pd.to_numeric(q.c,errors="coerce")
 return q.dropna()

def funding(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1): continue
  u=f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m:%Y-%m}.zip";p="/tmp/f.zip"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]));x.columns=[str(c).lower() for c in x.columns]
    tc=next(c for c in x if "time" in c);rc=next(c for c in x if "rate" in c)
    q.append(pd.DataFrame({"t":pd.to_datetime(x[tc],unit="ms",utc=True),"f":pd.to_numeric(x[rc],errors="coerce")}))
  except Exception as e: print("FUND_MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 return pd.concat(q).dropna().drop_duplicates("t").sort_values("t")

def trades(k,f,th,cost):
 k=k.set_index("t").c
 r=[]
 for _,z in f.iterrows():
  if abs(z.f)<th: continue
  sig=-1 if z.f>th else 1
  en=k.index[k.index<=z.t]
  ex=k.index[k.index>=z.t+pd.Timedelta(hours=1)]
  if len(en)==0 or len(ex)==0: continue
  ep=float(k.loc[en[-1]]);xp=float(k.loc[ex[0]])
  r.append(sig*(xp/ep-1)-sig*z.f-cost)
 return np.array(r)

D={};F={}
for s in SYM:
 print("LOAD",s);D[s]=load(s);F[s]=funding(s)

rows=[]
for s in SYM:
 f=F[s];k=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=f[(f.t>=m-pd.DateOffset(months=3))&(f.t<m)]
  te=f[(f.t>=m)&(f.t<m+pd.DateOffset(months=1))]
  scores=[(t,trades(k,tr,t,C[s]).sum()) for t in TH]
  p=max(scores,key=lambda z:z[1])[0]
  z=trades(k,te,p,C[s])
  rows.append([s,m.strftime("%Y-%m"),p,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","threshold","oos_total","trades"])
by_s=df.groupby("symbol").oos_total.sum();by_m=df.groupby("month").oos_total.sum()
df.to_csv(O/"v485_oos.csv",index=False)
(O/"summary_v485.md").write_text("# V4.85 — FUNDING CONTRARIAN + PRICE WALK-FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{by_s}\n\nBY_MONTH\n{by_m}\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(by_m>0).sum()}/{len(by_m)}")
print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((by_m>0).sum()),"/",len(by_m))