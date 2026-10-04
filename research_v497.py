import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];S=[1.5,2,2.5];V=[1.2,2,3];E=[24,48,72];H=[2,4,8];M=[.75,1,1.25,1.5,2];C0={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,2,3,4,5]);x.columns=["t","h","l","c","v"];q.append(x)
  except:pass
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 for c in ["h","l","c","v"]:x[c]=pd.to_numeric(x[c],errors="coerce")
 return x.dropna()
def ev(x,sh,vm,e,h,c):
 r=x.c.pct_change();atr=(x.h-x.l).rolling(24).mean()/x.c.shift(1);vr=x.v/x.v.rolling(24).median();ema=x.c.ewm(span=e,adjust=False).mean();sig=np.where((r>=sh*atr)&(vr>=vm)&(x.c>ema),1,np.where((r<=-sh*atr)&(vr>=vm)&(x.c<ema),-1,0));z=[];i=max(24,e)
 while i+h<len(x):
  if sig[i]:z.append(int(sig[i])*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(z)
D={s:load(s) for s in SYM};rows=[]
for mult in M:
 for s in SYM:
  x=D[s];c0=C0[s]*mult
  for m in pd.date_range("2023-01-01","2026-09-01",freq="MS",tz="UTC"):
   tr=x[(x.t>=m-pd.DateOffset(months=3))&(x.t<m)];te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))]
   sh,vm,e,h=max(((a,b,c,d,ev(tr,a,b,c,d,c0).sum()) for a in S for b in V for c in E for d in H),key=lambda q:q[4])[:4]
   z=ev(te,sh,vm,e,h,c0);rows.append([mult,s,m.strftime("%Y-%m"),z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["cost_mult","symbol","month","oos_total","trades"]);g=df.groupby("cost_mult").oos_total.sum();pm=df.groupby(["cost_mult","month"]).oos_total.sum().groupby(level=0).apply(lambda x:(x>0).sum())
df.to_csv(O/"v497_oos.csv",index=False);(O/"summary_v497.md").write_text("# V4.97 — SHOCK TREND COST STRESS\n\n"+df.groupby("cost_mult").oos_total.sum().to_string()+f"\n\nPOS_MONTHS\n{pm}\n\nTRADES\n"+df.groupby("cost_mult").trades.sum().to_string());print("TOTAL_BY_COST");print(g);print("POS_MONTHS");print(pm)