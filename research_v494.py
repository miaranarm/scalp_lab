import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];S=[1.5,2,2.5];V=[1.2,2,3];E=[24,48,72];H=[2,4,8];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,2,3,4,5]);x.columns=["t","h","l","c","v"];q.append(x)
  except Exception as e:print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 for c in ["h","l","c","v"]:x[c]=pd.to_numeric(x[c],errors="coerce")
 return x.dropna()
def ev(x,sh,vm,e,h,c):
 r=x.c.pct_change();atr=(x.h-x.l).rolling(24).mean()/x.c.shift(1);vr=x.v/x.v.rolling(24).median();ema=x.c.ewm(span=e,adjust=False).mean()
 sig=np.where((r>=sh*atr)&(vr>=vm)&(x.c>ema),1,np.where((r<=-sh*atr)&(vr>=vm)&(x.c<ema),-1,0));z=[];i=max(24,e)
 while i+h<len(x):
  if sig[i]:z.append(int(sig[i])*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(z)
D={s:load(s) for s in SYM};rows=[]
for s in SYM:
 x=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=x[(x.t>=m-pd.DateOffset(months=3))&(x.t<m)];te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))]
  sh,vm,e,h=max(((a,b,c,d,ev(tr,a,b,c,d,C[s]).sum()) for a in S for b in V for c in E for d in H),key=lambda q:q[4])[:4]
  z=ev(te,sh,vm,e,h,C[s]);rows.append([s,m.strftime("%Y-%m"),sh,vm,e,h,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","shock","vol_mult","ema","hold_h","oos_total","trades"]);bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v494_oos.csv",index=False);(O/"summary_v494.md").write_text("# V4.94 — SHOCK + VOLUME + TREND FILTER\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(bm>0).sum()}/{len(bm)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((bm>0).sum()),"/",len(bm),"TRADES",df.trades.sum())