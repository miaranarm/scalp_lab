import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2022-10-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];P=[7,14,21];T=[20,25,30,35];H=[2,4,8];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/k.zip";urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,4]);x.columns=["t","c"];q.append(x)
  except:pass
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True);x.c=pd.to_numeric(x.c,errors="coerce");return x.dropna()
def ev(x,p,t,h,c):
 d=x.c.diff();up=d.clip(lower=0).rolling(p).mean();dn=(-d.clip(upper=0)).rolling(p).mean();rs=up/dn.replace(0,np.nan);rsi=100-100/(1+rs);sig=np.where(rsi<=t,1,np.where(rsi>=100-t,-1,0));r=[];i=p
 while i+h<len(x):
  if sig[i]:r.append(int(sig[i])*(x.c.iloc[i+h]/x.c.iloc[i]-1)-c);i+=h
  else:i+=1
 return np.array(r)
D={s:load(s) for s in SYM};rows=[];pars=[]
for s in SYM:
 x=D[s];tr=x[(x.t>="2023-01-01")&(x.t<"2026-01-01")]
 p=max(((a,b,h,ev(tr,a,b,h,C[s]).sum(),len(ev(tr,a,b,h,C[s]))) for a in P for b in T for h in H),key=lambda q:q[3]);per,t,h=p[:3];pars.append([s,per,t,h,p[3],p[4]])
 for mult in [.75,1,1.25,1.5,2]:
  for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
   te=x[(x.t>=m)&(x.t<m+pd.DateOffset(months=1))];r=ev(te,per,t,h,C[s]*mult);rows.append([mult,s,m.strftime("%Y-%m"),per,t,h,r.sum(),len(r)])
df=pd.DataFrame(rows,columns=["cost_mult","symbol","month","rsi_p","threshold","hold_h","oos_total","trades"]);pa=pd.DataFrame(pars,columns=["symbol","rsi_p","threshold","hold_h","train_total","train_trades"])
g=df.groupby("cost_mult").oos_total.sum();pm=df.groupby(["cost_mult","month"]).oos_total.sum().groupby(level=0).apply(lambda x:int((x>0).sum()))
df.to_csv(O/"v502_oos.csv",index=False);pa.to_csv(O/"v502_params.csv",index=False)
s="# V5.02 — RSI REVERSAL 2026 HOLDOUT\n\nTRAIN 2023-01..2025-12\nHOLDOUT 2026-01..2026-09\n\nPARAMS\n"+pa.to_string(index=False)+"\n\nTOTAL BY COST\n"+g.to_string()+"\n\nPOSITIVE MONTHS\n"+pm.to_string()+"\n\nTRADES\n"+df.groupby("cost_mult").trades.sum().to_string()+"\n";(O/"summary_v502.md").write_text(s);print(s)