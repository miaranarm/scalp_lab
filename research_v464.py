import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];PAIRS=[("BTCUSDT","ETHUSDT"),("ETHUSDT","SOLUSDT")];K=[1.5,2,2.5];W=96;H=12;C=.004
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,4]);x.columns=["t","close"];q.append(x)
   Path(p).unlink(missing_ok=True)
  except Exception as e:print("MISS",s,m,type(e).__name__)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),close=lambda x:x.close.astype(float)).drop_duplicates("t").sort_values("t")
D={s:load(s).set_index("t").close for s in SYM};X=pd.concat(D,axis=1).dropna()
def ev(d,k):
 z=(np.log(d.iloc[:,0]/d.iloc[:,1])-np.log(d.iloc[:,0]/d.iloc[:,1]).rolling(W).mean())/np.log(d.iloc[:,0]/d.iloc[:,1]).rolling(W).std();s=np.where(z>k,-1,np.where(z<-k,1,0));a=[];i=W
 while i+H+1<len(d):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*((d.iloc[ex,0]/d.iloc[en,0]-1)-(d.iloc[ex,1]/d.iloc[en,1]-1))-C);i=ex
 q=np.array(a);return float(q.sum()) if len(q) else np.nan,len(q)
rows=[]
for pa,pb in PAIRS:
 d=X[[pa,pb]]
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.index>=m-pd.DateOffset(months=3))&(d.index<m)];te=d[(d.index>=m)&(d.index<m+pd.DateOffset(months=1))]
  p=max(((k,ev(tr,k)[0]) for k in K),key=lambda x:x[1])[0];r,n=ev(te,p);rows.append([pa+"/"+pb,m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(rows,columns=["pair","month","selected_z","oos_total","trades"]);df.to_csv(O/"v464_oos.csv",index=False);g=df.groupby("pair").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum();(O/"summary_v464.md").write_text("# V4.64 — PAIR TRADING WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_PAIR\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}");print(df.to_string(index=False),"\nBY_PAIR",g,"\nTOTAL",s)