import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];K=[1.5,2,2.5];H=8;C=.002
def load(s,kind):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/{kind}/{s}/1h/{s}-1h-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]),header=0,usecols=[0,4]);x.columns=["t","v"];q.append(x)
   Path(p).unlink(missing_ok=True)
  except Exception as e:print("MISS",kind,s,m,type(e).__name__)
 return pd.concat(q).assign(t=lambda x:pd.to_datetime(x.t,unit="ms",utc=True),v=lambda x:x.v.astype(float)).drop_duplicates("t").sort_values("t")
def ev(p,c,k):
 z=(p-p.rolling(24).mean())/p.rolling(24).std();s=np.where(z>k,-1,np.where(z<-k,1,0));a=[];i=24
 while i+H+1<len(c):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(c.iloc[ex]/c.iloc[en]-1)-C);i=ex
 q=np.array(a);return float(q.sum()) if len(q) else np.nan,len(q)
rows=[]
for s in SYM:
 p=load(s,"premiumIndexKlines");c=load(s,"klines")
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  trp=p[(p.t>=m-pd.DateOffset(months=3))&(p.t<m)];tep=p[(p.t>=m)&(p.t<m+pd.DateOffset(months=1))]
  cc=c.set_index("t").v
  ctr=cc.reindex(trp.t,method="ffill");cte=cc.reindex(tep.t,method="ffill")
  psel=max(((k,ev(trp.v,ctr,k)[0]) for k in K),key=lambda x:x[1])[0];r,n=ev(tep.v,cte,psel);rows.append([s,m.strftime("%Y-%m"),psel,r,n])
df=pd.DataFrame(rows,columns=["symbol","month","selected_z","oos_total","trades"]);df.to_csv(O/"v460_oos.csv",index=False);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum()
(O/"summary_v460.md").write_text("# V4.60 — PREMIUM INDEX CONTRARIAN WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}")
print(df.to_string(index=False),"\nBY_SYMBOL",g,"\nTOTAL",s,"POS_MONTHS",(w>0).sum(),"/",len(w))