import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];LB=[4,8,12,24];H=[4,8,12];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/k.zip"
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),usecols=[0,4]);x.columns=["t","c"];q.append(x)
  except Exception as e:print("MISS",s,m.strftime("%Y-%m"),type(e).__name__)
 x=pd.concat(q).drop_duplicates("t").sort_values("t");x.t=pd.to_datetime(x.t,unit="ms",utc=True);x.c=pd.to_numeric(x.c,errors="coerce");return x.dropna()

D={s:load(s).set_index("t").c for s in SYM}
idx=D[SYM[0]].index.intersection(D[SYM[1]].index).intersection(D[SYM[2]].index)
X=pd.concat({s:D[s].reindex(idx) for s in SYM},axis=1).dropna()
rows=[]
for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
 tr=X[(X.index>=m-pd.DateOffset(months=3))&(X.index<m)];te=X[(X.index>=m)&(X.index<m+pd.DateOffset(months=1))]
 best=(-1e9,None)
 for lb in LB:
  rr=tr.pct_change(lb).shift(1)
  for h in H:
   r=tr.pct_change().rolling(h).sum().shift(-h)
   vals=[]
   for i in range(lb+1,len(tr)-h):
    q=rr.iloc[i].to_numpy(float)\n    if not np.isfinite(q).all(): continue\n    w,l=int(q.argmax()),int(q.argmin());vals.append((tr.iloc[i+h,w]/tr.iloc[i,w]-1)-(tr.iloc[i+h,l]/tr.iloc[i,l]-1)-C[SYM[w]]-C[SYM[l]])
   sc=np.nansum(vals)
   if sc>best[0]:best=(sc,(lb,h))
 lb,h=best[1];r=te.pct_change(lb).shift(1);z=[];i=lb+1
 while i+h<len(te):
  q=r.iloc[i].to_numpy(float)\n  if not np.isfinite(q).all(): i+=1; continue\n  w,l=int(q.argmax()),int(q.argmin());z.append((te.iloc[i+h,w]/te.iloc[i,w]-1)-(te.iloc[i+h,l]/te.iloc[i,l]-1)-C[SYM[w]]-C[SYM[l]]);i+=h
 rows.append([m.strftime("%Y-%m"),lb,h,np.nansum(z),len(z)])
df=pd.DataFrame(rows,columns=["month","lookback","hold_h","oos_total","trades"]);bm=df.groupby("month").oos_total.sum()
df.to_csv(O/"v487_oos.csv",index=False);(O/"summary_v487.md").write_text("# V4.87 — CROSS-SECTIONAL MOMENTUM\n\n"+df.to_string(index=False)+f"\n\nTOTAL {df.oos_total.sum():.6f} POS_MONTHS {(df.oos_total>0).sum()}/{len(df)} TRADES {df.trades.sum()}");print(df.to_string(index=False));print("TOTAL",df.oos_total.sum(),"POS_MONTHS",int((df.oos_total>0).sum()),"/",len(df),"TRADES",df.trades.sum())