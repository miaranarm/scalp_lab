import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-10-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];S=[1.5,2,2.5];V=[1.2,2,3];E=[24,48,72];H=[2,4,8];F=[0,.001,.002];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,2,3,4,5]);x.columns=["t","h","l","c","v"];q.append(x)
  except:pass
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 for c in ["h","l","c","v"]:x[c]=pd.to_numeric(x[c],errors="coerce")
 return x.dropna()
def ev(x,sh,vm,e,h,f,c):
 r=x.c.pct_change();atr=(x.h-x.l).rolling(24).mean()/x.c.shift(1);vr=x.v/x.v.rolling(24).median();ema=x.c.ewm(span=e,adjust=False).mean()
 sig=np.where((r>=sh*atr)&(vr>=vm)&(x.c>ema),1,np.where((r<=-sh*atr)&(vr>=vm)&(x.c<ema),-1,0));z=[];i=max(24,e)+1
 while i+h<len(x):
  if sig[i-1] and int(sig[i-1])*r.iloc[i]>=f:
   z.append(int(sig[i-1])*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(z)
D={s:load(s) for s in SYM};rows=[];pars=[]
for s in SYM:
 x=D[s];tr=x[(x.t>="2023-01-01")&(x.t<"2026-01-01")]
 p=max(((a,b,c,d,f,ev(tr,a,b,c,d,f,C[s]).sum(),len(ev(tr,a,b,c,d,f,C[s]))) for a in S for b in V for c in E for d in H for f in F),key=lambda q:q[5])
 sh,vm,e,h,f=p[:5];pars.append([s,sh,vm,e,h,f,p[5],p[6]])
 for mult in [.75,1,1.25,1.5,2]:
  c=C[s]*mult
  for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
   te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))];z=ev(te,sh,vm,e,h,f,c);rows.append([mult,s,m.strftime("%Y-%m"),sh,vm,e,h,f,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["cost_mult","symbol","month","shock","vol_mult","ema","hold_h","confirm","oos_total","trades"]);pa=pd.DataFrame(pars,columns=["symbol","shock","vol_mult","ema","hold_h","confirm","train_total","train_trades"])
g=df.groupby("cost_mult").oos_total.sum();pm=df.groupby(["cost_mult","month"]).oos_total.sum().groupby(level=0).apply(lambda x:int((x>0).sum()))
df.to_csv(O/"v499_oos.csv",index=False);pa.to_csv(O/"v499_params.csv",index=False)
s="# V4.99 — ONE-BAR CONFIRMATION HOLDOUT\n\nTRAIN 2023-01..2025-12\nHOLDOUT 2026-01..2026-09\n\nPARAMS\n"+pa.to_string(index=False)+"\n\nTOTAL BY COST\n"+g.to_string()+"\n\nPOSITIVE MONTHS\n"+pm.to_string()+"\n\nTRADES\n"+df.groupby("cost_mult").trades.sum().to_string()+"\n";(O/"summary_v499.md").write_text(s);print(s)