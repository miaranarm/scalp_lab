import zipfile,urllib.request,numpy as np,pandas as pd
from pathlib import Path
SYM=["BTCUSDT","ETHUSDT","SOLUSDT"]; F={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
START=pd.Timestamp("2026-04-01",tz="UTC"); END=pd.Timestamp("2026-10-03",tz="UTC"); TH=[.2,.3,.4,.5]; H=[1,3,6]; LB=[1,3,6]
OUT=Path("results"); OUT.mkdir(exist_ok=True)
def src(s):
 m=START.replace(day=1)
 while m<=END:
  if m.year==END.year and m.month==END.month:
   d=m
   while d<=END.normalize():
    yield f"{s}-aggTrades-{d:%Y-%m-%d}.zip",f"https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d:%Y-%m-%d}.zip"; d+=pd.Timedelta(days=1)
  else: yield f"{s}-aggTrades-{m:%Y-%m}.zip",f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{s}/{s}-aggTrades-{m:%Y-%m}.zip"
  m+=pd.offsets.MonthBegin(1)
def load(s):
 z=[]
 for n,u in src(s):
  try:
   p="/tmp/"+n; urllib.request.urlretrieve(u,p)
   with zipfile.ZipFile(p) as f:
    a=[]
    for d in pd.read_csv(f.open(f.namelist()[0]),header=None,names=["id","price","qty","first","last","t","maker"],chunksize=500000):
     d["t"]=pd.to_datetime(pd.to_numeric(d.t,errors="coerce"),unit="ms",utc=True); d["price"]=pd.to_numeric(d.price,errors="coerce"); d["qty"]=pd.to_numeric(d.qty,errors="coerce"); d["maker"]=pd.to_numeric(d.maker,errors="coerce"); d=d.dropna(subset=["t","price","qty","maker"]); d["maker"]=d.maker.astype(bool); d=d[(d.t>=START)&(d.t<END)]
     if len(d):
      d["b"]=d.t.dt.floor("5min"); d["buy"]=np.where(~d.maker,d.qty,0.); d["sell"]=np.where(d.maker,d.qty,0.); a.append(d.groupby("b").agg(buy=("buy","sum"),sell=("sell","sum"),close=("price","last")))
    if a:z.append(pd.concat(a).groupby(level=0).agg({"buy":"sum","sell":"sum","close":"last"}))
   __import__("os").remove(p)
  except: pass
 d=pd.concat(z).groupby(level=0).agg({"buy":"sum","sell":"sum","close":"last"}).sort_index().reset_index(names="t"); d["imb"]=(d.buy-d.sell)/(d.buy+d.sell).replace(0,np.nan); return d
def ev(d,th,h,lb,mode,fee):
 ret=d.close.pct_change(lb); side=np.where((d.imb>th)&(ret>0 if mode=="MOM" else ret<0),1,np.where((d.imb<-th)&(ret<0 if mode=="MOM" else ret>0),-1,0)); r=d.close.shift(-h)/d.close-1; x=(pd.Series(side,index=d.index)*r-fee)[side!=0].dropna(); return (float(x.mean()),len(x),float(x.sum()))
R=[]; S=[]
for s in SYM:
 d0=load(s)
 for iv in ["5m","15m"]:
  d=d0 if iv=="5m" else d0.set_index("t").resample("15min").agg({"buy":"sum","sell":"sum","close":"last"}).dropna().reset_index(); d["imb"]=(d.buy-d.sell)/(d.buy+d.sell).replace(0,np.nan)
  tr=d[d.t<pd.Timestamp("2026-07-01",tz="UTC")]; te=d[(d.t>=pd.Timestamp("2026-07-01",tz="UTC"))&(d.t<pd.Timestamp("2026-09-01",tz="UTC"))]; ho=d[d.t>=pd.Timestamp("2026-09-01",tz="UTC")]
  for mode in ["MOM","CONTRA"]:
   sc={(t,h,l):ev(tr,t,h,l,mode,F[s])[2] for t in TH for h in H for l in LB}; t,h,l=max(sc,key=sc.get); a=ev(te,t,h,l,mode,F[s]); b=ev(ho,t,h,l,mode,F[s]); S.append([s,iv,mode,t,h,l,sc[(t,h,l)],*a,*b])
   for p,x in [("TRAIN",tr),("TEST",te),("HOLDOUT",ho)]:
    for tt in TH:
     for hh in H:
      for ll in LB:
       m=ev(x,tt,hh,ll,mode,F[s]); R.append([s,iv,p,mode,tt,hh,ll,*m])
q=pd.DataFrame(R,columns=["symbol","interval","period","mode","threshold","horizon","lookback","mean","trades","total"]); s=pd.DataFrame(S,columns=["symbol","interval","mode","threshold","horizon","lookback","train_total","test_mean","test_trades","test_total","holdout_mean","holdout_trades","holdout_total"]); q.to_csv(OUT/"v436_matrix.csv",index=False); s.to_csv(OUT/"v436_holdout.csv",index=False); Path(OUT/"summary_v436.md").write_text("# V4.36 — ORDER-FLOW + PRICE CONFIRMATION\n\n"+s.to_string(index=False)+"\n",encoding="utf8"); print(s.to_string(index=False))