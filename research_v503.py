import io,zipfile,urllib.request
from pathlib import Path
import numpy as np,pandas as pd

O=Path("results");O.mkdir(exist_ok=True)
A=pd.Timestamp("2019-09-13",tz="UTC");B=pd.Timestamp("2026-10-01",tz="UTC")
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"];C={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
H=12;PATH=24

def load(s):
 q=[]
 for m in pd.date_range(A,B,freq="MS",tz="UTC"):
  u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m:%Y-%m}.zip"
  try:
   z=urllib.request.urlopen(u,timeout=30).read()
   with zipfile.ZipFile(io.BytesIO(z)) as f:
    x=pd.read_csv(f.open(f.namelist()[0]),usecols=[0,1,2,3,4,5]);q.append(x)
  except: pass
 if not q:return pd.DataFrame()
 x=pd.concat(q).drop_duplicates(0).sort_values(0);x.columns=["t","o","h","l","c","v"]
 x.t=pd.to_datetime(x.t,unit="ms",utc=True)
 return x.set_index("t").apply(pd.to_numeric,errors="coerce").dropna()

def features(x):
 c,h,l,o,v=x.c,x.h,x.l,x.o,x.v
 e20=c.ewm(span=20).mean();e50=c.ewm(span=50).mean();e200=c.ewm(span=200).mean()
 atr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1).rolling(14).mean()
 hi20=h.shift(1).rolling(20).max();lo20=l.shift(1).rolling(20).min()
 r=(c.diff().clip(lower=0).rolling(14).mean()/(-c.diff().clip(upper=0)).rolling(14).mean()).replace([np.inf],np.nan)
 rsi=100-100/(1+r)
 mid=c.rolling(20).mean();sd=c.rolling(20).std();z=(c-mid)/(2*sd)
 roc=c.pct_change(12)
 av=atr.rolling(50).mean();vx=atr/av
 vwap=(c*v).rolling(24).sum()/v.rolling(24).sum()
 slope=e50.pct_change(12)
 bull=(e50>e200)&(slope>0);bear=(e50<e200)&(slope<0);rng=~(bull|bear)
 return locals()

def signals(f):
 c=f["c"];s={}
 s["Breakout"]=np.where(c>f["hi20"],1,np.where(c<f["lo20"],-1,0))
 s["Donchian"]=s["Breakout"].copy()
 s["Pullback"]=np.where((f["e50"]>f["e200"])&(c<f["e20"])&(c>f["e50"]),1,np.where((f["e50"]<f["e200"])&(c>f["e20"])&(c<f["e50"]),-1,0))
 s["MeanReversion_RSI"]=np.where(f["rsi"]<30,1,np.where(f["rsi"]>70,-1,0))
 s["VWAP"]=np.where(c<f["vwap"]*.995,1,np.where(c>f["vwap"]*1.005,-1,0))
 s["Momentum"]=np.where(f["roc"]>.01,1,np.where(f["roc"]<-.01,-1,0))
 s["VolatilityExpansion"]=np.where((f["vx"]>1.5)&(c>f["e20"]),1,np.where((f["vx"]>1.5)&(c<f["e20"]),-1,0))
 s["TrendFollowing"]=np.where((f["e50"]>f["e200"])&(f["e50"].shift(1)<=f["e200"].shift(1)),1,np.where((f["e50"]<f["e200"])&(f["e50"].shift(1)>=f["e200"].shift(1)),-1,0))
 s["RangeTrading"]=np.where(f["z"]<-1,1,np.where(f["z"]>1,-1,0))
 s["Trend_Pullback"]=np.where((f["e50"]>f["e200"])&(c<f["e20"])&(c>f["e50"]),1,np.where((f["e50"]<f["e200"])&(c>f["e20"])&(c<f["e50"]),-1,0))
 s["Breakout_VolExp"]=np.where((c>f["hi20"])&(f["vx"]>1.25),1,np.where((c<f["lo20"])&(f["vx"]>1.25),-1,0))
 s["RSI_Range"]=np.where(f["rng"]&(f["rsi"]<30),1,np.where(f["rng"]&(f["rsi"]>70),-1,0))
 return s

def regime(f,i):
 return "bull" if bool(f["bull"].iloc[i]) else ("bear" if bool(f["bear"].iloc[i]) else "range")

def events(x,f,sig,sym,fam):
 c,h,l=x.c.values,x.h.values,x.l.values
 out=[];n=len(x)
 for i in np.flatnonzero(sig):
  if i+PATH>=n:continue
  d=int(sig[i]);entry=c[i]
  path=np.array([(c[i+k]/entry-1)*d for k in range(1,PATH+1)])
  hi=np.max([(h[i+k]/entry-1)*d for k in range(1,PATH+1)])
  lo=np.min([(l[i+k]/entry-1)*d for k in range(1,PATH+1)])
  r12=(c[i+H]/entry-1)*d
  out.append([x.index[i],sym,fam,d,regime(f,i),r12,hi,lo])
 return out

ALL=[];TR=[]
for s in SYM:
 x=load(s)
 if x.empty:continue
 f=features(x);ss=signals(f)
 for fam,sg in ss.items():
  ev=events(x,f,sg,s,fam)
  ALL+=ev
  for costmult in [1,1.5,2]:
   for e in ev:
    net=e[5]-C[s]*costmult
    TR.append(e+[costmult,net])
E=pd.DataFrame(ALL,columns=["time","symbol","family","side","regime","gross12h","mfe24h","mae24h"])
T=pd.DataFrame(TR,columns=list(E.columns)+["cost_mult","net12h"])
T["year"]=pd.to_datetime(T.time).dt.year;T["month"]=pd.to_datetime(T.time).dt.to_period("M").astype(str)
def stats(g):
 r=g.net12h.dropna();w=r[r>0];l=r[r<0]
 eq=r.cumsum();dd=eq-eq.cummax()
 return pd.Series({"trades":len(r),"total_return":r.sum(),"return_trade":r.mean(),"win_rate":(r>0).mean(),"profit_factor":w.sum()/abs(l.sum()) if len(l) else np.nan,"max_drawdown":dd.min(),"sharpe":r.mean()/r.std()*np.sqrt(24*365) if r.std() else np.nan,"positive_months":g.groupby("month").net12h.sum().gt(0).sum(),"positive_years":g.groupby("year").net12h.sum().gt(0).sum()})
S=T.groupby(["cost_mult","family"]).apply(stats).reset_index()
R=T.groupby(["cost_mult","family","symbol"]).apply(stats).reset_index()
G=T.groupby(["cost_mult","family","regime"]).apply(stats).reset_index()
E.to_csv(O/"meta_signal_path_events.csv",index=False);S.to_csv(O/"meta_family.csv",index=False);R.to_csv(O/"meta_symbol.csv",index=False);G.to_csv(O/"meta_regime.csv",index=False)
rank=S[S.cost_mult==1].sort_values(["profit_factor","sharpe"],ascending=False)
(S.sort_values(["cost_mult","profit_factor"],ascending=[True,False]).to_string(index=False)).replace("nan","NA")
md="# V5.03 META-SCAN — SIGNAL → PATH → RESULT\n\nBinance USD-M 1h, BTC/ETH/SOL, earliest available → 2026-09-30. Fixed 12h outcome; 24h MFE/MAE path. No parameter optimization.\n\n## FAMILY RANKING\n\n"+S.sort_values(["cost_mult","profit_factor"],ascending=[True,False]).to_string(index=False)+"\n\n## SYMBOL\n\n"+R.to_string(index=False)+"\n\n## REGIME\n\n"+G.to_string(index=False)+"\n"
(O/"summary_v503.md").write_text(md);print(md[:12000])