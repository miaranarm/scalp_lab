import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];IMB=[.2,.3,.4,.5];VOL=[1.5,2,3];H=3;C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/5m/{s}-5m-{m:%Y-%m}.zip";p="/tmp/k.zip"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,1,2,3,4,5,9]);x.columns=["t","o","h","l","c","v","tb"]
    q.append(x)
  except Exception as e: print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 for c in ["o","h","l","c","v","tb"]:x[c]=pd.to_numeric(x[c],errors="coerce")
 x["imb"]=2*x.tb/x.v-1;x["rng"]=(x.h-x.l)/x.o;x["vr"]=x.v/x.v.rolling(96).median()
 return x.dropna()

def ev(d,im,vol,cost):
 x=d.reset_index(drop=True);s=np.where((x.imb<=-im)&(x.vr>=vol),1,np.where((x.imb>=im)&(x.vr>=vol),-1,0));r=[];i=96
 while i+H<len(x):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H
  r.append(s[i]*(x.c.iloc[ex]/x.c.iloc[en]-1)-cost);i=ex
 return np.array(r)

D={s:load(s) for s in SYM};rows=[]
GRID=[(a,b) for a in IMB for b in VOL]
for s in SYM:
 d=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)]
  te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
  p=max(((a,b,ev(tr,a,b,C[s]).sum()) for a,b in GRID),key=lambda z:z[2])[:2]
  z=ev(te,*p,C[s]);rows.append([s,m.strftime("%Y-%m"),*p,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","imb","vol_mult","oos_total","trades"]);bs=df.groupby("symbol").oos_total.sum();bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v486_oos.csv",index=False);(O/"summary_v486.md").write_text("# V4.86 — TAKER IMBALANCE + VOLUME WALK-FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{bs}\n\nBY_MONTH\n{bm}\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(bm>0).sum()}/{len(bm)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((bm>0).sum()),"/",len(bm),"TRADES",df.trades.sum())