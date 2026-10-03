import io,os,zipfile,urllib.request,numpy as np,pandas as pd
S=["BTCUSDT","ETHUSDT","SOLUSDT"]; I=["5m","15m"]; CFG={"BTCUSDT":(96,1.5,3),"ETHUSDT":(24,1.0,3),"SOLUSDT":(96,1.5,6)}; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
A=pd.Timestamp("2025-10-01",tz="UTC"); B=pd.Timestamp("2026-10-03",tz="UTC")
def load(s,iv):
 out=[]; u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/{iv}"
 for m in pd.date_range(A,B,freq="MS"):
  n=f"{s}-{iv}-{m:%Y-%m}.zip"
  try:
   z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(f"{u}/{n}",timeout=60).read())); d=pd.read_csv(io.BytesIO(z.read(z.namelist()[0])),header=None).iloc[:,:12]
   d.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]; d=d[pd.to_numeric(d.t,errors="coerce").notna()].copy(); d["t"]=pd.to_datetime(pd.to_numeric(d.t),unit="ms",utc=True)
   for c in ["h","l","c"]: d[c]=pd.to_numeric(d[c])
   out.append(d[["t","h","l","c"]])
  except Exception as e: print("SKIP",n,type(e).__name__)
 return pd.concat(out).drop_duplicates("t").sort_values("t").reset_index(drop=True)
def eval(d,w,k,h,fee):
 rng=d.h.rolling(w,min_periods=w).max()-d.l.rolling(w,min_periods=w).min(); base=rng.rolling(w,min_periods=w).median(); comp=rng<base*k
 hi=d.h.rolling(w,min_periods=w).max().shift(1); lo=d.l.rolling(w,min_periods=w).min().shift(1)
 side=np.where(comp&(d.c>hi),1,np.where(comp&(d.c<lo),-1,0)); fut=d.c.shift(-h)/d.c-1
 x=(pd.Series(side,index=d.index)*fut-fee)[side!=0].dropna()
 return (x.mean(),len(x),x.sum()) if len(x) else (np.nan,0,np.nan)
def md(df):
 return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n"+"\n".join("| "+" | ".join(str(x) for x in row)+" |" for row in df.itertuples(index=False,name=None))
os.makedirs("results",exist_ok=True); R=[]
for s in S:
 for iv in I:
  d=load(s,iv); w,k,h=CFG[s]; step=30 if iv=="15m" else 60
  for end in pd.date_range(pd.Timestamp("2026-04-01",tz="UTC"),pd.Timestamp("2026-10-01",tz="UTC"),freq="30D"):
   st=end-pd.Timedelta(days=30); x=d[(d.t>=st)&(d.t<end)].copy()
   m,n,total=eval(x,w,k,h,F[s]); bench=(x.c.iloc[-1]/x.c.iloc[0]-1-F[s]) if len(x)>1 else np.nan
   R.append([s,iv,st.date(),end.date(),w,k,h,m,n,total,bench])
q=pd.DataFrame(R,columns=["symbol","interval","start","end","window","compression","h","signal_mean","trades","signal_total","buyhold_net"])
q.to_csv("results/v431_robustness.csv",index=False)
with open("results/summary_v431.md","w") as z:
 z.write("# V4.31 — Robustness Audit of V4.30\n\nNo parameter selection. Fixed configurations from V4.30 FINAL: BTC 96/1.5/3, ETH 24/1.0/3, SOL 96/1.5/6. Tests rolling 30-day blocks from Apr-Oct 2026, plus net buy-and-hold benchmark.\n\n"+md(q)+"\n\nPositive blocks: "+str((q.signal_total>0).sum())+"/"+str(len(q))+"\n")
