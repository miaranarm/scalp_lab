from __future__ import annotations
import argparse,io,math,time,warnings
from pathlib import Path
import requests,numpy as np,pandas as pd

warnings.filterwarnings("ignore")
OUT=Path("results"); OUT.mkdir(exist_ok=True)

TRAIN,TEST,STEP,HOLD=180,45,45,90
MIN_TRAIN,MIN_FOLDS,MIN_TRADES=50,5,50
FT,FM=.0005,.0002
SLIP={"BTCUSDT":.00010,"ETHUSDT":.00015,"SOLUSDT":.00030}
MS={"1h":pd.Timedelta(hours=1),"4h":pd.Timedelta(hours=4)}
UA={"User-Agent":"Mozilla/5.0"}

def log(x=""): print(x,flush=True)

def months(a,b):
    p=pd.Period(a,freq="M"); q=pd.Period(b,freq="M")
    while p<=q:
        yield p
        p+=1

def fetch(symbol,iv,days):
    end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=days)
    log(f"  data {iv} ...")
    rows=[]
    url="https://data.binance.vision/data/futures/um"
    for p in months(start,end):
        fn=f"{symbol}-{iv}-{p.year}-{p.month:02d}.zip"
        u=f"{url}/monthly/klines/{symbol}/{iv}/{fn}"
        try:
            r=requests.get(u,headers=UA,timeout=30)
            if r.status_code==200:
                z=pd.read_csv(io.BytesIO(r.content),compression="zip",header=None)
                z=z.iloc[:,:12]; rows.append(z)
        except: pass
    if not rows: raise RuntimeError(f"no data {symbol} {iv}")
    z=pd.concat(rows,ignore_index=True)
    z.columns=["time","open","high","low","close","volume","ct","qv","trades","tbv","tqv","x"]
    z["time"]=pd.to_datetime(z.time,unit="ms",utc=True)
    z=z[(z.time>=start)&(z.time<=end)]
    for c in ["open","high","low","close","volume"]: z[c]=pd.to_numeric(z[c],errors="coerce")
    return z.drop_duplicates("time").sort_values("time").reset_index(drop=True)

def atr(x,n=14):
    h,l,c=x.high,x.low,x.close
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def features(x):
    x=x.copy()
    x["atr14"]=atr(x)
    x["ema20"]=x.close.ewm(span=20,adjust=False).mean()
    x["ema50"]=x.close.ewm(span=50,adjust=False).mean()
    x["ema200"]=x.close.ewm(span=200,adjust=False).mean()
    d=x.close.diff()
    up=d.clip(lower=0).rolling(14).mean()
    dn=(-d.clip(upper=0)).rolling(14).mean()
    rs=up/dn.replace(0,np.nan)
    x["rsi"]=100-100/(1+rs)
    x["vwap"]=((x.close*x.volume).rolling(48).sum()/x.volume.rolling(48).sum())
    x["z48"]=(x.close-x.close.rolling(48).mean())/x.close.rolling(48).std()
    x["z96"]=(x.close-x.close.rolling(96).mean())/x.close.rolling(96).std()
    x["dc20h"]=x.high.rolling(20).max().shift(1)
    x["dc20l"]=x.low.rolling(20).min().shift(1)
    x["dc50h"]=x.high.rolling(50).max().shift(1)
    x["dc50l"]=x.low.rolling(50).min().shift(1)
    x["atrp"]=x.atr14/x.close
    return x

def context(x,higher,iv):
    h=higher.copy()
    h["ema20_ctx"]=h.close.ewm(span=20,adjust=False).mean()
    h["ema50_ctx"]=h.close.ewm(span=50,adjust=False).mean()
    h["ema200_ctx"]=h.close.ewm(span=200,adjust=False).mean()
    h["atr14_ctx"]=atr(h)
    h=h[["time","close","ema20_ctx","ema50_ctx","ema200_ctx","atr14_ctx"]]
    h=h.rename(columns={"close":"close_ctx"})
    h["time"]=h.time+MS[iv]
    return pd.merge_asof(
        x.sort_values("time"),h.sort_values("time"),
        on="time",direction="backward"
    )

def candidates(x,higher,iv):
    x=context(features(x),higher,iv)
    x["trend"]=np.where(
        (x.ema20_ctx>x.ema50_ctx)&(x.ema50_ctx>x.ema200_ctx),"trend",
        np.where((x.ema20_ctx<x.ema50_ctx)&(x.ema50_ctx<x.ema200_ctx),"down","range")
    )
    a=[]

    def add(name,mask):
        y=x.copy(); y["signal"]=name; y["sig"]=mask.fillna(False)
        a.append(y)

    add("vwap48k2",(x.close<x.vwap-2*x.atr14))
    add("vwap96k2",(x.close<x.close.rolling(96).mean()-2*x.atr14))
    add("vwap48k3",(x.close<x.vwap-3*x.atr14))
    add("donchian20v0",x.close>x.dc20h)
    add("donchian20v1.5",x.close>x.dc20h+1.5*x.atr14)
    add("donchian50v1.5",x.close>x.dc50h+1.5*x.atr14)
    add("zscore30t2",x.z48<-2)
    add("zscore60t2.5",x.z96<-2.5)
    add("pullbackRSI35",x.rsi<35)
    add("pullbackRSI40",x.rsi<40)
    add("breakout20",x.close>x.dc20h)

    return a

EXITS=[(1.5,1,12),(2,1,24),(3,1.5,36),(2,2,24)]
PROFILES=["taker","maker_tp","maker_both"]
REGIMES=["all","trend","range"]

def signal_ok(row,reg):
    if reg=="all": return True
    if reg=="trend": return row.trend in ("trend","down")
    return row.trend=="range"

def simulate(df,reg,tp,sl,hold,profile,capital=100):
    d=df
    c=d.close.to_numpy(float); hi=d.high.to_numpy(float)
    lo=d.low.to_numpy(float); sig=d.sig.to_numpy(bool)
    atrv=d.atr14.to_numpy(float)
    trades=[]
    i=0; n=len(d)
    while i<n-2:
        if not sig[i] or not signal_ok(d.iloc[i],reg) or not np.isfinite(atrv[i]):
            i+=1; continue

        j=i+1
        if j>=n: break
        entry=c[j]
        if profile in ("maker_tp","maker_both"):
            if lo[j]>c[i] and hi[j]<c[i]:
                i+=1; continue
            entry=c[i]

        a=atrv[i]
        if not np.isfinite(a) or a<=0:
            i+=1; continue

        target=entry+tp*a
        stop=entry-sl*a
        fee=FM if profile!="taker" else FT
        slip=SLIP.get(d.attrs.get("symbol",""),.0002)
        exitp=None; reason=""
        end=min(n,j+hold)

        for k in range(j,end):
            if lo[k]<=stop:
                exitp=stop*(1-slip); reason="SL"; break
            if hi[k]>=target:
                exitp=target*(1-slip); reason="TP"; break

        if exitp is None:
            exitp=c[end-1]*(1-slip); reason="TIME"

        r=(exitp/entry-1)-2*fee
        trades.append(r)
        i=max(j+1,end if reason=="TIME" else k+1)

    if not trades:
        return dict(n=0,ret=0,pf=np.nan,dd=0,edge=np.nan)

    r=np.array(trades)
    eq=np.cumprod(1+r)
    peak=np.maximum.accumulate(eq)
    dd=np.min(eq/peak-1)
    gp=r[r>0].sum()
    gl=-r[r<0].sum()
    pf=gp/gl if gl else np.inf
    return dict(n=len(r),ret=(eq[-1]-1)*100,pf=pf,dd=dd*100,edge=r.mean()*100)

def configs():
    sigs=[
        "vwap48k2","vwap96k2","vwap48k3","donchian20v0",
        "donchian20v1.5","donchian50v1.5","zscore30t2",
        "zscore60t2.5","pullbackRSI35","pullbackRSI40","breakout20"
    ]
    return [(s,r,p,t,sl,h) for s in sigs for r in REGIMES
            for p in PROFILES for t,sl,h in EXITS]

def folds(start,end):
    out=[]; cur=start+pd.Timedelta(days=TRAIN)
    while cur+pd.Timedelta(days=TEST)<=end:
        out.append((
            cur-pd.Timedelta(days=TRAIN),cur,
            cur,cur+pd.Timedelta(days=TEST)
        ))
        cur+=pd.Timedelta(days=STEP)
    return out

def metric(s):
    if s["n"]<MIN_TRAIN: return -np.inf
    return s["ret"]

def run_symbol(symbol,iv,days,capital):
    log(f"\n[{symbol}]")
    e=fetch(symbol,iv,days); e.attrs["symbol"]=symbol
    h=fetch(symbol,"4h",days+40)
    cs=candidates(e,h,iv)
    cfg=configs()
    log(f"data={len(e):,} cfg={len(cfg)}")

    bysig={z.signal:z for z in cs}
    # Simulate once/config over full history.
    cache={}
    for n,r,p,t,sl,hold in cfg:
        z=bysig[n].copy()
        z["sig"]=z["sig"]&z.trend.notna()
        cache[(n,r,p,t,sl,hold)]=simulate(z,r,t,sl,hold,p,capital)

    end=e.time.max()
    wf_end=end-pd.Timedelta(days=HOLD)
    fs=folds(e.time.min(),wf_end)
    log(f"wf={len(fs)}")

    rows=[]; selected=[]
    for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
        if fi==1 or fi==len(fs): log(f"  fold {fi}/{len(fs)}")

        for key in cfg:
            n,r,p,t,sl,hold=key
            z=bysig[n]
            tr=z[(z.time>=tr0)&(z.time<tr1)]
            te=z[(z.time>=te0)&(z.time<te1)]

            # Re-simulate slices to obtain proper fold metrics.
            a=simulate(tr,r,t,sl,hold,p,capital)
            b=simulate(te,r,t,sl,hold,p,capital)
            ok=a["n"]>=MIN_TRAIN and np.isfinite(a["ret"])
            rows.append(dict(
                symbol=symbol,interval=iv,fold=fi,signal=n,regime=r,
                profile=p,tp=t,sl=sl,hold=hold,
                train_n=a["n"],train_ret=a["ret"],
                test_n=b["n"],test_ret=b["ret"],test_pf=b["pf"],
                test_dd=b["dd"],test_edge=b["edge"],
                train_eligible=ok,selected=False
            ))

        rr=pd.DataFrame([x for x in rows if x["fold"]==fi])
        rr=rr[rr.train_eligible]
        if len(rr):
            k=rr.train_ret.idxmax()
            rows[k]["selected"]=True
            selected.append(rows[k])

    wf=pd.DataFrame(rows)
    sel=pd.DataFrame(selected)

    groups=[]
    for key,g in wf.groupby(
        ["symbol","interval","signal","regime","profile","tp","sl","hold"],
        dropna=False
    ):
        el=g[g.train_eligible]
        ac=el[el.test_n>0]
        if len(el)==0: continue
        pos=(ac.test_ret>0).mean() if len(ac) else np.nan
        pf=ac.test_pf.replace([np.inf],np.nan).median()
        edge=ac.test_edge.mean()
        robust=(
            len(el)>=MIN_FOLDS and len(ac)>=MIN_FOLDS and
            ac.test_n.sum()>=MIN_TRADES and
            pos>=.50 and np.isfinite(pf) and pf>=1 and
            np.isfinite(edge) and edge>=0
        )
        groups.append(dict(
            symbol=key[0],interval=key[1],signal=key[2],regime=key[3],
            profile=key[4],tp=key[5],sl=key[6],hold=key[7],
            eligible_folds=len(el),active_folds=len(ac),
            total_trades=int(ac.test_n.sum()),
            mean_oos=ac.test_ret.mean(),
            median_oos=ac.test_ret.median(),
            positive_fold_ratio=pos,
            median_pf=pf,median_dd=ac.test_dd.median(),
            mean_edge=edge,robust=bool(robust)
        ))

    rob=pd.DataFrame(groups)
    log(f"robust={int(rob.robust.sum()) if len(rob) else 0}")

    # Holdout: LAST 90 DAYS ONLY.
    hold=rob[rob.robust].copy()
    ho=[]
    if len(hold):
        hold=hold.sort_values(
            ["median_oos","median_pf","active_folds","total_trades"],
            ascending=False
        )
        for _,q in hold.head(1).iterrows():
            z=bysig[q.signal]
            hs=z[z.time>=wf_end]
            a=simulate(hs,q.regime,q.tp,q.sl,q.hold,q.profile,capital)
            ho.append(dict(**q.to_dict(),holdout_n=a["n"],
                           holdout_ret=a["ret"],holdout_pf=a["pf"],
                           holdout_dd=a["dd"],holdout_edge=a["edge"]))

    return wf,sel,rob,pd.DataFrame(ho)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",nargs="+",default=["BTCUSDT","ETHUSDT","SOLUSDT"])
    ap.add_argument("--intervals",nargs="+",default=["1h"])
    ap.add_argument("--days",type=int,default=730)
    ap.add_argument("--capital",type=float,default=100)
    ap.add_argument("--mc-runs",type=int,default=0)
    ap.add_argument("--random-runs",type=int,default=0)
    a=ap.parse_args()

    log("SCALP LAB V4.3.1")
    log(f"{','.join(a.symbols)} | {','.join(a.intervals)} | {a.days}d")
    log("WF=180/45/45 HOLD=90 MC=0 RANDOM=0")

    W=[];S=[];R=[];H=[]
    for sym in a.symbols:
        for iv in a.intervals:
            try:
                w,s,r,h=run_symbol(sym,iv,a.days,a.capital)
                W.append(w); S.append(s); R.append(r); H.append(h)
            except Exception as ex:
                log(f"ERROR {sym}: {type(ex).__name__}: {ex}")

    wf=pd.concat(W,ignore_index=True) if W else pd.DataFrame()
    sel=pd.concat(S,ignore_index=True) if S else pd.DataFrame()
    rob=pd.concat(R,ignore_index=True) if R else pd.DataFrame()
    ho=pd.concat(H,ignore_index=True) if H else pd.DataFrame()

    wf.to_csv(OUT/"walk_forward_v43.csv",index=False)
    sel.to_csv(OUT/"selected_v43.csv",index=False)
    rob.to_csv(OUT/"robustness_v43.csv",index=False)
    ho.to_csv(OUT/"holdout_v43.csv",index=False)

    if len(rob):
        g=rob.groupby(["signal","regime","profile","tp","sl","hold"]).agg(
            symbols=("symbol","nunique"),robust_symbols=("robust","sum")
        ).reset_index()
    else:g=pd.DataFrame()
    g.to_csv(OUT/"global_v43.csv",index=False)

    md=[
        "# SCALP LAB V4.3.1",
        f"- WF rows: {len(wf)}",
        f"- Selected: {len(sel)}",
        f"- Robust: {int(rob.robust.sum()) if len(rob) else 0}",
        f"- Holdout: {len(ho)}"
    ]
    (OUT/"summary_v43.md").write_text("\n".join(md),encoding="utf-8")
    log(f"\nDONE wf={len(wf)} selected={len(sel)} robust={int(rob.robust.sum()) if len(rob) else 0} holdout={len(ho)}")

if __name__=="__main__":
    main()
