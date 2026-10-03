import io,zipfile,urllib.request
from pathlib import Path
from datetime import timedelta
import pandas as pd
import numpy as np

SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; IV=["5m","15m"]
BASE="https://data.binance.vision/data/futures/um/monthly/klines"; OUT=Path("results"); OUT.mkdir(exist_ok=True)
START=pd.Timestamp("2025-10-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC")
FEE={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}; TH=[.20,.30,.40]; H={"5m":[3,6,12],"15m":[3,6,12]}

def months(a,b):
 x=pd.Timestamp(a.year,a.month,1,tz="UTC"); z=pd.Timestamp(b.year,b.month,1,tz="UTC")
 while x<=z: yield x; x+=pd.offsets.MonthBegin(1)

def load(s,iv):
 fs=[]
 for m in months(START,END):
  u=f"{BASE}/{s}/{iv}/{s}-{iv}-{m:%Y-%m}.zip"
  try:
   raw=urllib.request.urlopen(u,timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(raw)) as q: d=pd.read_csv(q.open(q.namelist()[0]),header=None)
   d=d.iloc[:,:12]; d.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]; fs.append(d)
  except Exception as e: print("MISS",s,iv,m.strftime("%Y-%m"),type(e).__name__)
 d=pd.concat(fs,ignore_index=True); d["t"]=pd.to_datetime(d.t,unit="ms",utc=True); d=d[(d.t>=START)&(d.t<END)]
 for c in ["o","h","l","c","v","tb"]: d[c]=pd.to_numeric(d[c],errors="coerce")
 d=d.dropna().drop_duplicates("t").sort_values("t").reset_index(drop=True); d["imb"]=2*d.tb/d.v-1; return d

def ev(d,th,h,s):
 sig=np.where(d.imb>th,-1,np.where(d.imb<-th,1,0)); r=d.c.shift(-h)/d.o.shift(-1)-1
 return pd.DataFrame({"sig":sig,"net":sig*r-FEE[s]}).query("sig!=0").dropna()

oos=[]; finals=[]
for s in SYM:
 for iv in IV:
  d=load(s,iv)
  if len(d)<1000: continue
  fs=d.t.max()-timedelta(days=30); core=d[d.t<fs]; d0=core.t.min(); folds=[]
  for k in range(6):
   a=d0+timedelta(days=30*k); b=a+timedelta(days=120); c=b+timedelta(days=30)
   tr=core[(core.t>=a)&(core.t<b)]; te=core[(core.t>=b)&(core.t<c)]
   cand=[]
   for th in TH:
    for h in H[iv]:
     x=ev(tr,th,h,s); y=ev(te,th,h,s)
     if len(x)>=30 and len(y)>=10: cand.append((x.net.mean(),th,h,len(y),y.net.mean()))
   if cand:
    z=max(cand,key=lambda q:q[0]); folds.append([s,iv,k,z[1],z[2],z[3],z[4]]); oos.append(folds[-1])
  if not folds: continue
  q=pd.DataFrame(folds,columns=["s","iv","fold","th","h","n","net"]); a=q.groupby(["th","h"]).apply(lambda g:np.average(g.net,weights=g.n),include_groups=False).reset_index(name="oos_net"); ch=a.sort_values("oos_net",ascending=False).iloc[0]
  z=ev(d[d.t>=fs],float(ch.th),int(ch.h),s)
  finals.append([s,iv,float(ch.th),int(ch.h),len(z),z.net.mean() if len(z) else np.nan,z.net.sum() if len(z) else np.nan,fs,d.t.max()])
O=pd.DataFrame(oos,columns=["symbol","interval","fold","threshold","horizon","n","net"]); F=pd.DataFrame(finals,columns=["symbol","interval","threshold","horizon","n","final_mean","final_sum","final_start","final_end"])
O.to_csv(OUT/"v423_oos.csv",index=False); F.to_csv(OUT/"v423_final.csv",index=False)
Path(OUT/"summary_v423.md").write_text("# SCALP LAB V4.23 — TAKER-IMBALANCE HYPOTHESIS\n\n- New hypothesis: extreme taker-buy imbalance predicts short-horizon reversal.\n- Binance USD-M Futures klines; imbalance = 2*taker-buy-volume/volume - 1.\n- No VWAP, Donchian, breakout, pullback, RSI or regime filter.\n- Fixed grid: thresholds 0.20/0.30/0.40; horizons 3/6/12 bars.\n- Six chronological 120d TRAIN / 30d TEST folds. FINAL = last 30d and confirmation-only.\n- Round-trip cost estimates: BTC 0.12%, ETH 0.13%, SOL 0.16%.\n\n## OOS\n\n"+O.to_string(index=False)+"\n\n## FINAL\n\n"+F.to_string(index=False)+"\n",encoding="utf8")
print(F.to_string(index=False))