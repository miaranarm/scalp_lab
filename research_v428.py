import io,os,zipfile,urllib.request,numpy as np,pandas as pd
S=["BTCUSDT","ETHUSDT","SOLUSDT"]; I=["5m","15m"]; W=[12,24,48]; H=[1,3,6]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
A=pd.Timestamp("2025-10-01",tz="UTC"); B=pd.Timestamp("2026-10-03",tz="UTC")
def load(s,iv):
 out=[]; u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/{iv}"
 for m in pd.date_range(A,B,freq="MS"):
  n=f"{s}-{iv}-{m:%Y-%m}.zip"
  try:
   z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(f"{u}/{n}",timeout=60).read())); d=pd.read_csv(io.BytesIO(z.read(z.namelist()[0])),header=None).iloc[:,:12]
   d.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]; d=d[pd.to_numeric(d.t,errors="coerce").notna()].copy()
   d["t"]=pd.to_datetime(pd.to_numeric(d.t),unit="ms",utc=True)
   for c in ["o","h","l","c"]: d[c]=pd.to_numeric(d[c])
   out.append(d[["t","o","h","l","c"]])
  except Exception as e: print("SKIP",n,type(e).__name__)
 if not out: raise RuntimeError("no data")
 return pd.concat(out).drop_duplicates("t").sort_values("t").reset_index(drop=True)
def sc(d,w,h,fee):
 mid=(d.h+d.l)/2; sd=((d.h-d.l).rolling(w,min_periods=w).std()); dev=(d.c-mid)/sd.replace(0,np.nan)
 z=dev.rolling(w,min_periods=w).mean(); side=np.sign(z)
 fut=d.c.shift(-h)/d.c-1; x=(side*fut-fee)[side.ne(0)].dropna()
 return (x.mean(),len(x)) if len(x) else (np.nan,0)
def md(df):
 return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join("| "+" | ".join(str(x) for x in row)+" |" for row in df.itertuples(index=False,name=None))
os.makedirs("results",exist_ok=True); O=[]; Q=[]
for s in S:
 for iv in I:
  d=load(s,iv); d=d[(d.t>=A)&(d.t<B)].reset_index(drop=True)
  for p in range(0,max(0,len(d)-1500),300):
   tr=d.iloc[p:p+1200]; te=d.iloc[p+1200:p+1500]; best=max(((sc(tr,w,h,F[s])[0],w,h) for w in W for h in H),key=lambda x:-np.inf if not np.isfinite(x[0]) else x[0]); m,n=sc(te,best[1],best[2],F[s]); O.append([s,iv,p,best[1],best[2],m,n])
  fs=d.t.max()-pd.Timedelta(days=30); tr=d[d.t<fs].tail(1200); te=d[d.t>=fs]; best=max(((sc(tr,w,h,F[s])[0],w,h) for w in W for h in H),key=lambda x:-np.inf if not np.isfinite(x[0]) else x[0]); m,n=sc(te,best[1],best[2],F[s]); Q.append([s,iv,best[1],best[2],m,n])
o=pd.DataFrame(O,columns=["symbol","interval","fold","window","h","oos_return","trades"]); q=pd.DataFrame(Q,columns=["symbol","interval","window","h","final_return","trades"])
o.to_csv("results/v428_oos.csv",index=False); q.to_csv("results/v428_final.csv",index=False)
with open("results/summary_v428.md","w") as z:
 z.write("# V4.28 — Volatility-Normalized Displacement\n\nRolling standardized close displacement from candle midpoint. Fixed windows 12/24/48 and horizons 1/3/6. Chronological TRAIN/TEST; final 30d confirmation-only.\n\n## FINAL HOLDOUT\n\n"+md(q)+"\n\nFINAL negative blocks: "+str((q.final_return<0).sum())+"/"+str(len(q))+"\n\n## OOS folds\n\n"+md(o)+"\n")
