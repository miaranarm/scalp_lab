import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC");CUT=pd.Timestamp("2026-08-20",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};H=4
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1];urllib.request.urlretrieve(u,p)
  with zipfile.ZipFile(p) as z:
   x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,2,3,4]);x.columns=["t","h","l","c"];q.append(x)
  Path(p).unlink(missing_ok=True)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),**{k:lambda x,k=k:x[k].astype(float) for k in "hlc"}).drop_duplicates("t").sort_values("t")
def ev(d,cost):
 x=d.set_index("t");atr=(x.h-x.l).rolling(24).mean();r=x.c.pct_change();s=np.where(r>2*atr/x.c.shift(1),-1,np.where(r<-2*atr/x.c.shift(1),1,0));a=[];i=24
 while i+H+1<len(x):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(x.c.iloc[ex]/x.c.iloc[en]-1)-cost);i=ex
 return np.array(a)
D={s:load(s) for s in SYM};monthly={}
for s,d in D.items():
 for m in pd.date_range("2026-05-01","2026-08-01",freq="MS",tz="UTC"):
  z=ev(d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))],C[s]);monthly[s,m.strftime("%Y-%m")]=z.sum()
sel=[s for s in SYM if sum(monthly.get((s,(CUT-pd.DateOffset(months=i)).strftime("%Y-%m")),0) for i in [1,2,3])>0]
rows=[];total=0
for s in sel:
 z=ev(D[s][D[s].t>=CUT],C[s]);v=z.sum();rows.append([s,v,len(z)]);total+=v
df=pd.DataFrame(rows,columns=["symbol","holdout_total","trades"]);df.to_csv(O/"v480_holdout.csv",index=False);(O/"summary_v480.md").write_text("# V4.80 — WINNER FILTER FINAL HOLDOUT\n\nSELECTED "+",".join(sel)+f"\n\n"+df.to_string(index=False)+f"\n\nTOTAL {total:.6f} POS_SYMBOLS {(df.holdout_total>0).sum()}/{len(df)}");print("SELECTED",sel,"\n",df,"\nTOTAL",total)