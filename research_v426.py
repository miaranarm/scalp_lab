import io,os,zipfile,urllib.request
import numpy as np,pandas as pd

S=["BTCUSDT","ETHUSDT","SOLUSDT"]; I=["5m","15m"]
TH=[1.5,2,2.5]; H=[1,3,6]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
A=pd.Timestamp("2025-10-01",tz="UTC"); B=pd.Timestamp("2026-10-03",tz="UTC")

def load(s,iv):
 u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/{iv}"
 out=[]
 for m in pd.date_range(A,B,freq="MS"):
  n=f"{s}-{iv}-{m:%Y-%m}.zip"
  try:
   b=urllib.request.urlopen(f"{u}/{n}",timeout=60).read()
   z=zipfile.ZipFile(io.BytesIO(b)); q=z.read(z.namelist()[0])
   d=pd.read_csv(io.BytesIO(q),header=None).iloc[:,:12]
   d.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]
   d=d[pd.to_numeric(d.t,errors="coerce").notna()].copy()
   d["t"]=pd.to_datetime(pd.to_numeric(d.t),unit="ms",utc=True)
   d["c"]=pd.to_numeric(d.c); d["v"]=pd.to_numeric(d.v)
   out.append(d[["t","c","v"]])
  except Exception as e: print("SKIP",n,type(e).__name__)
 if not out: raise RuntimeError(f"no data {s} {iv}")
 return pd.concat(out).drop_duplicates("t").sort_values("t").reset_index(drop=True)

def sc(d,t,h,fee):
 med=d.v.rolling(48,min_periods=48).median()
 shock=d.v/med; r=d.c.pct_change()
 sig=shock>=t
 side=np.sign(r)
 fut=d.c.shift(-h)/d.c-1
 x=(side*fut-fee)[sig & side.ne(0)].dropna()
 return (x.mean(),len(x)) if len(x) else (np.nan,0)

os.makedirs("results",exist_ok=True); O=[]; Q=[]
for s in S:
 for iv in I:
  d=load(s,iv); d=d[(d.t>=A)&(d.t<B)].reset_index(drop=True)
  for p in range(0,max(0,len(d)-1500),300):
   tr=d.iloc[p:p+1200]; te=d.iloc[p+1200:p+1500]
   best=max(((sc(tr,t,h,F[s])[0],t,h) for t in TH for h in H),key=lambda x:-np.inf if not np.isfinite(x[0]) else x[0])
   m,n=sc(te,best[1],best[2],F[s]); O.append([s,iv,p,best[1],best[2],m,n])
  fs=d.t.max()-pd.Timedelta(days=30); tr=d[d.t<fs].tail(1200); te=d[d.t>=fs]
  best=max(((sc(tr,t,h,F[s])[0],t,h) for t in TH for h in H),key=lambda x:-np.inf if not np.isfinite(x[0]) else x[0])
  m,n=sc(te,best[1],best[2],F[s]); Q.append([s,iv,best[1],best[2],m,n])
o=pd.DataFrame(O,columns=["symbol","interval","fold","thr","h","oos_return","trades"])
q=pd.DataFrame(Q,columns=["symbol","interval","thr","h","final_return","trades"])
o.to_csv("results/v426_oos.csv",index=False); q.to_csv("results/v426_final.csv",index=False)

def md(df):
 return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join("| "+" | ".join(str(x) for x in row)+" |" for row in df.itertuples(index=False,name=None))
with open("results/summary_v426.md","w") as z:
 z.write("# V4.26 — Volume Shock Continuation\n\n")
 z.write("Abnormal base volume versus 48-bar median + candle direction. Fixed thresholds 1.5/2/2.5, horizons 1/3/6. Chronological TRAIN/TEST; final 30d confirmation-only.\n\n")
 z.write("## FINAL HOLDOUT\n\n"+md(q)+"\n\n")
 z.write(f"FINAL negative blocks: {(q.final_return<0).sum()}/{len(q)}\n\n")
 z.write("## OOS folds\n\n"+md(o)+"\n")
