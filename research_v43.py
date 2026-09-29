from __future__ import annotations
import argparse,io,warnings
from pathlib import Path
import requests,numpy as np,pandas as pd

warnings.filterwarnings("ignore")
OUT=Path("results");OUT.mkdir(exist_ok=True)

TRAIN,TEST,STEP,HOLD=180,45,45,90
MIN_TRAIN,MIN_TRADES=50,50
FT,FM=.0005,.0002
SLIP={"BTCUSDT":.00010,"ETHUSDT":.00015,"SOLUSDT":.00030}
UA={"User-Agent":"Mozilla/5.0"}
COLS=["time","open","high","low","close","volume","ct","qv","trades","tbv","tqv","x"]

def log(x): print(x,flush=True)

def months(a,b):
    p=pd.Period(a,"M");q=pd.Period(b,"M")
    while p<=q:
        yield p
        p+=1

def read_zip(content):
    z=pd.read_csv(io.BytesIO(content),compression="zip")
    if "open_time" not in z.columns:
        z=pd.read_csv(io.BytesIO(content),compression="zip",header=None).iloc[:,:12]
        z.columns=COLS
    else:
        z=z.rename(columns={"open_time":"time"}).iloc[:,:12]
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
    if not rows: raise RuntimeError(f"no data {symbol} {iv}")
    z=pd.concat(rows,ignore_index=True)
    z=z[(z.time>=start)&(z.time<=end)].drop_duplicates("time")
    return z.sort_values("time").reset_index(drop=True)

def atr(x,n=14):
    h,l,c=x.high,x.low,x.close
    return pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1).rolling(n).mean()

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
    h=h[["time","close","ema20_ctx","ema50_ctx","ema200_ctx","atr14_ctx"]]
    h=h.rename(columns={"close":"close_ctx"})
    step=h.time.diff().mode().iloc[0]
    h["time"]+=step
    return pd.merge_asof(
        x.sort_values("time"),h.sort_values("time"),
        on="time",direction="backward"
    )

def candidates(x,h):
    x=context(features(x),h)
    x["trend"]=np.where(
        (x.ema20_ctx>x.ema50_ctx)&(x.ema50_ctx>x.ema200_ctx),"trend",
        np.where(
            (x.ema20_ctx<x.ema50_ctx)&(x.ema50_ctx<x.ema200_ctx),
            "down","range"
        )
    )
    a=[]
    def add(name,mask,side,family):
        y=x[["time","open","high","low","close","atr14","trend"]].copy()
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

EXITS=[(1.5,1,12),(2,1,24),(3,1.5,36),(2,2,24)]
PROFILES=["taker","maker_tp","maker_both"]
REGIMES=["all","trend","range"]

def simulate(d,reg,tp,sl,hold,profile,symbol,random_side=False,rng=None):
    if len(d)<3:return 0,0,np.nan,0,np.nan

    c=d.close.to_numpy(float)
    hi=d.high.to_numpy(float)
    lo=d.low.to_numpy(float)
    av=d.atr14.to_numpy(float)
    sig=d.sig.to_numpy(bool)
    side0=int(d.side.iloc[0])
    trend=d.trend.to_numpy()
    n=len(d);i=0;tr=[]
    slip=SLIP.get(symbol,.0002)

    while i<n-2:
        t=trend[i]
        ok=(t in ("trend","down") if reg=="trend"
            else t=="range" if reg=="range" else True)

        if not sig[i] or not ok or not np.isfinite(av[i]):
            i+=1
            continue

        side=int(rng.choice([-1,1])) if random_side else side0
        j=i+1
        limit=c[i]
        entry=c[j]

        if profile!="taker":
            if side==1 and lo[j]>limit:
                i+=1;continue
            if side==-1 and hi[j]<limit:
                i+=1;continue
            entry=limit

        a=av[i]
        if not np.isfinite(a) or a<=0:
            i+=1;continue

        target=entry+side*tp*a
        stop=entry-side*sl*a
        end=min(n,j+hold)
        exitp=None
        reason=""

        for k in range(j,end):
            hit_sl=lo[k]<=stop if side==1 else hi[k]>=stop
            hit_tp=hi[k]>=target if side==1 else lo[k]<=target
            if hit_sl:
                exitp=stop*(1-side*slip);reason="SL";break
            if hit_tp:
                exitp=target*(1-side*slip);reason="TP";break

        if exitp is None:
            k=end-1
            exitp=c[k]*(1-side*slip)
            reason="TIME"

        ef=FM if profile=="maker_both" else FT
        xf=FM if profile in ("maker_tp","maker_both") and reason=="TP" else FT
        tr.append(side*(exitp/entry-1)-ef-xf)
        i=max(j+1,end if reason=="TIME" else k+1)

    if not tr:return 0,0,np.nan,0,np.nan

    r=np.asarray(tr)
    eq=np.cumprod(1+r)
    peak=np.maximum.accumulate(eq)
    gp=r[r>0].sum()
    gl=-r[r<0].sum()

    return (
        len(r),
        (eq[-1]-1)*100,
        gp/gl if gl else np.inf,
        np.min(eq/peak-1)*100,
        r.mean()*100
    )

def configs():
    sigs=[
        "vwap48_k2","mean96_k2","vwap48_k3",
        "donchian20_v0","donchian20_v1.5","donchian50_v1.5",
        "zscore48_t2","zscore96_t2.5","pullbackRSI35","pullbackRSI40",
        "vwap48_k2_short","mean96_k2_short","vwap48_k3_short",
        "donchian20_v0_short","donchian20_v1.5_short",
        "donchian50_v1.5_short","zscore48_t2_short",
        "zscore96_t2.5_short","pullbackRSI35_short","pullbackRSI40_short"
    ]
    return [(s,r,p,t,sl,h) for s in sigs for r in REGIMES
            for p in PROFILES for t,sl,h in EXITS]

def folds(start,end):
    out=[]
    cur=start+pd.Timedelta(days=TRAIN)
    while cur+pd.Timedelta(days=TEST)<=end:
        out.append((cur-pd.Timedelta(days=TRAIN),cur,cur,cur+pd.Timedelta(days=TEST)))
        cur+=pd.Timedelta(days=STEP)
    return out

def run_symbol(symbol,iv,days):
    e=fetch(symbol,iv,days)
    h=fetch(symbol,"4h",days+40)
    cs=candidates(e,h)
    cfg=configs()
    end=e.time.max()
    wf_end=end-pd.Timedelta(days=HOLD)
    fs=folds(e.time.min(),wf_end)

    if len(fs)<5:
        raise RuntimeError(f"folds={len(fs)}")

    rows=[]

    for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
        for n,r,p,t,sl,hold in cfg:
            z=cs[n]
            tr=z[(z.time>=tr0)&(z.time<tr1)]
            te=z[(z.time>=te0)&(z.time<te1)]
            a=simulate(tr,r,t,sl,hold,p,symbol)
            b=simulate(te,r,t,sl,hold,p,symbol)

            rows.append({
                "s":symbol,"f":fi,"sig":n,
                "side":"S" if z.side.iloc[0]<0 else "L",
                "fam":z.family.iloc[0],"reg":r,"prof":p,
                "tp":t,"sl":sl,"h":hold,
                "tn":a[0],"tr":a[1],"n":b[0],
                "ret":b[1],"pf":b[2],"dd":b[3],"edge":b[4],
                "ok":a[0]>=MIN_TRAIN and np.isfinite(a[1])
            })

    wf=pd.DataFrame(rows)

    keys=["s","sig","side","fam","reg","prof","tp","sl","h"]
    groups=[]

    for key,g in wf.groupby(keys,dropna=False):
        el=g[g.ok]
        ac=el[el.n>0]
        if not len(el):continue

        groups.append({
            "s":key[0],"sig":key[1],"side":key[2],"fam":key[3],
            "reg":key[4],"prof":key[5],"tp":key[6],"sl":key[7],"h":key[8],
            "ef":len(el),"af":len(ac),"trades":int(ac.n.sum()),
            "mean":ac.ret.mean(),"med":ac.ret.median(),
            "pos":(ac.ret>0).mean(),
            "pf":ac.pf.replace([np.inf],np.nan).median(),
            "dd":ac.dd.median(),"edge":ac.edge.mean()
        })

    rob=pd.DataFrame(groups)

    if len(rob):
        rob["robust"]=(
            (rob.ef>=5)&(rob.af>=5)&(rob.trades>=MIN_TRADES)&
            (rob.pos>=.50)&(rob.pf>=1)&(rob.edge>=0)
        )
    else:
        rob["robust"]=False

    return wf,rob,len(e),len(fs),cs,wf_end

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",nargs="+",default=["BTCUSDT","ETHUSDT","SOLUSDT"])
    ap.add_argument("--intervals",nargs="+",default=["1h"])
    ap.add_argument("--days",type=int,default=730)
    ap.add_argument("--top",type=int,default=10)
    ap.add_argument("--random-runs",type=int,default=20)
    a=ap.parse_args()

    log(f"V435 | {','.join(a.symbols)} | {a.days}d")

    ALL_W=[];ALL_R=[];STAB=[];HOLD=[];errors=[]

    for sym in a.symbols:
        for iv in a.intervals:
            try:
                wf,rob,n,nf,cs,wf_end=run_symbol(sym,iv,a.days)
                ALL_W.append(wf)
                ALL_R.append(rob)

                rb=rob[rob.robust].sort_values(
                    ["med","pf","pos","trades"],
                    ascending=False
                ).head(a.top)

                for _,q in rb.iterrows():
                    z=cs[str(q.sig)]

                    periods=[
                        ("H1",wf_end-pd.Timedelta(days=180),wf_end-pd.Timedelta(days=90)),
                        ("H2",wf_end-pd.Timedelta(days=90),wf_end),
                        ("HO",wf_end,wf_end+pd.Timedelta(days=90))
                    ]

                    for pn,p0,p1 in periods:
                        d=z[(z.time>=p0)&(z.time<p1)]
                        x=simulate(
                            d,str(q.reg),float(q.tp),float(q.sl),
                            int(q.h),str(q.prof),sym
                        )
                        STAB.append({
                            "s":sym,"sig":q.sig,"side":q.side,"fam":q.fam,
                            "reg":q.reg,"prof":q.prof,
                            "tp":q.tp,"sl":q.sl,"h":q.h,
                            "wf":q.med,"pf_wf":q.pf,
                            "period":pn,"n":x[0],"ret":x[1],
                            "pf":x[2],"dd":x[3],"edge":x[4]
                        })

                    d=z[z.time>=wf_end]
                    x=simulate(
                        d,str(q.reg),float(q.tp),float(q.sl),
                        int(q.h),str(q.prof),sym
                    )

                    re=[];rp=[]
                    for seed in range(a.random_runs):
                        rr=simulate(
                            d,str(q.reg),float(q.tp),float(q.sl),
                            int(q.h),str(q.prof),sym,
                            True,np.random.default_rng(seed)
                        )
                        re.append(rr[4]);rp.append(rr[2])

                    HOLD.append({
                        "s":sym,"sig":q.sig,"side":q.side,"fam":q.fam,
                        "reg":q.reg,"prof":q.prof,
                        "tp":q.tp,"sl":q.sl,"h":q.h,
                        "wf":q.med,"pf_wf":q.pf,
                        "n":x[0],"ret":x[1],"pf":x[2],"dd":x[3],
                        "edge":x[4],"rnd_edge":np.nanmean(re),
                        "rnd_pf":np.nanmedian(rp)
                    })

                log(f"{sym}: data={n} folds={nf} robust={int(rob.robust.sum())} top={len(rb)}")

            except Exception as ex:
                msg=f"{sym}:{type(ex).__name__}:{ex}"
                errors.append(msg)
                log("ERR "+msg)

    wf=pd.concat(ALL_W,ignore_index=True) if ALL_W else pd.DataFrame()
    rob=pd.concat(ALL_R,ignore_index=True) if ALL_R else pd.DataFrame()
    stab=pd.DataFrame(STAB)
    ho=pd.DataFrame(HOLD)

    wf.to_csv(OUT/"walk_forward_v435.csv",index=False)
    rob.to_csv(OUT/"robustness_v435.csv",index=False)
    stab.to_csv(OUT/"stability_v435.csv",index=False)
    ho.to_csv(OUT/"holdout_v435.csv",index=False)

    if len(stab):
        ss=stab.groupby(
            ["s","sig","side","fam","reg","prof","tp","sl","h"]
        ).agg(
            periods=("period","count"),
            positive=("ret",lambda x:int((x>0).sum())),
            mean=("ret","mean"),
            median=("ret","median"),
            pf=("pf","mean"),
            worst_dd=("dd","min")
        ).reset_index()
    else:
        ss=pd.DataFrame()

    ss.to_csv(OUT/"stability_summary_v435.csv",index=False)

    summary="\n".join([
        "# V435",
        f"WF={len(wf)}",
        f"ROBUST={int(rob.robust.sum()) if len(rob) else 0}",
        f"STAB={len(stab)}",
        f"HO={len(ho)}",
        f"ERR={len(errors)}"
    ])

    Path(OUT/"summary_v435.md").write_text(summary,encoding="utf-8")
    log(f"DONE WF={len(wf)} ROB={int(rob.robust.sum()) if len(rob) else 0} STAB={len(stab)} HO={len(ho)} ERR={len(errors)}")

    if errors:
        raise RuntimeError(";".join(errors))

if __name__=="__main__":
    main()
