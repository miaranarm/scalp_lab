import io,os,zipfile,urllib.request,numpy as np,pandas as pd
S=["BTCUSDT","ETHUSDT","SOLUSDT"]; I=["5m","15m"]
F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
A=pd.Timestamp("2025-10-01",tz="UTC"); B=pd.Timestamp("2026-10-03",tz="UTC")
COMB=["VOL+CLV","VOL+DISP","COMP+VOL","COMP+DISP","VOL+CLV+DISP","COMP+VOL+DISP"]
def load(s,iv):
 out=[]; u=f"https://data.binance.vision/data/futures/um/monthly/klines/{s}/{iv}"
 for m in pd.date_range(A,B,freq="MS"):
  n=f"{s}-{iv}-{m:%Y-%m}.zip"
  try:
   z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(f"{u}/{n}",timeout=60).read()))
   d=pd.read_csv(io.BytesIO(z.read(z.namelist()[0])),header=None).iloc[:,:12]
   d=d[pd.to_numeric(d.iloc[:,0],errors="coerce").notna()].copy()
   d.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]
   d["t"]=pd.to_datetime(pd.to_numeric(d.t),unit="ms",utc=True)
   for c in ["o","h","l","c","v"]: d[c]=pd.to_numeric(d[c])
   out.append(d[["t","o","h","l","c","v"]])
  except Exception as e: print("SKIP",n,type(e).__name__)
 return pd.concat(out).drop_duplicates("t").sort_values("t").reset_index(drop=True)
def sig(d,combo):
 c=d.c; h=d.h; l=d.l; v=d.v
 vs=v/v.rolling(48,min_periods=48).median()>2
 clv=((2*c-h-l)/(h-l).replace(0,np.nan)).rolling(24,min_periods=24).mean()
 clvS=np.sign(clv)
 disp=(c-(h+l)/2)/(h-l).replace(0,np.nan)
 ds=np.sign(disp.rolling(24,min_periods=24).mean())
 z=(c-c.rolling(48,min_periods=48).mean())/c.rolling(48,min_periods=48).std()
 mr=np.where(z>2.5,-1,np.where(z<-2.5,1,0))
 rng=h.rolling(96,min_periods=96).max()-l.rolling(96,min_periods=96).min()
 base=rng.rolling(96,min_periods=96).median()
 comp=rng<base*1.5
 hi=h.rolling(96,min_periods=96).max().shift(1); lo=l.rolling(96,min_periods=96).min().shift(1)
 br=np.where(comp&(c>hi),1,np.where(comp&(c<lo),-1,0))
 vol=np.where(vs,np.sign(c-c.shift(1)),0)
 cl=np.where(vs,clvS,0); di=np.where(vs,ds,0)
 if combo=="VOL+CLV": return np.where((vol!=0)&(np.sign(cl)==vol),vol,0)
 if combo=="VOL+DISP": return np.where((vol!=0)&(np.sign(di)==vol),vol,0)
 if combo=="COMP+VOL": return np.where((br!=0)&(vol==br),br,0)
 if combo=="COMP+DISP": return np.where((br!=0)&(di==br),br,0)
 if combo=="VOL+CLV+DISP": return np.where((vol!=0)&(np.sign(cl)==vol)&(np.sign(di)==vol),vol,0)
 return np.where((br!=0)&(vol==br)&(di==br),br,0)
def ev(d,combo,h,fee):
 s=sig(d,combo); fut=d.c.shift(-h)/d.c-1
 x=pd.Series(s,index=d.index)*fut-fee
 x=x[s!=0].dropna()
 return (float(x.mean()),len(x),float(x.sum())) if len(x) else (np.nan,0,np.nan)
def row(s,iv,combo,period,d):
 m,n,t=ev(d,combo,1 if iv=="5m" else 1,F[s]); return [s,iv,combo,period,m,n,t]
os.makedirs("results",exist_ok=True); R=[]; H=[]
for s in S:
 for iv in I:
  d=load(s,iv); fee=F[s]
  cuts=[pd.Timestamp("2026-03-01",tz="UTC"),pd.Timestamp("2026-07-01",tz="UTC"),pd.Timestamp("2026-08-16",tz="UTC"),pd.Timestamp("2026-09-03",tz="UTC")]
  train=d[d.t<cuts[1]].copy(); test=d[(d.t>=cuts[1])&(d.t<cuts[2])].copy(); hold=d[(d.t>=cuts[2])&(d.t<cuts[3])].copy()
  scores={c:ev(train,c,1,fee)[2] for c in COMB}; best=max(scores,key=scores.get)
  tm=ev(test,best,1,fee); hm=ev(hold,best,1,fee)
  H.append([s,iv,best,scores[best],tm[0],tm[1],tm[2],hm[0],hm[1],hm[2]])
  for c in COMB:
   for p,x in [("TRAIN",train),("TEST",test),("HOLDOUT",hold)]: R.append(row(s,iv,c,p,x))
q=pd.DataFrame(R,columns=["symbol","interval","combo","period","mean","trades","total"])
h=pd.DataFrame(H,columns=["symbol","interval","selected","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"])
q.to_csv("results/v432_matrix.csv",index=False); h.to_csv("results/v432_holdout.csv",index=False)
def md(df):
 return "| "+" | ".join(df.columns)+" |\n| "+" | ".join(["---"]*len(df.columns))+" |\n" + "\n".join("| "+" | ".join(str(x) for x in r)+" |" for r in df.itertuples(index=False,name=None))
with open("results/summary_v432.md","w") as f:
 f.write("# V4.32 — Multi-Factor Interaction Audit\n\nFixed predefined combinations. TRAIN selects one combination per symbol/interval; TEST is OOS; HOLDOUT is confirmation only. No parameter tuning.\n\n## Selected configurations\n\n"+md(h)+"\n\n## Full matrix\n\n"+md(q))
