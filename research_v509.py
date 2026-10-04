import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
O=Path("results");O.mkdir(exist_ok=True);A=pd.Timestamp("2020-01-01",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC");SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  try:
   z=urllib.request.urlopen(f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip",timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:q.append(pd.read_csv(f.open(f.namelist()[0]),header=None,usecols=range(6)))
  except:pass
 if not q:return pd.DataFrame()
 x=pd.concat(q,ignore_index=True).drop_duplicates().apply(pd.to_numeric,errors="coerce").dropna().sort_values(0);x.columns=["t","o","h","l","c","v"];x.t=pd.to_datetime(x.t,unit="ms",utc=True);return x.set_index("t")
DATA={}
for s in SYM:
 x=load(s)
 if x.empty:continue
 c=x.c;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);vx=tr.rolling(14).mean()/tr.rolling(14).mean().rolling(50).mean();sl=e50.pct_change(12);bull=(e50>e200)&(sl>0);sgs={}
 for th in [1.5,1.75]:
  sg=np.where((vx>th)&(c>e20)&bull,1,0);out=[];i=0;n=len(x)
  while i+49<n:
   if sg[i]==0:i+=1;continue
   r=(c.iloc[i+49]/x.o.iloc[i+1]-1)-C[s]*3;out.append([x.index[i],r]);i+=49
  DATA[s]=out
rows=[]
folds=[("2022-01","2023-07"),("2022-07","2024-01"),("2023-01","2024-07"),("2023-07","2025-01"),("2024-01","2025-07"),("2024-07","2026-01"),("2025-01","2026-07")]
for fs,te in folds:
 for th in [1.5,1.75]:
  rs=[]
  for s in SYM:
   x=load(s);c=x.c;e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean();tr=pd.concat([x.h-x.l,(x.h-c.shift()).abs(),(x.l-c.shift()).abs()],axis=1).max(axis=1);vx=tr.rolling(14).mean()/tr.rolling(14).mean().rolling(50).mean();sl=e50.pct_change(12);bull=(e50>e200)&(sl>0);sg=np.where((vx>th)&(c>e20)&bull,1,0);i=0;n=len(x)
   while i+49<n:
    if sg[i]==0:i+=1;continue
    t=x.index[i]
    if t>=pd.Timestamp(fs,tz="UTC") and t<pd.Timestamp(te,tz="UTC"):rs.append((c.iloc[i+49]/x.o.iloc[i+1]-1)-C[s]*3)
    i+=49
  a=np.array(rs);pf=a[a>0].sum()/abs(a[a<0].sum()) if (a<0).any() else np.nan;rows.append([fs,te,th,len(a),a.sum(),a.mean(),(a>0).mean(),pf])
R=pd.DataFrame(rows,columns=["train_end","test_end","threshold","trades","total","mean","win","pf"])
sel=[]
for te,g in R.groupby("test_end"):
 q=g[g.trades>=10].sort_values(["mean","pf"],ascending=False);sel.append(q.iloc[0].tolist() if len(q) else [None,te,None,0,0,0,0,np.nan])
S=pd.DataFrame(sel,columns=R.columns);md="# V5.09 WALK-FORWARD\n\nRolling threshold selection 1.5 vs 1.75; fixed 48h, BULL ETH/BTC/SOL, next-open, non-overlap, cost x3. Each test window is OOS to its preceding train concept.\n\n## ALL FOLDS\n"+R.to_string(index=False)+"\n\n## SELECTED OOS FOLDS\n"+S.to_string(index=False)+"\n";R.to_csv(O/"v509_folds.csv",index=False);S.to_csv(O/"v509_selected.csv",index=False);(O/"summary_v509.md").write_text(md);print(md)
