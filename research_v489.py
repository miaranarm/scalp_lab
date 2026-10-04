import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];PAIR=[(20,50),(30,80)];PB=[2,3,4];H=[4,8];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m:%Y-%m}.zip"
  try:
   p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,4]);x.columns=["t","c"];q.append(x)
  except Exception as e:print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True);x.c=pd.to_numeric(x.c,errors="coerce");return x.dropna()
def ev(x,a,b,pb,h,c):
 c15=x.c;ema=c15.ewm(span=10,adjust=False).mean();ret=c15.pct_change(pb);slow=c15.ewm(span=b,adjust=False).mean();fast=c15.ewm(span=a,adjust=False).mean()
 s=np.where((fast>slow)&(ret<0)&(c15>ema),1,np.where((fast<slow)&(ret>0)&(c15<ema),-1,0));z=[];i=b
 while i+h<len(x):
  if s[i]:z.append(s[i]*(c15.iloc[i+h]/c15.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(z)
D={s:load(s) for s in SYM};rows=[]
for s in SYM:
 x=D[s]
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=x[(x.t>=m-pd.DateOffset(months=3))&(x.t<m)];te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))]
  a,b,pb,h=max(((a,b,p,h,ev(tr,a,b,p,h,C[s]).sum()) for a,b in PAIR for p in PB for h in H),key=lambda q:q[4])[:4]
  z=ev(te,a,b,pb,h,C[s]);rows.append([s,m.strftime("%Y-%m"),a,b,pb,h,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","ema_fast","ema_slow","pullback","hold_h","oos_total","trades"]);bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v489_oos.csv",index=False);(O/"summary_v489.md").write_text("# V4.89 — TREND PULLBACK CONTINUATION\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(bm>0).sum()}/{len(bm)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((bm>0).sum()),"/",len(bm),"TRADES",df.trades.sum())