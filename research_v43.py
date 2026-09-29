from __future__ import annotations
import argparse,io,warnings
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
COLS=["time","open","high","low","close","volume","ct","qv","trades","tbv","tqv","x"]

def log(x=""): print(x,flush=True)

def months(a,b):
    p=pd.Period(a,"M"); q=pd.Period(b,"M")
    while p<=q:
        yield p
        p+=1

def read_zip(content):
    z=pd.read_csv(io.BytesIO(content),compression="zip")
    if "open_time" not in z.columns:
        z=pd.read_csv(io.BytesIO(content),compression="zip",header=None)
        z=z.iloc[:,:12]; z.columns=COLS
    else:
        z=z.rename(columns={"open_time":"time"})
        z=z.iloc[:,:12]
        z.columns=COLS

    z["time"]=pd.to_numeric(z["time"],errors="coerce")
    z=z.dropna(subset=["time"])
    z["time"]=pd.to_datetime(z["time"],unit="ms",utc=True)

    for c in ["open","high","low","close","volume"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")

    return z.dropna(subset=["open","high","low","close"])

def get_file(url):
    try:
        r=requests.get(url,headers=UA,timeout=30)
        return read_zip(r.content) if r.status_code==200 else None
    except Exception:
        return None

def fetch(symbol,iv,days):
    end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=days)
    base="https://data.binance.vision/data/futures/um"
    rows=[]

    for p in months(start,end):
        fn=f"{symbol}-{iv}-{p.year}-{p.month:02d}.zip"
        z=get_file(f"{base}/monthly/klines/{symbol}/{iv}/{fn}")

        if z is not None:
            rows.append(z)
            continue

        if p==end.to_period("M"):
            d=p.start_time.tz_localize("UTC")
            while d<=end:
                fn=f"{symbol}-{iv}-{d:%Y-%m-%d}.zip"
                z=get_file(f"{base}/daily/klines/{symbol}/{iv}/{fn}")
                if z is not None: rows.append(z)
                d+=pd.Timedelta(days=1)

    if not rows:
        raise RuntimeError(f"no data {symbol} {iv}")

    z=pd.concat(rows,ignore_index=True)
    z=z[(z.time>=start)&(z.time<=end)]
    z=z.drop_duplicates("time").sort_values("time").reset_index(drop=True)

    if len(z)<1000:
        raise RuntimeError(f"insufficient data {symbol} {iv}: {len(z)}")

    return z

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

    x["vwap"]=(x.close*x.volume).rolling(48).sum()/x.volume.rolling(48).sum()
    x["z48"]=(x.close-x.close.rolling(48).mean())/x.close.rolling(48).std()
    x["z96"]=(x.close-x.close.rolling(96).mean())/x.close.rolling(96).std()
    x["dc20h"]=x.high.rolling(20).max().shift(1)
    x["dc50h"]=x.high.rolling(50).max().shift(1)
    return x

def context(x,higher,iv):
    h=higher.copy()
    h["ema20_ctx"]=h.close.ewm(span=20,adjust=False).mean()
    h["ema50_ctx"]=h.close.ewm(span=50,adjust=False).mean()
    h["ema200_ctx"]=h.close.ewm(span=200,adjust=False).mean()
    h["atr14_ctx"]=atr(h)
    h=h[["time","close","ema20_ctx","ema50_ctx","ema200_ctx","atr14_ctx"]]
    h=h.rename(columns={"close":"close_ctx"})
    h["time"]+=MS[iv]

    return pd.merge_asof(
        x.sort_values("time"),
        h.sort_values("time"),
        on="time",direction="backward"
    )

def candidates(x,higher,iv):
    x=context(features(x),higher,iv)

    x["trend"]=np.where(
        (x.ema20_ctx>x.ema50_ctx)&(x.ema50_ctx>x.ema200_ctx),
        "trend",
        np.where(
            (x.ema20_ctx<x.ema50_ctx)&(x.ema50_ctx<x.ema200_ctx),
            "down","range"
        )
    )

    a=[]

    def add(name,mask):
        y=x.copy()
        y["signal"]=name
        y["sig"]=mask.fillna(False)
        a.append(y)

    add("vwap48k2",x.close<x.vwap-2*x.atr14)
    add("vwap96k2",x.close<x.close.rolling(96).mean()-2*x.atr14)
    add("vwap48k3",x.close<x.vwap-3*x.atr14)
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
    return (
        reg=="all" or
        (reg=="trend" and row.trend in ("trend","down")) or
        row.trend=="range"
    )

def simulate(df,reg,tp,sl,hold,profile,symbol):
    if len(df)<3:
        return dict(n=0,ret=0,pf=np.nan,dd=0,edge=np.nan)

    c=df.close.to_numpy(float)
    hi=df.high.to_numpy(float)
    lo=df.low.to_numpy(float)
    sig=df.sig.to_numpy(bool)
    av=df.atr14.to_numpy(float)

    trades=[]; i=0; n=len(df)
    slip=SLIP.get(symbol,.0002)
    fee=FM if profile!="taker" else FT

    while i<n-2:
        if not sig[i] or not signal_ok(df.iloc[i],reg) or not np.isfinite(av[i]):
            i+=1
            continue

        j=i+1
        entry=c[j]

        if profile!="taker":
            if lo[j]>c[i] and hi[j]<c[i]:
                i+=1
                continue
            entry=c[i]

        a=av[i]
        if not np.isfinite(a) or a<=0:
            i+=1
            continue

        target=entry+tp*a
        stop=entry-sl*a
        end=min(n,j+hold)
        exitp=None
        reason=""

        for k in range(j,end):
            if lo[k]<=stop:
                exitp=stop*(1-slip)
                reason="SL"
                break
            if hi[k]>=target:
                exitp=target*(1-slip)
                reason="TP"
                break

        if exitp is None:
            exitp=c[end-1]*(1-slip)
            reason="TIME"

        trades.append(exitp/entry-1-2*fee)
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

    return dict(
        n=len(r),
        ret=(eq[-1]-1)*100,
        pf=pf,
        dd=dd*100,
        edge=r.mean()*100
    )

def configs():
    sigs=[
        "vwap48k2","vwap96k2","vwap48k3",
        "donchian20v0","donchian20v1.5","donchian50v1.5",
        "zscore30t2","zscore60t2.5",
        "pullbackRSI35","pullbackRSI40","breakout20"
    ]
    return [
        (s,r,p,t,sl,h)
        for s in sigs
        for r in REGIMES
        for p in PROFILES
        for t,sl,h in EXITS
    ]

def folds(start,end):
    out=[]
    cur=start+pd.Timedelta(days=TRAIN)

    while cur+pd.Timedelta(days=TEST)<=end:
        out.append((
            cur-pd.Timedelta(days=TRAIN),cur,
            cur,cur+pd.Timedelta(days=TEST)
        ))
        cur+=pd.Timedelta(days=STEP)

    return out

def run_symbol(symbol,iv,days):
    e=fetch(symbol,iv,days)
    h=fetch(symbol,"4h",days+40)
    cs=candidates(e,h,iv)
    bysig={z["signal"].iloc[0]:z for z in cs}
    cfg=configs()

    end=e.time.max()
    wf_end=end-pd.Timedelta(days=HOLD)
    fs=folds(e.time.min(),wf_end)

    if len(fs)<MIN_FOLDS:
        raise RuntimeError(f"too few folds {len(fs)}")

    rows=[]
    selected=[]

    for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
        base=len(rows)

        for n,r,p,t,sl,hold in cfg:
            z=bysig[n]
            tr=z[(z.time>=tr0)&(z.time<tr1)]
            te=z[(z.time>=te0)&(z.time<te1)]

            a=simulate(tr,r,t,sl,hold,p,symbol)
            b=simulate(te,r,t,sl,hold,p,symbol)
            ok=a["n"]>=MIN_TRAIN and np.isfinite(a["ret"])

            rows.append(dict(
                symbol=symbol,interval=iv,fold=fi,
                signal=n,regime=r,profile=p,tp=t,sl=sl,hold=hold,
                train_n=a["n"],train_ret=a["ret"],
                test_n=b["n"],test_ret=b["ret"],
                test_pf=b["pf"],test_dd=b["dd"],
                test_edge=b["edge"],
                train_eligible=ok,selected=False
            ))

        cand=[
            (i,rows[i])
            for i in range(base,len(rows))
            if rows[i]["train_eligible"]
        ]

        if cand:
            bi=max(cand,key=lambda x:x[1]["train_ret"])[0]
            rows[bi]["selected"]=True
            selected.append(rows[bi].copy())

    wf=pd.DataFrame(rows)
    sel=pd.DataFrame(selected)
    groups=[]

    for key,g in wf.groupby(
        ["symbol","interval","signal","regime","profile","tp","sl","hold"],
        dropna=False
    ):
        el=g[g.train_eligible]
        ac=el[el.test_n>0]

        if len(el)==0:
            continue

        pos=(ac.test_ret>0).mean()
        pf=ac.test_pf.replace([np.inf],np.nan).median()
        edge=ac.test_edge.mean()

        robust=(
            len(el)>=MIN_FOLDS and
            len(ac)>=MIN_FOLDS and
            ac.test_n.sum()>=MIN_TRADES and
            pos>=.50 and
            np.isfinite(pf) and pf>=1 and
            np.isfinite(edge) and edge>=0
        )

        groups.append(dict(
            symbol=key[0],interval=key[1],
            signal=key[2],regime=key[3],
            profile=key[4],tp=key[5],sl=key[6],hold=key[7],
            eligible_folds=len(el),
            active_folds=len(ac),
            total_trades=int(ac.test_n.sum()),
            mean_oos=ac.test_ret.mean(),
            median_oos=ac.test_ret.median(),
            positive_fold_ratio=pos,
            median_pf=pf,
            median_dd=ac.test_dd.median(),
            mean_edge=edge,
            robust=bool(robust)
        ))

    rob=pd.DataFrame(groups)
    ho=[]

    if len(rob):
        hold_df=rob[rob["robust"]].copy()

        if len(hold_df):
            hold_df=hold_df.sort_values(
                ["median_oos","median_pf","active_folds","total_trades"],
                ascending=False
            )

            q=hold_df.iloc[0]

            # Explicit [] : jamais d'ambiguïté pandas.
            sig=str(q["signal"])
            reg=str(q["regime"])
            prof=str(q["profile"])
            tp=float(q["tp"])
            sl=float(q["sl"])
            hd=int(q["hold"])

            z=bysig[sig]
            hs=z[z.time>=wf_end]

            a=simulate(hs,reg,tp,sl,hd,prof,symbol)

            ho.append(dict(
                **q.to_dict(),
                holdout_n=a["n"],
                holdout_ret=a["ret"],
                holdout_pf=a["pf"],
                holdout_dd=a["dd"],
                holdout_edge=a["edge"]
            ))

    return wf,sel,rob,pd.DataFrame(ho),len(e),len(fs)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",nargs="+",default=["BTCUSDT","ETHUSDT","SOLUSDT"])
    ap.add_argument("--intervals",nargs="+",default=["1h"])
    ap.add_argument("--days",type=int,default=730)
    ap.add_argument("--capital",type=float,default=100)
    ap.add_argument("--mc-runs",type=int,default=0)
    ap.add_argument("--random-runs",type=int,default=0)
    a=ap.parse_args()

    log(f"V4.3.1 | {','.join(a.symbols)} | {','.join(a.intervals)} | {a.days}d")
    log("WF=180/45/45 HOLD=90 | MC=0 RANDOM=0")

    W=[]; S=[]; R=[]; H=[]; errors=[]

    for sym in a.symbols:
        for iv in a.intervals:
            try:
                w,s,r,h,nf,nw=run_symbol(sym,iv,a.days)
                W.append(w); S.append(s); R.append(r); H.append(h)
                log(f"{sym} data={nf} WF={nw} R={int(r['robust'].sum()) if len(r) else 0}")
            except Exception as ex:
                msg=f"{sym}: {type(ex).__name__}: {ex}"
                errors.append(msg)
                log(f"ERROR {msg}")

    wf=pd.concat(W,ignore_index=True) if W else pd.DataFrame()
    sel=pd.concat(S,ignore_index=True) if S else pd.DataFrame()
    rob=pd.concat(R,ignore_index=True) if R else pd.DataFrame()
    ho=pd.concat(H,ignore_index=True) if H else pd.DataFrame()

    wf.to_csv(OUT/"walk_forward_v43.csv",index=False)
    sel.to_csv(OUT/"selected_v43.csv",index=False)
    rob.to_csv(OUT/"robustness_v43.csv",index=False)
    ho.to_csv(OUT/"holdout_v43.csv",index=False)

    if len(rob):
        g=rob.groupby(
            ["signal","regime","profile","tp","sl","hold"]
        ).agg(
            symbols=("symbol","nunique"),
            robust_symbols=("robust","sum")
        ).reset_index()
    else:
        g=pd.DataFrame()

    g.to_csv(OUT/"global_v43.csv",index=False)

    (OUT/"summary_v43.md").write_text(
        "\n".join([
            "# SCALP LAB V4.3.1",
            f"WF rows: {len(wf)}",
            f"Selected: {len(sel)}",
            f"Robust: {int(rob['robust'].sum()) if len(rob) else 0}",
            f"Holdout: {len(ho)}",
            f"Errors: {len(errors)}"
        ]),
        encoding="utf-8"
    )

    log(
        f"DONE wf={len(wf)} sel={len(sel)} "
        f"robust={int(rob['robust'].sum()) if len(rob) else 0} "
        f"hold={len(ho)}"
    )

    if errors:
        raise RuntimeError("; ".join(errors))

if __name__=="__main__":
    main()
