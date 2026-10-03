import io,zipfile,urllib.request
import numpy as np,pandas as pd

SYMS=["BTCUSDT","ETHUSDT","SOLUSDT"]; INTS=["5m","15m"]
START=pd.Timestamp("2025-10-01",tz="UTC"); END=pd.Timestamp("2026-10-01",tz="UTC")
FEE={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
H=[1,3,6]; Z=[1.0,1.5,2.0]
TRAIN=120; TEST=30

def load(s,iv):
 out=[]; d=START
 while d<END:
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/{iv}/{s}-{iv}-{d.year}-{d.month:02d}.zip"
  try:
   z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(u,timeout=60).read()))
   x=pd.read_csv(z.open(z.namelist()[0]),header=None).iloc[:,:12]
   x.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]
   x=x[pd.to_numeric(x.t,errors="coerce").notna()].copy()
   x["t"]=pd.to_datetime(pd.to_numeric(x.t),unit="ms",utc=True)
   for c in ["o","h","l","c"]: x[c]=pd.to_numeric(x[c],errors="coerce")
   out.append(x[["t","o","h","l","c"]])
  except: pass
  d=(d+pd.offsets.MonthBegin(1)).normalize()
 x=pd.concat(out).drop_duplicates("t").sort_values("t")
 return x[(x.t>=START)&(x.t<END)].reset_index(drop=True)

def feat(x):
 q=x.copy()
 q["tr"]=np.maximum(q.h-q.l,np.maximum(abs(q.h-q.c.shift()),abs(q.l-q.c.shift())))
 q["atr"]=q.tr.rolling(24).mean()
 q["mid"]=(q.h.rolling(20).max()+q.l.rolling(20).min())/2
 q["dev"]=(q.c-q.mid)/q.atr
 return q

def score(q,h,z,fee):
 r=q.c.shift(-h)/q.o-1
 s=np.where(q.dev>z,-1,np.where(q.dev<-z,1,0))
 n=s*r-fee*(s!=0)
 a=n[s!=0]
 return (float(np.nanmean(a)),int(len(a))) if len(a) else (np.nan,0)

def main():
 O=[];F=[]
 for s in SYMS:
  for iv in INTS:
   d=feat(load(s,iv)); hold=END-pd.Timedelta(days=30); cur=START+pd.Timedelta(days=TRAIN)
   while cur+pd.Timedelta(days=TEST)<=hold:
    tr=d[(d.t>=cur-pd.Timedelta(days=TRAIN))&(d.t<cur)]; te=d[(d.t>=cur)&(d.t<cur+pd.Timedelta(days=TEST))]
    b=None
    for h in H:
     for z in Z:
      sc,n=score(tr,h,z,FEE[s])
      if np.isfinite(sc) and (b is None or sc>b[0]): b=(sc,h,z)
    if b:
     sc,n=score(te,b[1],b[2],FEE[s]); O.append([s,iv,cur.date(),b[2],b[1],n,sc])
    cur+=pd.Timedelta(days=TEST)
   o=pd.DataFrame(O,columns=["symbol","interval","fold","z","horizon","n","net"])
   a=o[(o.symbol==s)&(o.interval==iv)]
   if len(a):
    g=a.groupby(["z","horizon"]).net.mean().sort_values(ascending=False); z,h=g.index[0]
    sc,n=score(d[d.t>=hold],h,z,FEE[s]); F.append([s,iv,z,h,n,sc])
 o=pd.DataFrame(O,columns=["symbol","interval","fold","z","horizon","n","net"])
 f=pd.DataFrame(F,columns=["symbol","interval","z","horizon","n","final_mean"])
 o.to_csv("results/v425_oos.csv",index=False); f.to_csv("results/v425_final.csv",index=False)
 open("results/summary_v425.md","w").write("# SCALP LAB V4.25 — VOLATILITY-NORMALIZED EXTREME\n\nIndependent hypothesis: price extremes normalized by recent true range mean revert.\n\nFixed z thresholds: 1/1.5/2 ATR; horizons 1/3/6 bars. Six chronological 120d TRAIN / 30d TEST folds. FINAL last 30d, confirmation only.\n\n## OOS\n\n"+(o.to_string(index=False) if len(o) else "NO RESULTS")+"\n\n## FINAL\n\n"+(f.to_string(index=False) if len(f) else "NO RESULTS"))
if __name__=="__main__": main()
