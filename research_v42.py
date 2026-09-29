"""
SCALP LAB V4.2 — robustesse statistique Binance USD-M
"""
from __future__ import annotations
import argparse,io,math,time,zipfile
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests

BASE="https://data.binance.vision/data/futures/um"
MS={"5m":300000,"15m":900000,"1h":3600000,"4h":14400000}
FT,FM,TH=0.0005,0.0002,0.00005
SLIP={"BTCUSDT":.0001,"ETHUSDT":.00015,"SOLUSDT":.0003}
EXITS=((1.5,1,12),(2,1,24),(3,1.5,36),(2,2,24))
PROFILES=("taker","maker_tp","maker_both")
TRAIN,TEST,HOLD,STEP=180,45,90,45
MIN_TRAIN=50
MIN_FOLDS=5
MIN_TRADES=50
MIN_POS=.50
MIN_RANDOM=.50
MIN_PF=1.
MIN_EDGE=0.
RANDOM_RUNS=100
MC_RUNS=5000
SEED=20260928
CAPITAL=100.
CTX={"5m":"1h","15m":"1h","1h":"4h"}
WARM={"1h":12,"4h":40}
SIGNALS=(
("vwap",{"n":48,"k":2}),("vwap",{"n":96,"k":2}),
("vwap",{"n":48,"k":3}),("donchian",{"n":20,"vol":0}),
("donchian",{"n":20,"vol":1.5}),("donchian",{"n":50,"vol":1.5}),
("zscore",{"n":30,"thr":2}),("zscore",{"n":60,"thr":2.5}),
("pullback",{"rsi":35}),("pullback",{"rsi":40}),("breakout",{"n":20}))
REGIMES=("all","trend","range")


# ============================================================
# DATA
# ============================================================

def unzip_csv(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        raw=z.read(z.namelist()[0]).decode()
    return [r[:12] for r in (x.split(",") for x in raw.splitlines())
            if r and r[0].isdigit()]

def fetch(symbol,iv,a,b):
    out=[]; step=MS[iv]
    s=datetime.fromtimestamp(a/1000,timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    e=datetime.fromtimestamp(b/1000,timezone.utc)
    while s<e:
        n=s.replace(year=s.year+1,month=1) if s.month==12 else s.replace(month=s.month+1)
        aa=max(s.timestamp()*1000,a); bb=min(n.timestamp()*1000-step,b)
        if aa<=bb:
            u=f"{BASE}/monthly/klines/{symbol}/{iv}/{symbol}-{iv}-{s:%Y-%m}.zip"
            try:r=requests.get(u,timeout=60)
            except requests.RequestException:r=None
            if r is not None and r.ok: out+=unzip_csv(r.content)
            else:
                d=datetime.fromtimestamp(aa/1000,timezone.utc).date()
                z=datetime.fromtimestamp(bb/1000,timezone.utc).date()
                while d<=z:
                    u=f"{BASE}/daily/klines/{symbol}/{iv}/{symbol}-{iv}-{d}.zip"
                    try:q=requests.get(u,timeout=30)
                    except requests.RequestException:q=None
                    if q is not None and q.ok: out+=unzip_csv(q.content)
                    d+=pd.Timedelta(days=1)
        s=n
    return out

def frame(rows):
    cols=["time","open","high","low","close","volume","x","q","n","tb","tq","i"]
    d=pd.DataFrame(rows,columns=cols)
    for c in cols[:6]: d[c]=pd.to_numeric(d[c],errors="coerce")
    return d.dropna(subset=cols[:6]).drop_duplicates("time").sort_values("time").reset_index(drop=True)


# ============================================================
# FEATURES
# ============================================================

def features(d):
    c,h,l,v=d.close,d.high,d.low,d.volume
    p=c.shift()
    tr=pd.concat([h-l,(h-p).abs(),(l-p).abs()],axis=1).max(axis=1)
    du=c.diff(); up=du.clip(lower=0); dn=-du.clip(upper=0)
    au=up.ewm(alpha=1/14,adjust=False).mean()
    ad=dn.ewm(alpha=1/14,adjust=False).mean()
    rsi=100-100/(1+au/ad.replace(0,np.nan))
    atr=tr.ewm(alpha=1/14,adjust=False).mean()
    e9=c.ewm(span=9,adjust=False).mean()
    e20=c.ewm(span=20,adjust=False).mean()
    e50=c.ewm(span=50,adjust=False).mean()
    e200=c.ewm(span=200,adjust=False).mean()
    z=(c-c.rolling(20).mean())/c.rolling(20).std().replace(0,np.nan)
    vr=v/v.rolling(20).mean().replace(0,np.nan)
    typ=(h+l+c)/3
    return {
        "c":c.to_numpy(float),"h":h.to_numpy(float),"l":l.to_numpy(float),
        "v":v.to_numpy(float),"rsi":rsi.to_numpy(float),"atr":atr.to_numpy(float),
        "ema9":e9.to_numpy(float),"ema20":e20.to_numpy(float),
        "ema50":e50.to_numpy(float),"ema200":e200.to_numpy(float),
        "z20":z.to_numpy(float),"vol_ratio":vr.to_numpy(float),
        "vwap48":((typ*v).rolling(48).sum()/v.rolling(48).sum()).to_numpy(float),
        "vwap96":((typ*v).rolling(96).sum()/v.rolling(96).sum()).to_numpy(float),
        "atr_pct":(atr/c).to_numpy(float),"ret":c.pct_change().to_numpy(float),
        "ema20_slope":e20.pct_change(6).to_numpy(float),
        "ema50_slope":e50.pct_change(12).to_numpy(float),
        "ema_sep":((e20-e50)/c).to_numpy(float),
        "dist200":((c-e200)/e200).to_numpy(float)
    }

def context(entry,h1,iv):
    f=features(h1)
    keys=("c","ema20","ema50","ema200","atr","rsi","ema20_slope","ema50_slope","ema_sep","dist200")
    x=pd.DataFrame({"time":h1.time.to_numpy(),**{k:f[k] for k in keys}})
    x.time+=MS[iv]
    e=pd.DataFrame({"time":entry.time.to_numpy()})
    a=pd.merge_asof(e.sort_values("time"),x.sort_values("time"),on="time",direction="backward")
    c,e20,e50,e200,s20,s50,sep,d200=[a[k].to_numpy(float) for k in
        ("c","ema20","ema50","ema200","ema20_slope","ema50_slope","ema_sep","dist200")]
    valid=np.isfinite(np.column_stack([c,e20,e50,e200,s20,s50,sep,d200])).all(1)
    up=valid&(e20>e50)&(c>e200)&(sep>=.0025)&(d200<=.045)
    dn=valid&(e20<e50)&(c<e200)&(sep<=-.0025)&(d200>=-.045)
    return {
        "all":valid,"trend":up|dn,
        "range":valid&(abs(sep)<.0025)&(abs(d200)<.02),
        "trend_up":up,"trend_down":dn
    }

@dataclass
class Candidate:
    name:str
    signal:np.ndarray
    regime:str

def sig(long,short):
    x=np.zeros(len(long),dtype=np.int8)
    x[long]=1;x[short]=-1
    return x

def signal(name,p,f):
    c,h,l=f["c"],f["h"],f["l"]
    if name=="vwap":
        dist=(c-f[f"vwap{p['n']}"])/f["atr"]
        return sig(dist<-p["k"],dist>p["k"])
    if name=="donchian":
        n=p["n"]
        hi=pd.Series(h).rolling(n).max().shift(1).to_numpy()
        lo=pd.Series(l).rolling(n).min().shift(1).to_numpy()
        vr=f["vol_ratio"]
        return sig((c>hi)&(vr>p["vol"]),(c<lo)&(vr>p["vol"]))
    if name=="zscore":
        z=(pd.Series(c)-pd.Series(c).rolling(p["n"]).mean())/pd.Series(c).rolling(p["n"]).std().replace(0,np.nan)
        return sig(z.to_numpy()<-p["thr"],z.to_numpy()>p["thr"])
    if name=="pullback":
        r=f["rsi"]
        up=(f["ema20"]>f["ema50"])&(c>f["ema200"])
        dn=(f["ema20"]<f["ema50"])&(c<f["ema200"])
        return sig(up&(r<p["rsi"]),dn&(r>100-p["rsi"]))
    if name=="breakout":
        n=p["n"]
        hi=pd.Series(h).rolling(n).max().shift(1).to_numpy()
        lo=pd.Series(l).rolling(n).min().shift(1).to_numpy()
        a=f["atr_pct"]; base=pd.Series(a).rolling(50).mean().to_numpy()
        return sig((c>hi)&(a>base),(c<lo)&(a>base))
    raise ValueError(name)

def candidates(entry,h1,iv):
    f=features(entry); m=context(entry,h1,iv); out=[]
    for name,p in SIGNALS:
        s=signal(name,p,f)
        label=name+" "+" ".join(f"{k}={v}" for k,v in p.items())
        for reg in REGIMES:
            x=s.copy(); x[~m[reg]]=0
            if np.any(x): out.append(Candidate(label,x,reg))
    return f,out


# ============================================================
# SIMULATION
# ============================================================

def simulate(L,s,tp,sl,hold,profile,slip,fee_scale=1.,slip_scale=1.):
    c,h,l,a=L["c"],L["h"],L["l"],L["atr"]
    slip*=slip_scale
    maker_tp=profile in ("maker_tp","maker_both")
    out=[]; free=0
    for j in np.flatnonzero(s):
        if j<free or j+1>=len(c) or not np.isfinite(a[j]) or a[j]<=0: continue
        side=int(s[j]); atr=a[j]
        if profile=="maker_both":
            if side==1 and l[j+1]>c[j]*(1-TH): continue
            if side==-1 and h[j+1]<c[j]*(1+TH): continue
            entry=c[j]; ef=FM*fee_scale
        else:
            entry=c[j+1]*(1+side*slip); ef=FT*fee_scale
        tp_px=entry+side*tp*atr; sl_px=entry-side*sl*atr
        tp_touch=tp_px*(1+side*TH) if maker_tp else tp_px
        end=min(j+hold,len(c)-1); ex=end; px=c[end]; kind="time"
        for k in range(j+1,end+1):
            hit_tp=h[k]>=tp_touch if side==1 else l[k]<=tp_touch
            hit_sl=l[k]<=sl_px if side==1 else h[k]>=sl_px
            if hit_sl:
                ex=k;px=sl_px*(1-side*slip);kind="sl";break
            if hit_tp:
                ex=k;px=tp_px if maker_tp else tp_px*(1-side*slip);kind="tp";break
        if kind=="time": px*=1-side*slip
        xf=(FM if kind=="tp" and profile!="taker" else FT)*fee_scale
        gross=side*(px-entry)/entry
        net=(1+gross)*(1-ef)*(1-xf)-1
        out.append({"signal_i":j,"entry_i":j+1,"exit_i":ex,"gross":gross,
                    "net":net,"kind":kind,"side":side,"duration":ex-j})
        free=ex+1
    return out

def inside(tr,a,b):
    return [t for t in tr if a<=t["signal_i"]<b and a<=t["entry_i"]<b and t["exit_i"]<b]


# ============================================================
# STATS
# ============================================================

def empty():
    return {k:np.nan for k in ("mean","se","t","gross","fees","win","pf","median","p25","p75","dd","ret")}|{"n":0}

def stats(tr):
    if not tr:return empty()
    n=np.array([x["net"] for x in tr],float); g=np.array([x["gross"] for x in tr],float)
    n=n[np.isfinite(n)];g=g[np.isfinite(g)]
    if not len(n):return empty()
    eq=np.cumprod(1+n);dd=(eq/np.maximum.accumulate(eq)-1)
    win=n[n>0];loss=n[n<0]
    pf=np.sum(win)/abs(np.sum(loss)) if len(loss) else np.inf
    mean=float(n.mean());se=n.std(ddof=1)/math.sqrt(len(n)) if len(n)>1 else np.nan
    return {"n":len(n),"mean":mean,"se":se,
            "t":mean/se if np.isfinite(se) and se>0 else np.nan,
            "gross":float(g.mean()),"fees":float(g.mean()-mean),
            "win":float(np.mean(n>0)),"pf":pf,"median":float(np.median(n)),
            "p25":float(np.percentile(n,25)),"p75":float(np.percentile(n,75)),
            "dd":float(dd.min()),"ret":float(eq[-1]-1)}

def score(s):
    if s["n"]<MIN_TRAIN or not np.isfinite(s["mean"]):return -np.inf
    pf=2 if np.isinf(s["pf"]) else np.clip(s["pf"]-1,-1,2)
    mean=np.clip(s["mean"]*1000,-2,2);dd=np.clip(abs(s["dd"])*10,0,2)
    tc=np.clip(s["t"],-3,3)/3 if np.isfinite(s["t"]) else 0
    nc=min(math.log1p(s["n"])/math.log1p(150),1)
    return .35*tc+.30*pf+.20*(mean/2)+.15*nc-.15*dd


# ============================================================
# BENCHMARKS / MC
# ============================================================

def mc(trades,capital,runs,seed):
    if runs<=0 or len(trades)<20:
        return {"enabled":False,"median":np.nan,"p05":np.nan,"p95":np.nan,"dd":np.nan}
    r=np.array([x["net"] for x in trades],float);r=r[np.isfinite(r)]
    if len(r)<20:return {"enabled":False,"median":np.nan,"p05":np.nan,"p95":np.nan,"dd":np.nan}
    rng=np.random.default_rng(seed);fin=[];dds=[]
    for _ in range(int(runs)):
        x=rng.choice(r,len(r),replace=True);eq=capital*np.cumprod(1+x)
        fin.append(float(eq[-1]));dds.append(float(np.min(eq/np.maximum.accumulate(eq)-1)))
    return {"enabled":True,"median":float(np.median(fin)),
            "p05":float(np.percentile(fin,5)),"p95":float(np.percentile(fin,95)),
            "dd":float(np.median(dds))}

def random_mc(L,s,tp,sl,hold,profile,slip,a,b,seed,runs=100):
    if runs<=0:return {"mean":np.nan,"se":np.nan,"n":0,"p05":np.nan,"p95":np.nan}
    idx=np.flatnonzero(s)
    if not len(idx):return {"mean":np.nan,"se":np.nan,"n":0,"p05":np.nan,"p95":np.nan}
    vals=[];ns=[]
    for i in range(runs):
        x=np.zeros(len(s),dtype=np.int8)
        x[idx]=np.random.default_rng(seed+i).choice([-1,1],len(idx))
        z=stats(inside(simulate(L,x,tp,sl,hold,profile,slip),a,b))
        if np.isfinite(z["mean"]):vals.append(z["mean"]);ns.append(z["n"])
    if not vals:return {"mean":np.nan,"se":np.nan,"n":0,"p05":np.nan,"p95":np.nan}
    x=np.array(vals)
    return {"mean":float(x.mean()),
            "se":float(x.std(ddof=1)/math.sqrt(len(x))) if len(x)>1 else np.nan,
            "n":int(round(np.mean(ns))),"p05":float(np.percentile(x,5)),
            "p95":float(np.percentile(x,95))}

def fixed(L,a,b,hold=12):
    s=np.zeros(len(L["c"]),dtype=np.int8);s[a:b:hold]=1
    return simulate(L,s,2,1,hold,"taker",SLIP.get("DEFAULT",.0003))

def buyhold(L,a,b):
    if b<=a+1:return []
    e,x=L["c"][a],L["c"][b-1]
    if not np.isfinite(e) or e<=0:return []
    g=x/e-1;net=(1+g)*(1-FT)**2-1
    return [{"signal_i":a,"entry_i":a,"exit_i":b-1,"gross":g,"net":net}]


# ============================================================
# WF / ROBUSTESSE
# ============================================================

def folds(n,iv):
    bars=86400000//MS[iv];tr=TRAIN*bars;te=TEST*bars;usable=n-HOLD*bars
    out=[];s=0
    while s+tr+te<=usable:
        out.append((s,s+tr,s+tr,s+tr+te));s+=STEP*bars
    return out,usable

def finite_median(x):
    x=pd.to_numeric(x,errors="coerce");x=x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan

def robustness(wf):
    if wf.empty:return pd.DataFrame()
    oos=wf[wf.fold!="FINAL"]
    if oos.empty:return pd.DataFrame()
    cols=["symbol","interval","signal","regime","profile","tp","sl","hold"];out=[]
    for key,g in oos.groupby(cols,dropna=False):
        n=pd.to_numeric(g.test_n,errors="coerce").fillna(0)
        g=g[n>0]
        if g.empty:continue
        means=pd.to_numeric(g.test_mean,errors="coerce");means=means[np.isfinite(means)]
        if not len(means):continue
        edges=pd.to_numeric(g.edge_vs_random,errors="coerce");edges=edges[np.isfinite(edges)]
        pf=finite_median(g.test_pf);dd=finite_median(g.test_dd)
        pos=float(np.mean(means>0))
        beat=float(np.mean(edges>0)) if len(edges) else 0
        mededge=float(np.median(edges)) if len(edges) else np.nan
        mean=float(means.mean());std=float(means.std(ddof=1)) if len(means)>1 else np.nan
        t=mean/(std/math.sqrt(len(means))) if np.isfinite(std) and std>0 else np.nan
        nf=len(g);nt=int(pd.to_numeric(g.test_n,errors="coerce").fillna(0).sum())
        stability=(pos+beat)/2
        pfc=np.clip(pf-1,-1,2);pfc=(pfc+1)/3 if np.isfinite(pf) else 0
        ec=np.clip(mededge,-.01,.01);ec=(ec+.01)/.02 if np.isfinite(mededge) else 0
        sample=min(1,nt/200);fold=min(1,nf/10)
        consistency=max(0,1-min(std/.01,1)) if np.isfinite(std) and std>0 else 0
        rs=.25*stability+.18*pfc+.18*ec+.12*sample+.12*fold+.15*consistency
        robust=(nf>=MIN_FOLDS and nt>=MIN_TRADES and pos>=MIN_POS and
                beat>=MIN_RANDOM and np.isfinite(pf) and pf>=MIN_PF and
                np.isfinite(mededge) and mededge>=MIN_EDGE)
        out.append(dict(zip(cols,key),active_folds=nf,total_trades=nt,
            mean_oos=mean,median_oos=float(np.median(means)),std_oos=std,t_oos=t,
            positive_fold_ratio=pos,beat_random_ratio=beat,median_pf=pf,
            median_dd=dd,mean_edge_random=float(edges.mean()) if len(edges) else np.nan,
            median_edge_random=mededge,robustness_score=rs,robust=robust))
    return pd.DataFrame(out)

def global_robust(r):
    if r.empty:return pd.DataFrame()
    cols=["interval","signal","regime","profile","tp","sl","hold"];out=[]
    for key,g in r.groupby(cols,dropna=False):
        out.append(dict(zip(cols,key),
            symbols=g.symbol.nunique(),robust_symbols=int(g.robust.sum()),
            total_trades=int(g.total_trades.sum()),mean_oos=float(g.mean_oos.mean()),
            positive_fold_ratio=float(g.positive_fold_ratio.mean()),
            beat_random_ratio=float(g.beat_random_ratio.mean()),
            median_pf=finite_median(g.median_pf),
            median_edge_random=finite_median(g.median_edge_random)))
    x=pd.DataFrame(out)
    x["global_robust"]=((x.symbols>=3)&(x.robust_symbols>=2)&(x.total_trades>=150)&
        (x.positive_fold_ratio>=.5)&(x.beat_random_ratio>=.5)&
        (x.median_pf>=1)&(x.median_edge_random>=0))
    return x.sort_values(["global_robust","median_edge_random","median_pf","total_trades"],
                         ascending=False).reset_index(drop=True)


# ============================================================
# MAIN
# ============================================================

def pct(x):
    try:x=float(x)
    except:return "nan"
    return f"{x*100:+.4f}%" if np.isfinite(x) else "nan"

def num(x,d=2):
    try:x=float(x)
    except:return "nan"
    return f"{x:.{d}f}" if np.isfinite(x) else "nan"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--intervals",default="5m,15m")
    ap.add_argument("--days",type=int,default=730)
    ap.add_argument("--capital",type=float,default=CAPITAL)
    ap.add_argument("--mc-runs",type=int,default=MC_RUNS)
    a=ap.parse_args()

    t0=time.time();out=Path("results");out.mkdir(exist_ok=True)
    for f in ["walk_forward_v42.csv","robustness_v42.csv","global_v42.csv",
              "stress_test_v42.csv","holdout_v42.csv","summary_v42.md"]:
        p=out/f
        if p.exists():p.unlink()

    syms=[x.strip() for x in a.symbols.split(",") if x.strip()]
    ivs=[x.strip() for x in a.intervals.split(",") if x.strip()]
    end=int(time.time()*1000);start=end-a.days*86400000
    rows=[];holds=[];stress_rows=[]

    print(f"V4.2 | {','.join(syms)} | {','.join(ivs)} | {a.days}j | MC={a.mc_runs}")

    for iv in ivs:
        for sym in syms:
            tic=time.time();ctx=CTX.get(iv,"1h")
            entry=frame(fetch(sym,iv,start,end))
            h1=frame(fetch(sym,ctx,start-WARM.get(ctx,12)*86400000,end))
            minbars=int((TRAIN+TEST+HOLD)*86400000/MS[iv]*.5)
            if len(entry)<minbars or len(h1)<200:
                print(f"{sym} {iv} | SKIP data {len(entry)}/{len(h1)}")
                continue

            entry=entry[entry.time>=start].reset_index(drop=True)
            fs,hs=folds(len(entry),iv)
            L,cands=candidates(entry,h1,ctx)
            print(f"{sym} {iv} | candles={len(entry)} candidates={len(cands)} folds={len(fs)}")

            for fi,(tr0,tr1,te0,te1) in enumerate(fs,1):
                best=None
                for ci,c in enumerate(cands):
                    for tp,sl,hold in EXITS:
                        for prof in PROFILES:
                            tr=inside(simulate(L,c.signal,tp,sl,hold,prof,SLIP.get(sym,.0003)),tr0,tr1)
                            st=stats(tr);sc=score(st)
                            if best is None or sc>best["score"]:
                                best={"ci":ci,"c":c,"tp":tp,"sl":sl,"hold":hold,
                                      "prof":prof,"score":sc,"tr":st}
                if best is None or not np.isfinite(best["score"]):
                    continue

                tt=inside(simulate(L,best["c"].signal,best["tp"],best["sl"],best["hold"],
                                   best["prof"],SLIP.get(sym,.0003)),te0,te1)
                ts=stats(tt);m=mc(tt,a.capital,a.mc_runs,SEED+fi)
                rm=random_mc(L,best["c"].signal,best["tp"],best["sl"],best["hold"],
                             best["prof"],SLIP.get(sym,.0003),te0,te1,SEED+fi*1000,RANDOM_RUNS)
                edge=ts["mean"]-rm["mean"] if np.isfinite(ts["mean"]) and np.isfinite(rm["mean"]) else np.nan
                bh=stats(buyhold(L,te0,te1))

                rows.append({
                    "symbol":sym,"interval":iv,"fold":fi,"candidate":best["ci"],
                    "signal":best["c"].name,"regime":best["c"].regime,"profile":best["prof"],
                    "tp":best["tp"],"sl":best["sl"],"hold":best["hold"],
                    "train_n":best["tr"]["n"],"train_mean":best["tr"]["mean"],"train_pf":best["tr"]["pf"],
                    "test_n":ts["n"],"test_gross":ts["gross"],"test_mean":ts["mean"],
                    "test_se":ts["se"],"test_t":ts["t"],"test_fees":ts["fees"],
                    "test_win":ts["win"],"test_pf":ts["pf"],"test_median":ts["median"],
                    "test_p25":ts["p25"],"test_p75":ts["p75"],"test_dd":ts["dd"],"test_return":ts["ret"],
                    "mc_enabled":m["enabled"],"mc_median":m["median"],"mc_p05":m["p05"],
                    "mc_p95":m["p95"],"mc_dd":m["dd"],
                    "bench_random_mean":rm["mean"],"bench_random_se":rm["se"],
                    "bench_random_p05":rm["p05"],"bench_random_p95":rm["p95"],
                    "bench_random_n":rm["n"],"edge_vs_random":edge,"bench_bh_return":bh["ret"]
                })

            wf=pd.DataFrame([x for x in rows if x["symbol"]==sym and x["interval"]==iv])
            rob=robustness(wf)
            good=rob[rob.robust].copy() if not rob.empty else pd.DataFrame()

            if not good.empty:
                good=good.sort_values(["robustness_score","median_edge_random","median_pf"],ascending=False)
                q=good.iloc[0]
                ci=next((i for i,c in enumerate(cands)
                         if c.name==q.signal and c.regime==q.regime),None)
                if ci is not None:
                    tr=inside(simulate(L,cands[ci].signal,float(q.tp),float(q.sl),int(q.hold),
                                       q.profile,SLIP.get(sym,.0003)),hs,len(entry))
                    z=stats(tr);m=mc(tr,a.capital,a.mc_runs,SEED+999)
                    holds.append({"symbol":sym,"interval":iv,"signal":q.signal,"regime":q.regime,
                        "profile":q.profile,"tp":q.tp,"sl":q.sl,"hold":q.hold,
                        "robust_active_folds":q.active_folds,"robust_total_trades":q.total_trades,
                        "robust_positive_ratio":q.positive_fold_ratio,
                        "robust_beat_random_ratio":q.beat_random_ratio,
                        "robust_median_pf":q.median_pf,"robust_median_edge_random":q.median_edge_random,
                        "robustness_score":q.robustness_score,"holdout_n":z["n"],
                        "holdout_mean":z["mean"],"holdout_t":z["t"],"holdout_pf":z["pf"],
                        "holdout_dd":z["dd"],"holdout_return":z["ret"],
                        "mc_enabled":m["enabled"],"mc_median":m["median"],
                        "mc_p05":m["p05"],"mc_p95":m["p95"],"mc_dd":m["dd"]})
                    print(f"  HOLDOUT | {q.signal} | {pct(z['mean'])} | PF={num(z['pf'])} | n={z['n']}")
            else:
                print("  HOLDOUT | NOT RUN — no robust configuration")

            print(f"  done {sym} {iv} | {((time.time()-tic)/60):.1f} min")

    wf=pd.DataFrame(rows)
    rob=robustness(wf)
    glob=global_robust(rob)
    hold=pd.DataFrame(holds)

    wf.to_csv(out/"walk_forward_v42.csv",index=False)
    rob.to_csv(out/"robustness_v42.csv",index=False)
    glob.to_csv(out/"global_v42.csv",index=False)
    hold.to_csv(out/"holdout_v42.csv",index=False)

    report=[
        "# SCALP LAB V4.2",
        "",
        f"- History : {a.days} jours",
        f"- TRAIN/TEST/STEP : {TRAIN}/{TEST}/{STEP} jours",
        f"- HOLDOUT : {HOLD} jours",
        f"- MC : {a.mc_runs}",
        f"- Robustesse : folds>={MIN_FOLDS}, trades>={MIN_TRADES}, "
        f"positifs>={MIN_POS:.0%}, >random>={MIN_RANDOM:.0%}, PF>={MIN_PF}",
        "",
        "## Résultat",
        ""
    ]

    if rob.empty:
        report.append("Aucune configuration analysable.")
    else:
        report.append(f"- Configurations analysées : {len(rob)}")
        report.append(f"- Configurations robustes : {int(rob.robust.sum())}")
        if not hold.empty:
            report.append(f"- Holdouts exécutés : {len(hold)}")
        else:
            report.append("- Holdouts exécutés : 0")

    report += [
        "",
        "## Limites",
        "",
        "- OHLCV uniquement.",
        "- Pas de funding, carnet d'ordres ou latence réelle.",
        "- Priorité SL si TP et SL sont touchés dans la même bougie.",
        "- Exécution maker approximée.",
        "- Le holdout final n'intervient jamais dans le filtre de robustesse.",
        "- Un fold avec n=0 n'est pas actif.",
        "- Une absence de configuration robuste est un résultat valide."
    ]

    (out/"summary_v42.md").write_text("\n".join(report)+"\n",encoding="utf-8")

    print("")
    print(f"V4.2 TERMINÉ | {len(wf)} folds | robustes={int(rob.robust.sum()) if not rob.empty else 0} | "
          f"holdouts={len(hold)} | {((time.time()-t0)/60):.1f} min")

if __name__=="__main__":
    main()
