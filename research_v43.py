from __future__ import annotations
import argparse,io,warnings
from pathlib import Path
import requests,numpy as np,pandas as pd

warnings.filterwarnings("ignore")
OUT=Path("results");OUT.mkdir(exist_ok=True)

TRAIN,TEST,STEP,HOLD=180,45,45,90
MIN_TRAIN,MIN_FOLDS,MIN_TRADES=50,5,50
FT,FM=.0005,.0002
SLIP={"BTCUSDT":.00010,"ETHUSDT":.00015,"SOLUSDT":.00030}
CTX="4h"
UA={"User-Agent":"Mozilla/5.0"}
COLS=["time","open","high","low","close","volume","ct","qv","trades","tbv","tqv","x"]

def log(x=""):print(x,flush=True)

def months(a,b):
    p=pd.Period(a,"M");q=pd.Period(b,"M")
    while p<=q:
        yield p
        p+=1

def read_zip(content):
    z=pd.read_csv(io.BytesIO(content),compression="zip")
    if "open_time" not in z.columns:
        z=pd.read_csv(io.BytesIO(content),compression="zip",header=None)
        z=z.iloc[:,:12]
        z.columns=COLS
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

                if z is not None:
                    rows.append(z)

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
    tr=pd.concat([
        h-l,
        (h-c.shift()).abs(),
        (l-c.shift()).abs()
    ],axis=1).max(axis=1)
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
    x["rsi"]=100-100/(1+up/dn.replace(0,np.nan))

    x["vwap48"]=(x.close*x.volume).rolling(48).sum()/x.volume.rolling(48).sum()
    x["mean96"]=x.close.rolling(96).mean()

    x["z48"]=(x.close-x.close.rolling(48).mean())/x.close.rolling(48).std()
    x["z96"]=(x.close-x.close.rolling(96).mean())/x.close.rolling(96).std()

    x["dc20h"]=x.high.rolling(20).max().shift(1)
    x["dc50h"]=x.high.rolling(50).max().shift(1)
    x["dc20l"]=x.low.rolling(20).min().shift(1)
    x["dc50l"]=x.low.rolling(50).min().shift(1)

    return x

def context(x,h):
    h=h.copy()

    h["ema20_ctx"]=h.close.ewm(span=20,adjust=False).mean()
    h["ema50_ctx"]=h.close.ewm(span=50,adjust=False).mean()
    h["ema200_ctx"]=h.close.ewm(span=200,adjust=False).mean()
    h["atr14_ctx"]=atr(h)

    h=h[
        ["time","close","ema20_ctx","ema50_ctx",
         "ema200_ctx","atr14_ctx"]
    ]

    h=h.rename(columns={"close":"close_ctx"})

    step=h.time.diff().mode().iloc[0]
    h["time"]+=step

    return pd.merge_asof(
        x.sort_values("time"),
        h.sort_values("time"),
        on="time",
        direction="backward"
    )

def candidates(x,h):
    x=context(features(x),h)

    x["trend"]=np.where(
        (x.ema20_ctx>x.ema50_ctx)&
        (x.ema50_ctx>x.ema200_ctx),
        "trend",
        np.where(
            (x.ema20_ctx<x.ema50_ctx)&
            (x.ema50_ctx<x.ema200_ctx),
            "down",
            "range"
        )
    )

    a=[]

    def add(name,mask,side,family):
        y=x[
            ["time","open","high","low","close","atr14","trend"]
        ].copy()

        y["sig"]=mask.fillna(False).to_numpy(bool)
        y["side"]=side
        y["family"]=family
        a.append((name,y))

    add("vwap48_k2",x.close<x.vwap48-2*x.atr14,1,"vwap")
    add("mean96_k2",x.close<x.mean96-2*x.atr14,1,"mean")
    add("vwap48_k3",x.close<x.vwap48-3*x.atr14,1,"vwap")

    add("donchian20_v0",x.close>x.dc20h,1,"donchian")
    add("donchian20_v1.5",x.close>x.dc20h+1.5*x.atr14,1,"donchian")
    add("donchian50_v1.5",x.close>x.dc50h+1.5*x.atr14,1,"donchian")

    add("zscore48_t2",x.z48<-2,1,"zscore")
    add("zscore96_t2.5",x.z96<-2.5,1,"zscore")
    add("pullbackRSI35",x.rsi<35,1,"rsi")
    add("pullbackRSI40",x.rsi<40,1,"rsi")

    add("vwap48_k2_short",x.close>x.vwap48+2*x.atr14,-1,"vwap")
    add("mean96_k2_short",x.close>x.mean96+2*x.atr14,-1,"mean")
    add("vwap48_k3_short",x.close>x.vwap48+3*x.atr14,-1,"vwap")

    add("donchian20_v0_short",x.close<x.dc20l,-1,"donchian")
    add("donchian20_v1.5_short",x.close<x.dc20l-1.5*x.atr14,-1,"donchian")
    add("donchian50_v1.5_short",x.close<x.dc50l-1.5*x.atr14,-1,"donchian")

    add("zscore48_t2_short",x.z48>2,-1,"zscore")
    add("zscore96_t2.5_short",x.z96>2.5,-1,"zscore")

    add("pullbackRSI35_short",x.rsi>65,-1,"rsi")
    add("pullbackRSI40_short",x.rsi>60,-1,"rsi")

    return dict(a)

EXITS=[
    (1.5,1,12),
    (2,1,24),
    (3,1.5,36),
    (2,2,24)
]

PROFILES=["taker","maker_tp","maker_both"]
REGIMES=["all","trend","range"]

def simulate(
    d,reg,tp,sl,hold,profile,symbol,
    random_side=False,rng=None
):
    if len(d)<3:
        return 0,0,np.nan,0,np.nan

    c=d.close.to_numpy(float)
    hi=d.high.to_numpy(float)
    lo=d.low.to_numpy(float)
    av=d.atr14.to_numpy(float)

    # IMPORTANT : conversion NumPy pour éviter KeyError après slicing pandas
    sig=d.sig.to_numpy(bool)

    side0=int(d.side.iloc[0])
    trend=d.trend.to_numpy()

    n=len(d)
    i=0
    tr=[]

    slip=SLIP.get(symbol,.0002)

    while i<n-2:
        t=trend[i]

        if reg=="trend":
            ok=t in ("trend","down")
        elif reg=="range":
            ok=t=="range"
        else:
            ok=True

        if not sig[i] or not ok or not np.isfinite(av[i]):
            i+=1
            continue

        if random_side:
            side=int(rng.choice([-1,1]))
        else:
            side=side0

        j=i+1
        limit=c[i]
        entry=c[j]

        if profile!="taker":
            if side==1 and lo[j]>limit:
                i+=1
                continue

            if side==-1 and hi[j]<limit:
                i+=1
                continue

            entry=limit

        a=av[i]

        if not np.isfinite(a) or a<=0:
            i+=1
            continue

        target=entry+side*tp*a
        stop=entry-side*sl*a

        end=min(n,j+hold)
        exitp=None
        reason=""

        for k in range(j,end):
            hit_sl=lo[k]<=stop if side==1 else hi[k]>=stop
            hit_tp=hi[k]>=target if side==1 else lo[k]<=target

            if hit_sl:
                exitp=stop*(1-side*slip)
                reason="SL"
                break

            if hit_tp:
                exitp=target*(1-side*slip)
                reason="TP"
                break

        if exitp is None:
            k=end-1
            exitp=c[k]*(1-side*slip)
            reason="TIME"

        entry_fee=FM if profile=="maker_both" else FT

        exit_fee=(
            FM
            if profile in ("maker_tp","maker_both")
            and reason=="TP"
            else FT
        )

        pnl=side*(exitp/entry-1)-entry_fee-exit_fee
        tr.append(pnl)

        i=max(
            j+1,
            end if reason=="TIME" else k+1
        )

    if not tr:
        return 0,0,np.nan,0,np.nan

    r=np.asarray(tr)
    eq=np.cumprod(1+r)
    peak=np.maximum.accumulate(eq)
    dd=np.min(eq/peak-1)

    gp=r[r>0].sum()
    gl=-r[r<0].sum()
    pf=gp/gl if gl else np.inf

    return (
        len(r),
        (eq[-1]-1)*100,
        pf,
        dd*100,
        r.mean()*100
    )

def configs():
    sigs=[
        "vwap48_k2",
        "mean96_k2",
        "vwap48_k3",
        "donchian20_v0",
        "donchian20_v1.5",
        "donchian50_v1.5",
        "zscore48_t2",
        "zscore96_t2.5",
        "pullbackRSI35",
        "pullbackRSI40",

        "vwap48_k2_short",
        "mean96_k2_short",
        "vwap48_k3_short",
        "donchian20_v0_short",
        "donchian20_v1.5_short",
        "donchian50_v1.5_short",
        "zscore48_t2_short",
        "zscore96_t2.5_short",
        "pullbackRSI35_short",
        "pullbackRSI40_short"
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
            cur-pd.Timedelta(days=TRAIN),
            cur,
            cur,
            cur+pd.Timedelta(days=TEST)
        ))
        cur+=pd.Timedelta(days=STEP)

    return out

def run_symbol(symbol,iv,days,random_runs):
    e=fetch(symbol,iv,days)
    h=fetch(symbol,CTX,days+40)

    cs=candidates(e,h)
    cfg=configs()

    bysig=cs

    end=e.time.max()
    wf_end=end-pd.Timedelta(days=HOLD)

    fs=folds(e.time.min(),wf_end)

    if len(fs)<MIN_FOLDS:
        raise RuntimeError(f"too few folds {len(fs)}")

    rows=[]
    selected=[]

    for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
        log(f"{symbol} FOLD {fi}/{len(fs)}")

        fold_rows=[]

        for n,r,p,t,sl,hold in cfg:
            z=bysig[n]

            tr=z[
                (z.time>=tr0)&
                (z.time<tr1)
            ]

            te=z[
                (z.time>=te0)&
                (z.time<te1)
            ]

            a=simulate(
                tr,r,t,sl,hold,p,symbol
            )

            b=simulate(
                te,r,t,sl,hold,p,symbol
            )

            ok=(
                a[0]>=MIN_TRAIN and
                np.isfinite(a[1])
            )

            fold_rows.append(dict(
                symbol=symbol,
                interval=iv,
                fold=fi,
                signal=n,
                side="SHORT" if z.side.iloc[0]<0 else "LONG",
                family=z.family.iloc[0],
                regime=r,
                profile=p,
                tp=t,
                sl=sl,
                hold=hold,
                train_n=a[0],
                train_ret=a[1],
                test_n=b[0],
                test_ret=b[1],
                test_pf=b[2],
                test_dd=b[3],
                test_edge=b[4],
                train_eligible=ok,
                selected=False
            ))

        rows.extend(fold_rows)

        cand=[
            x for x in fold_rows
            if x["train_eligible"]
        ]

        if cand:
            bi=max(
                cand,
                key=lambda x:x["train_ret"]
            )

            bi["selected"]=True
            selected.append(bi.copy())

    wf=pd.DataFrame(rows)
    sel=pd.DataFrame(selected)
    groups=[]

    keys=[
        "symbol","interval","signal","side","family",
        "regime","profile","tp","sl","hold"
    ]

    for key,g in wf.groupby(
        keys,
        dropna=False
    ):
        el=g[g.train_eligible]
        ac=el[el.test_n>0]

        if not len(el):
            continue

        pos=(ac.test_ret>0).mean()
        pf=ac.test_pf.replace(
            [np.inf],np.nan
        ).median()

        edge=ac.test_edge.mean()

        robust=(
            len(el)>=MIN_FOLDS and
            len(ac)>=MIN_FOLDS and
            ac.test_n.sum()>=MIN_TRADES and
            pos>=.50 and
            np.isfinite(pf) and
            pf>=1 and
            np.isfinite(edge) and
            edge>=0
        )

        groups.append(dict(
            symbol=key[0],
            interval=key[1],
            signal=key[2],
            side=key[3],
            family=key[4],
            regime=key[5],
            profile=key[6],
            tp=key[7],
            sl=key[8],
            hold=key[9],
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
        qdf=rob[rob.robust].copy()

        if len(qdf):
            qdf=qdf.sort_values(
                [
                    "median_oos",
                    "median_pf",
                    "active_folds",
                    "total_trades"
                ],
                ascending=False
            )

            q=qdf.iloc[0]

            z=bysig[str(q.signal)]
            hs=z[z.time>=wf_end]

            a=simulate(
                hs,
                str(q.regime),
                float(q.tp),
                float(q.sl),
                int(q.hold),
                str(q.profile),
                symbol
            )

            rnd_mean=np.nan
            rnd_pf=np.nan

            if random_runs:
                er=[]
                pr=[]

                for seed in range(random_runs):
                    rng=np.random.default_rng(seed)

                    rr=simulate(
                        hs,
                        str(q.regime),
                        float(q.tp),
                        float(q.sl),
                        int(q.hold),
                        str(q.profile),
                        symbol,
                        True,
                        rng
                    )

                    er.append(rr[4])
                    pr.append(rr[2])

                rnd_mean=float(np.nanmean(er))
                rnd_pf=float(np.nanmedian(pr))

            ho.append(dict(
                **q.to_dict(),
                holdout_n=a[0],
                holdout_ret=a[1],
                holdout_pf=a[2],
                holdout_dd=a[3],
                holdout_edge=a[4],
                holdout_random_edge=rnd_mean,
                holdout_random_pf=rnd_pf
            ))

    return (
        wf,
        sel,
        rob,
        pd.DataFrame(ho),
        len(e),
        len(fs)
    )

def main():
    ap=argparse.ArgumentParser()

    ap.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT","ETHUSDT","SOLUSDT"]
    )

    ap.add_argument(
        "--intervals",
        nargs="+",
        default=["1h"]
    )

    ap.add_argument(
        "--days",
        type=int,
        default=730
    )

    ap.add_argument(
        "--random-runs",
        type=int,
        default=20
    )

    a=ap.parse_args()

    log(
        f"V4.3.4 | {','.join(a.symbols)} | "
        f"{','.join(a.intervals)} | {a.days}d"
    )

    log(
        f"WF=180/45/45 HOLD=90 | "
        f"RANDOM={a.random_runs}"
    )

    W=[]
    S=[]
    R=[]
    H=[]
    errors=[]

    for sym in a.symbols:
        for iv in a.intervals:
            try:
                w,s,r,h,nf,nw=run_symbol(
                    sym,
                    iv,
                    a.days,
                    a.random_runs
                )

                W.append(w)
                S.append(s)
                R.append(r)
                H.append(h)

                if len(r):
                    rb=r[r.robust]

                    L=int(
                        (rb.side=="LONG").sum()
                    )

                    SRT=int(
                        (rb.side=="SHORT").sum()
                    )

                    log(
                        f"{sym} DONE data={nf} "
                        f"WF={nw} R={len(rb)} "
                        f"L={L} S={SRT}"
                    )
                else:
                    log(
                        f"{sym} DONE data={nf} "
                        f"WF={nw} R=0"
                    )

            except Exception as ex:
                msg=f"{sym}: {type(ex).__name__}: {ex}"
                errors.append(msg)
                log(f"ERROR {msg}")

    wf=(
        pd.concat(W,ignore_index=True)
        if W else pd.DataFrame()
    )

    sel=(
        pd.concat(S,ignore_index=True)
        if S else pd.DataFrame()
    )

    rob=(
        pd.concat(R,ignore_index=True)
        if R else pd.DataFrame()
    )

    ho=(
        pd.concat(H,ignore_index=True)
        if H else pd.DataFrame()
    )

    wf.to_csv(
        OUT/"walk_forward_v43.csv",
        index=False
    )

    sel.to_csv(
        OUT/"selected_v43.csv",
        index=False
    )

    rob.to_csv(
        OUT/"robustness_v43.csv",
        index=False
    )

    ho.to_csv(
        OUT/"holdout_v43.csv",
        index=False
    )

    if len(rob):
        g=rob.groupby(
            [
                "signal","side","family",
                "regime","profile",
                "tp","sl","hold"
            ]
        ).agg(
            symbols=("symbol","nunique"),
            robust_symbols=("robust","sum")
        ).reset_index()
    else:
        g=pd.DataFrame()

    g.to_csv(
        OUT/"global_v43.csv",
        index=False
    )

    (OUT/"summary_v43.md").write_text(
        "\n".join([
            "# SCALP LAB V4.3.4",
            f"WF rows: {len(wf)}",
            f"Selected: {len(sel)}",
            f"Robust: {int(rob.robust.sum()) if len(rob) else 0}",
            f"Holdout: {len(ho)}",
            f"Errors: {len(errors)}"
        ]),
        encoding="utf-8"
    )

    log(
        f"DONE wf={len(wf)} "
        f"sel={len(sel)} "
        f"robust={int(rob.robust.sum()) if len(rob) else 0} "
        f"hold={len(ho)}"
    )

    if errors:
        raise RuntimeError(
            "; ".join(errors)
        )

if __name__=="__main__":
    main()
