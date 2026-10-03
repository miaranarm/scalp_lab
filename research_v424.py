import io,zipfile,urllib.request,calendar
from datetime import datetime,timedelta,timezone
import numpy as np,pandas as pd

SYMS=["BTCUSDT","ETHUSDT","SOLUSDT"]; INTS=["5m","15m"]
START=pd.Timestamp("2025-10-01",tz="UTC"); END=pd.Timestamp("2026-10-01",tz="UTC")
FEE={"BTCUSDT":.0012,"ETHUSDT":.0013,"SOLUSDT":.0016}
H=[1,3,6]; TH=[0.0,.0002,.0004,.0008]
DAYS_TRAIN=120; DAYS_TEST=30

def load(sym,iv):
    out=[]; d=START.normalize()
    while d<END:
        y,m=d.year,d.month
        u=f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/{iv}/{sym}-{iv}-{y}-{m:02d}.zip"
        try:
            b=urllib.request.urlopen(u,timeout=60).read()
            z=zipfile.ZipFile(io.BytesIO(b))
            n=z.namelist()[0]
            x=pd.read_csv(z.open(n),header=None)
            x=x.iloc[:,:12]; x.columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","x"]
            x=x[pd.to_numeric(x.t,errors="coerce").notna()].copy()
            x["t"]=pd.to_datetime(pd.to_numeric(x.t),unit="ms",utc=True)
            out.append(x[["t","o","c"]])
        except Exception: pass
        d=(d+pd.offsets.MonthBegin(1)).normalize()
    if not out: return pd.DataFrame()
    x=pd.concat(out,ignore_index=True).drop_duplicates("t").sort_values("t")
    x=x[(x.t>=START)&(x.t<END)].copy()
    x["o"]=pd.to_numeric(x.o,errors="coerce"); x["c"]=pd.to_numeric(x.c,errors="coerce")
    x["r"]=x.c.shift(-1)/x.o-1
    return x.dropna(subset=["r"])

def fit(train,h,th):
    y=train.c.shift(-h)/train.o-1
    q=train.copy(); q["y"]=y
    q["hr"]=q.t.dt.hour
    m=q.groupby("hr").y.mean()
    return m

def score(test,h,th,m,fee):
    q=test.copy(); q["hr"]=q.t.dt.hour
    mu=q.hr.map(m).fillna(0.0)
    s=np.where(mu>th,1,np.where(mu<-th,-1,0))
    y=q.c.shift(-h)/q.o-1
    net=s*y-fee*(s!=0)
    return float(np.nanmean(net[s!=0])) if np.any(s!=0) else np.nan, int(np.sum(s!=0))

def main():
    os=[]
    finals=[]
    for sym in SYMS:
      for iv in INTS:
        d=load(sym,iv)
        if len(d)<1000: continue
        last30=END-pd.Timedelta(days=30)
        train0=START+pd.Timedelta(days=DAYS_TRAIN)
        folds=[]
        cur=train0
        while cur+pd.Timedelta(days=DAYS_TEST)<=last30:
            tr=d[(d.t>=cur-pd.Timedelta(days=DAYS_TRAIN))&(d.t<cur)]
            te=d[(d.t>=cur)&(d.t<cur+pd.Timedelta(days=DAYS_TEST))]
            best=None
            for h in H:
              for th in TH:
                m=fit(tr,h,th)
                sc,n=score(tr,h,th,m,FEE[sym])
                if np.isfinite(sc) and (best is None or sc>best[0]): best=(sc,h,th)
            if best:
                m=fit(tr,best[1],best[2]); sc,n=score(te,best[1],best[2],m,FEE[sym])
                os.append([sym,iv,cur.date(),best[2],best[1],n,sc])
            cur+=pd.Timedelta(days=DAYS_TEST)
        if os:
            a=pd.DataFrame(os,columns=["symbol","interval","fold","threshold","horizon","n","net"])
        # champion by aggregate OOS, not final
        z=a[(a.symbol==sym)&(a.interval==iv)]
        if len(z):
            g=z.groupby(["threshold","horizon"]).net.mean().sort_values(ascending=False)
            th,h=g.index[0]
            tr=d[d.t<last30]
            m=fit(tr,h,th)
            sc,n=score(d[d.t>=last30],h,th,m,FEE[sym])
            finals.append([sym,iv,th,h,n,sc])
    o=pd.DataFrame(os,columns=["symbol","interval","fold","threshold","horizon","n","net"])
    f=pd.DataFrame(finals,columns=["symbol","interval","threshold","horizon","n","final_mean"])
    o.to_csv("results/v424_oos.csv",index=False); f.to_csv("results/v424_final.csv",index=False)
    lines=["# SCALP LAB V4.24 — UTC HOUR SEASONALITY",
    "",
    "- Independent hypothesis: crypto returns contain stable UTC-hour seasonality.",
    "- Signal uses only the historical mean forward return for the entry candle's UTC hour.",
    "- No VWAP, Donchian, imbalance, RSI, ATR, breakout, pullback or regime filter.",
    "- Fixed horizons: 1/3/6 bars; fixed activation thresholds: 0/2/4/8 bps.",
    "- Six chronological 120d TRAIN / 30d TEST folds. FINAL = last 30d and confirmation-only.",
    "- Parameters are selected on aggregate OOS before FINAL; FINAL is never used for selection.",
    "",
    "## OOS", "", o.to_string(index=False) if len(o) else "NO RESULTS",
    "", "## FINAL", "", f.to_string(index=False) if len(f) else "NO RESULTS"]
    open("results/summary_v424.md","w").write("\n".join(lines))
if __name__=="__main__": main()
