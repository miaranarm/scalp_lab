import zipfile,urllib.request,pandas as pd,numpy as np
from pathlib import Path
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2024-10-01",tz="UTC");B=pd.Timestamp("2026-10-04",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];K=[.0003,.0005,.0008,.0012];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  if m>=B.replace(day=1):continue
  u=f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m:%Y-%m}.zip";p="/tmp/"+u.rsplit("/",1)[-1]
  try:
   urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as z:
    x=pd.read_csv(z.open(z.namelist()[0]));x.columns=[str(c).lower() for c in x.columns];t=[c for c in x if "time" in c][0];r=[c for c in x if "rate" in c][-1];q.append(pd.DataFrame({"t":pd.to_datetime(x[t],unit="ms",utc=True),"f":pd.to_numeric(x[r],errors="coerce")}))
   Path(p).unlink(missing_ok=True)
  except Exception as e: print("MISS",s,m,type(e).__name__)
 return pd.concat(q).dropna().drop_duplicates("t").sort_values("t")
def ev(d,k,c):
 s=np.where(d.f>k,-1,np.where(d.f<-k,1,0));r=[];i=0
 while i+1<len(d):
  if not s[i]:i+=1;continue
  en=i;ex=min(i+1,len(d)-1);r.append(s[i]*(d.f.iloc[ex]-d.f.iloc[en])-c);i=ex
 return np.array(r)
rows=[]
for s in SYM:
 d=load(s)
 for m in pd.date_range("2025-01-01","2026-09-01",freq="MS",tz="UTC"):
  tr=d[(d.t>=m-pd.DateOffset(months=3))&(d.t<m)];te=d[(d.t>=m)&(d.t<m+pd.DateOffset(months=1))]
  p=max(((k,ev(tr,k,C[s]).sum()) for k in K),key=lambda z:z[1])[0];z=ev(te,p,C[s]);rows.append([s,m.strftime("%Y-%m"),p,z.sum(),len(z)])
df=pd.DataFrame(rows,columns=["symbol","month","threshold","oos_total","trades"]);g=df.groupby("symbol").oos_total.sum();w=df.groupby("month").oos_total.sum();t=df.oos_total.sum();df.to_csv(O/"v484_oos.csv",index=False);(O/"summary_v484.md").write_text("# V4.84 — FUNDING CONTRARIAN WALK FORWARD\n\n"+df.to_string(index=False)+f"\n\nBY_SYMBOL\n{g}\n\nBY_MONTH\n{w}\n\nTOTAL {t:.6f} POS_MONTHS {(w>0).sum()}/{len(w)}");print(df.to_string(index=False),"\nTOTAL",t)