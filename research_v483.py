import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2025-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];BASE={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016};H=4;MULT=[1,1.25,1.5,2]
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
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
D={s:load(s) for s in SYM};rows=[]
for mult in MULT:
 cost={s:BASE[s]*mult for s in SYM};monthly={}
 for s,d in D.items():
  for m in pd.date_range("2024-12-01","2025-09-01",freq="MS",tz="UTC"):
   monthly[s,m.strftime("%Y-%m")]=ev(d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))],cost[s]).sum()
 for m in pd.date_range("2025-01-01","2025-09-01",freq="MS",tz="UTC"):
  key=m.strftime("%Y-%m");prev=[(m-pd.DateOffset(months=i)).strftime("%Y-%m") for i in [1,2,3]]
  sel=[s for s in SYM if sum(monthly.get((s,p),0) for p in prev)>0]
  z=sum(ev(D[s][(D[s].t>=m)&(D[s].t<m+pd.DateOffset(months=1))],cost[s]).sum() for s in sel)
  rows.append([key,mult,",".join(sel) or "NONE",z])
df=pd.DataFrame(rows,columns=["month","cost_mult","selected_symbols","oos_total"]);g=df.groupby("cost_mult").oos_total.sum();df.to_csv(O/"v483_oos.csv",index=False);(O/"summary_v483.md").write_text("# V4.83 — V4.79 2025 EXTERNAL HOLDOUT\n\n"+df.to_string(index=False)+f"\n\nTOTAL_BY_COST\n{g}\n\nPOS_MONTHS\n"+str(df.groupby("cost_mult").oos_total.apply(lambda x:f"{(x>0).sum()}/{len(x)}")));print(df.to_string(index=False),"\n",g)
