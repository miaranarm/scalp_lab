```python
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

def log(x=""): print(x,flush=True)

def months(a,b):
    p=pd.Period(a,"M");q=pd.Period(b,"M")
    while p<=q:
        yield p;p+=1

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
            rows.append(z);continue
        if p==end.to_period("M"):
            d=p.start_time.tz_localize("UTC")
            while d<=end:
                fn=f"{symbol}-{iv}-{d:%Y-%m-%d}.zip"
                z=get_file(f"{base}/daily/klines/{symbol}/{iv}/{fn}")
                if z is not None: rows.append(z)
                d+=pd.Timedelta(days=1)
    if not rows: raise RuntimeError(f"no data {symbol} {iv}")
    z=pd.concat(rows,ignore_index=True)
    z=z[(z.time>=start)&(z.time<=end)].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if len(z)<1000: raise RuntimeError(f"insufficient data {symbol} {iv}: {len(z)}")
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
    return pd.merge_asof(x.sort_values("time"),h.sort_values("time"),on="time",direction="backward")

def candidates(x,h):
    x=context(features(x),h)
    x["trend"]=np.where(
        (x.ema20_ctx>x.ema50_ctx)&(x.ema50_ctx>x.ema200_ctx),"trend",
        np.where((x.ema20_ctx<x.ema50_ctx)&(x.ema50_ctx<x.ema200_ctx),"down","range")
    )
    a=[]
    def add(name,mask,side,family):
        y=x[["time","open","high","low","close","atr14","trend"]].copy()
        y["sig"]=mask.fillna(False).to_numpy(bool)
        y["side"]=side;y["family"]=family;a.append((name,y))
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
    c=d.close.to_numpy(float);hi=d.high.to_numpy(float);lo=d.low.to_numpy(float)
    av=d.atr14.to_numpy(float);sig=d.sig.to_numpy(bool)
    side0=int(d.side.iloc[0]);trend=d.trend.to_numpy();n=len(d);i=0;tr=[]
    slip=SLIP.get(symbol,.0002)
    while i<n-2:
        t=trend[i]
        ok=t in ("trend","down") if reg=="trend" else t=="range" if reg=="range" else True
        if not sig[i] or not ok or not np.isfinite(av[i]):
            i+=1;continue
        side=int(rng.choice([-1,1])) if random_side else side0
        j=i+1;limit=c[i];entry=c[j]
        if profile!="taker":
            if side==1 and lo[j]>limit:i+=1;continue
            if side==-1 and hi[j]<limit:i+=1;continue
            entry=limit
        a=av[i]
        if not np.isfinite(a) or a<=0:i+=1;continue
        target=entry+side*tp*a;stop=entry-side*sl*a
        end=min(n,j+hold);exitp=None;reason=""
        for k in range(j,end):
            hit_sl=lo[k]<=stop if side==1 else hi[k]>=stop
            hit_tp=hi[k]>=target if side==1 else lo[k]<=target
            if hit_sl:
                exitp=stop*(1-side*slip);reason="SL";break
            if hit_tp:
                exitp=target*(1-side*slip);reason="TP";break
        if exitp is None:
            k=end-1;exitp=c[k]*(1-side*slip);reason="TIME"
        entry_fee=FM if profile=="maker_both" else FT
        exit_fee=FM if profile in ("maker_tp","maker_both") and reason=="TP" else FT
        tr.append(side*(exitp/entry-1)-entry_fee-exit_fee)
        i=max(j+1,end if reason=="TIME" else k+1)
    if not tr:return 0,0,np.nan,0,np.nan
    r=np.asarray(tr);eq=np.cumprod(1+r);peak=np.maximum.accumulate(eq)
    gp=r[r>0].sum();gl=-r[r<0].sum()
    return len(r),(eq[-1]-1)*100,(gp/gl if gl else np.inf),np.min(eq/peak-1)*100,r.mean()*100

def configs():
    sigs=[
        "vwap48_k2","mean96_k2","vwap48_k3",
        "donchian20_v0","donchian20_v1.5","donchian50_v1.5",
        "zscore48_t2","zscore96_t2.5","pullbackRSI35","pullbackRSI40",
        "vwap48_k2_short","mean96_k2_short","vwap48_k3_short",
        "donchian20_v0_short","donchian20_v1.5_short","donchian50_v1.5_short",
        "zscore48_t2_short","zscore96_t2.5_short",
        "pullbackRSI35_short","pullbackRSI40_short"
    ]
    return [(s,r,p,t,sl,h) for s in sigs for r in REGIMES for p in PROFILES for t,sl,h in EXITS]

def folds(start,end):
    out=[];cur=start+pd.Timedelta(days=TRAIN)
    while cur+pd.Timedelta(days=TEST)<=end:
        out.append((cur-pd.Timedelta(days=TRAIN),cur,cur,cur+pd.Timedelta(days=TEST)))
        cur+=pd.Timedelta(days=STEP)
    return out

def run_symbol(symbol,iv,days):
    e=fetch(symbol,iv,days);h=fetch(symbol,"4h",days+40)
    cs=candidates(e,h);cfg=configs()
    end=e.time.max();wf_end=end-pd.Timedelta(days=HOLD)
    fs=folds(e.time.min(),wf_end)
    if len(fs)<5:raise RuntimeError(f"too few folds {len(fs)}")
    rows=[]
    for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
        log(f"{symbol} FOLD {fi}/{len(fs)}")
        for n,r,p,t,sl,hold in cfg:
            z=cs[n]
            tr=z[(z.time>=tr0)&(z.time<tr1)]
            te=z[(z.time>=te0)&(z.time<te1)]
            a=simulate(tr,r,t,sl,hold,p,symbol)
            b=simulate(te,r,t,sl,hold,p,symbol)
            rows.append(dict(
                symbol=symbol,interval=iv,fold=fi,signal=n,
                side="SHORT" if z.side.iloc[0]<0 else "LONG",
                family=z.family.iloc[0],regime=r,profile=p,tp=t,sl=sl,hold=hold,
                train_n=a[0],train_ret=a[1],test_n=b[0],test_ret=b[1],
                test_pf=b[2],test_dd=b[3],test_edge=b[4],
                train_eligible=a[0]>=MIN_TRAIN and np.isfinite(a[1])
            ))
    wf=pd.DataFrame(rows)
    keys=["symbol","interval","signal","side","family","regime","profile","tp","sl","hold"]
    groups=[]
    for key,g in wf.groupby(keys,dropna=False):
        el=g[g.train_eligible];ac=el[el.test_n>0]
        if not len(el):continue
        groups.append(dict(
            symbol=key[0],interval=key[1],signal=key[2],side=key[3],family=key[4],
            regime=key[5],profile=key[6],tp=key[7],sl=key[8],hold=key[9],
            eligible_folds=len(el),active_folds=len(ac),
            total_trades=int(ac.test_n.sum()),
            mean_oos=ac.test_ret.mean(),median_oos=ac.test_ret.median(),
            positive_fold_ratio=(ac.test_ret>0).mean(),
            median_pf=ac.test_pf.replace([np.inf],np.nan).median(),
            median_dd=ac.test_dd.median(),mean_edge=ac.test_edge.mean()
        ))
    rob=pd.DataFrame(groups)
    if len(rob):
        rob["robust"]=(
            (rob.eligible_folds>=5)&
            (rob.active_folds>=5)&
            (rob.total_trades>=MIN_TRADES)&
            (rob.positive_fold_ratio>=.50)&
            (rob.median_pf>=1)&
            (rob.mean_edge>=0)
        )
    else:rob["robust"]=False
    return wf,rob,len(e),len(fs),cs,wf_end

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",nargs="+",default=["BTCUSDT","ETHUSDT","SOLUSDT"])
    ap.add_argument("--intervals",nargs="+",default=["1h"])
    ap.add_argument("--days",type=int,default=730)
    ap.add_argument("--top",type=int,default=10)
    ap.add_argument("--random-runs",type=int,default=20)
    a=ap.parse_args()

    log(f"V4.3.5 | {','.join(a.symbols)} | {','.join(a.intervals)} | {a.days}d")
    log(f"STABILITY | WF=180/45/45 HOLD=90 | TOP={a.top} RANDOM={a.random_runs}")

    ALL_W=[];ALL_R=[];STAB=[];HOLD=[];errors=[]

    for sym in a.symbols:
        for iv in a.intervals:
            try:
                wf,rob,n,nf,cs,wf_end=run_symbol(sym,iv,a.days)
                ALL_W.append(wf);ALL_R.append(rob)
                rb=rob[rob.robust].copy()
                rb=rb.sort_values(
                    ["median_oos","median_pf","positive_fold_ratio","total_trades"],
                    ascending=False
                ).head(a.top)

                for _,q in rb.iterrows():
                    z=cs[str(q.signal)]
                    periods=[
                        ("H1",wf_end-pd.Timedelta(days=180),wf_end-pd.Timedelta(days=90)),
                        ("H2",wf_end-pd.Timedelta(days=90),wf_end),
                        ("HO",wf_end,wf_end+pd.Timedelta(days=90))
                    ]
                    for pn,p0,p1 in periods:
                        d=z[(z.time>=p0)&(z.time<p1)]
                        x=simulate(d,str(q.regime),float(q.tp),float(q.sl),int(q.hold),str(q.profile),sym)
                        STAB.append(dict(
                            symbol=sym,signal=q.signal,side=q.side,family=q.family,
                            regime=q.regime,profile=q.profile,tp=q.tp,sl=q.sl,hold=q.hold,
                            wf_median=q.median_oos,wf_pf=q.median_pf,
                            period=pn,n=x[0],ret=x[1],pf=x[2],dd=x[3],edge=x[4]
                        ))
                    d=z[z.time>=wf_end]
                    x=simulate(d,str(q.regime),float(q.tp),float(q.sl),int(q.hold),str(q.profile),sym)
                    re=[];rp=[]
                    for seed in range(a.random_runs):
                        rr=simulate(d,str(q.regime),float(q.tp),float(q.sl),int(q.hold),str(q.profile),sym,True,np.random.default_rng(seed))
                        re.append(rr[4]);rp.append(rr[2])
                    HOLD.append(dict(
                        symbol=sym,signal=q.signal,side=q.side,family=q.family,
                        regime=q.regime,profile=q.profile,tp=q.tp,sl=q.sl,hold=q.hold,
                        wf_median=q.median_oos,wf_pf=q.median_pf,
                        holdout_n=x[0],holdout_ret=x[1],holdout_pf=x[2],
                        holdout_dd=x[3],holdout_edge=x[4],
                        random_edge=np.nanmean(re),random_pf=np.nanmedian(rp)
                    ))

                log(f"{sym} DONE data={n} WF={nf} robust={len(rb)}")

            except Exception as ex:
                msg=f"{sym}: {type(ex).__name__}: {ex}"
                errors.append(msg);log(f"ERROR {msg}")

    wf=pd.concat(ALL_W,ignore_index=True) if ALL_W else pd.DataFrame()
    rob=pd.concat(ALL_R,ignore_index=True) if ALL_R else pd.DataFrame()
    stab=pd.DataFrame(STAB);ho=pd.DataFrame(HOLD)

    wf.to_csv(OUT/"walk_forward_v435.csv",index=False)
    rob.to_csv(OUT/"robustness_v435.csv",index=False)
    stab.to_csv(OUT/"stability_v435.csv",index=False)
    ho.to_csv(OUT/"holdout_v435.csv",index=False)

    if len(stab):
        s=stab.groupby(
            ["symbol","signal","side","family","regime","profile","tp","sl","hold"]
        ).agg(
            periods=("period","count"),
            positive_periods=("ret",lambda x:int((x>0).sum())),
            mean_ret=("ret","mean"),
            median_ret=("ret","median"),
            mean_pf=("pf","mean"),
            worst_dd=("dd","min")
        ).reset_index()
    else:s=pd.DataFrame()

    s.to_csv(OUT/"stability_summary_v435.csv",index=False)

    Path(OUT/"summary_v435.md").write_text(
        "\n".join([
            "# SCALP LAB V4.3.5",
            f"WF rows: {len(wf)}",
            f"Robust: {int(rob.robust.sum()) if len(rob) else 0}",
            f"Stability rows: {len(stab)}",
            f"Holdout rows: {len(ho)}",
            f"Errors: {len(errors)}"
        ]),
        encoding="utf-8"
    )

    log(f"DONE wf={len(wf)} robust={int(rob.robust.sum()) if len(rob) else 0} stability={len(stab)} holdout={len(ho)} errors={len(errors)}")
    if errors:raise RuntimeError("; ".join(errors))

if __name__=="__main__":
    main()
```

### 2. `.github/workflows/v435-test.yml`

```yaml
name: SCALP LAB V4.3.5

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install
        run: |
          python -m pip install -q --upgrade pip
          pip install -q requests==2.32.5 pandas==2.2.3 numpy==2.1.3

      - name: Clean
        run: |
          rm -rf results
          mkdir -p results

      - name: Run
        run: |
          python -u research_v435.py \
            --symbols BTCUSDT ETHUSDT SOLUSDT \
            --intervals 1h \
            --days 730 \
            --top 10 \
            --random-runs 20

      - name: Results
        if: always()
        run: |
          cat results/summary_v435.md 2>/dev/null || true
          ls -lh results/ 2>/dev/null || true

      - name: Upload
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scalp-lab-v435-results
          path: results/*
          retention-days: 30
```

### Ce que V4.3.5 va nous apporter

Cette fois, on ne demande **plus** au programme de nous dire simplement « voici le meilleur ».

Il va produire notamment :

* `stability_v435.csv` → comportement des **10 meilleures configurations robustes** sur plusieurs périodes ;
* `stability_summary_v435.csv` → synthèse de leur stabilité ;
* `holdout_v435.csv` → comparaison détaillée avec le random ;
* `robustness_v435.csv` → toutes les configurations robustes ;
* `walk_forward_v435.csv` → toutes les évaluations WF.

Le point essentiel sera de regarder **si les meilleures configurations restent positives lorsqu'on change de période**.

**Lance le workflow V4.3.5.** Ensuite envoie-moi `stability_summary_v435.csv` et `holdout_v435.csv` : ce sera beaucoup plus révélateur que le simple nombre de configurations robustes.
