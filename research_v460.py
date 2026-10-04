import time,urllib.request,json,numpy as np,pandas as pd
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2025-10-01",tz="UTC");B=pd.Timestamp("2026-10-03",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];K=[.0003,.0006,.0010];H=32;C=.002
def load(s):
 u="https://fapi.binance.com/fapi/v1/fundingRate";rows=[];st=int(A.timestamp()*1000);en=int(B.timestamp()*1000)
 while st<en:
  q=json.load(urllib.request.urlopen(f"{u}?symbol={s}&startTime={st}&endTime={en}&limit=1000"))
  if not q:break
  rows+=q;st=int(q[-1]["fundingTime"])+1
  if len(q)<1000:break
  time.sleep(.1)
 return pd.DataFrame(rows).assign(t=lambda x:pd.to_datetime(x.fundingTime,unit="ms",utc=True),rate=lambda x:x.fundingRate.astype(float))[["t","rate"]]
def ev(d,k):
 r=d.set_index("t").rate.resample("8h").last().dropna();p=r.rolling(9).mean();s=np.where(r>k,-1,np.where(r<-k,1,0));a=[];i=9
 while i+H<len(p):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(p.iloc[ex]/p.iloc[en]-1)-C);i=ex
 x=np.array(a);return (float(x.sum()) if len(x) else np.nan,len(x))
# use BTC/ETH/SOL 1h close API for returns
def px(s):
 u="https://fapi.binance.com/fapi/v1/klines";q=[];st=int(A.timestamp()*1000);en=int(B.timestamp()*1000)
 while st<en:
  z=json.load(urllib.request.urlopen(f"{u}?symbol={s}&interval=8h&startTime={st}&endTime={en}&limit=1000"))
  if not z:break
  q+=z;st=z[-1][0]+1
  if len(z)<1000:break
 return pd.Series({pd.to_datetime(x[0],unit="ms",utc=True):float(x[4]) for x in q})
def ev2(f,c,k):
 r=f.set_index("t").rate.resample("8h").last().dropna();c=c.reindex(r.index,method="ffill");s=np.where(r>k,-1,np.where(r<-k,1,0));a=[];i=9
 while i+H<len(r):
  if not s[i]:i+=1;continue
  en=i+1;ex=en+H;a.append(s[i]*(c.iloc[ex]/c.iloc[en]-1)-C);i=ex
 x=np.array(a);return float(x.sum()) if len(x) else np.nan,len(x)
D={}
for s in SYM:D[s]=(load(s),px(s))
rows=[]
for s,(f,c) in D.items():
 for m in pd.date_range("2026-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=f[(f.t>=m-pd.DateOffset(months=3))&(f.t<m)];te=f[(f.t>=m)&(f.t<m+pd.DateOffset(months=1))]
  cc=c[(c.index>=m-pd.DateOffset(months=3))&(c.index<m+pd.DateOffset(months=1))]
  p=max(((k,ev2(tr,cc,k)[0]) for k in K),key=lambda x:x[1])[0];r,n=ev2(te,cc,p);rows.append([s,m.strftime("%Y-%m"),p,r,n])
df=pd.DataFrame(rows,columns=["symbol","month","selected_funding","oos_total","trades"]);df.to_csv(O/"v460_oos.csv",index=False);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();s=df.oos_total.sum()
(O/"summary_v460.md").write_text("# V4.60 — FUNDING CONTRARIAN WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {s:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}")
print(df.to_string(index=False),"\nBY_SYMBOL",g,"\nTOTAL",s,"POS_MONTHS",(w>0).sum(),"/",len(w))
