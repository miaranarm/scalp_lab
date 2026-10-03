import os,zipfile,io,urllib.request
import numpy as np,pandas as pd

SYMS=["BTCUSDT","ETHUSDT","SOLUSDT"]; INTS=["5m","15m"]
THR=[1.5,2.0,2.5]; H=[1,3,6]; FEE={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
START="2025-10-01"; END="2026-10-03"

def load(s,iv):
    u=f"https://data.binance.vision/data/futures/um/daily/klines/{s}/{iv}"
    ds=pd.date_range(START,END,freq="D",inclusive="left"); a=[]
    for d in ds:
        z=f"{s}-{iv}-{d:%Y-%m-%d}.zip"
        try:
            b=urllib.request.urlopen(f"{u}/{z}",timeout=20).read()
            q=zipfile.ZipFile(io.BytesIO(b)).read(z[:-4]+".csv")
            x=pd.read_csv(io.BytesIO(q),header=None)
            x=x.iloc[:,:12]; x.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]
            x=x[pd.to_numeric(x.t,errors="coerce").notna()].copy()
            x.t=pd.to_datetime(pd.to_numeric(x.t),unit="ms",utc=True); x.c=pd.to_numeric(x.c); x.v=pd.to_numeric(x.v)
            a.append(x[["t","c","v"]])
        except: pass
    if not a: raise RuntimeError(f"no data {s} {iv}")
    return pd.concat(a).drop_duplicates("t").sort_values("t").reset_index(drop=True)

def score(d,t,h,fee):
    # abnormal quote volume proxy + candle direction; continuation only
    q=d.v.rolling(48).median()
    shock=d.v/q
    ret=d.c.pct_change()
    sig=(shock>=t)&(ret>0) | (shock>=t)&(ret<0)
    side=np.where(ret>0,1,-1)
    f=d.c.shift(-h)/d.c-1
    r=side*f-fee
    r=r[sig].dropna()
    return r.mean() if len(r) else np.nan,len(r)

os.makedirs("results",exist_ok=True); rows=[]; finals=[]
for s in SYMS:
 for iv in INTS:
    d=load(s,iv)
    cut=d.t.searchsorted(pd.Timestamp(START,tz="UTC")); end=d.t.searchsorted(pd.Timestamp(END,tz="UTC"))
    d=d.iloc[cut:end].reset_index(drop=True)
    fold=1500
    folds=[]
    p=0
    while p+fold+600<=len(d):
        tr=d.iloc[p:p+1200]; te=d.iloc[p+1200:p+1500]
        best=None
        for t in THR:
          for h in H:
            m,n=score(tr,t,h,FEE[s])
            if np.isfinite(m) and (best is None or m>best[0]): best=(m,t,h,n)
        m,n=score(te,best[1],best[2],FEE[s])
        rows.append([s,iv,p,best[1],best[2],m,n]); p+=300
    # final 30d: last 30d; selection only on prior 120d
    final_start=d.t.max()-pd.Timedelta(days=30)
    train=d[d.t<final_start].tail(1200); final=d[d.t>=final_start]
    best=None
    for t in THR:
      for h in H:
        m,n=score(train,t,h,FEE[s])
        if np.isfinite(m) and (best is None or m>best[0]): best=(m,t,h,n)
    m,n=score(final,best[1],best[2],FEE[s])
    finals.append([s,iv,best[1],best[2],m,n])
pd.DataFrame(rows,columns=["symbol","interval","fold","thr","h","oos_return","trades"]).to_csv("results/v426_oos.csv",index=False)
pd.DataFrame(finals,columns=["symbol","interval","thr","h","final_return","trades"]).to_csv("results/v426_final.csv",index=False)
o=pd.DataFrame(rows); f=pd.DataFrame(finals)
with open("results/summary_v426.md","w") as z:
 z.write("# V4.26 — Volume Shock Continuation\n\n")
 z.write("Independent hypothesis: abnormal volume relative to 48-bar median, with candle direction, predicts short-horizon continuation. Fixed thresholds 1.5/2/2.5 and horizons 1/3/6. TRAIN→TEST; final 30d untouched until confirmation. Costs included.\n\n")
 z.write("## OOS\n\n"+o.to_markdown(index=False)+"\n\n")
 z.write("## FINAL HOLDOUT\n\n"+f.to_markdown(index=False)+"\n\n")
 z.write(f"FINAL negative blocks: {(f.final_return<0).sum()}/{len(f)}\n")
