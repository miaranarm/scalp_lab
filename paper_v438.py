from __future__ import annotations
import argparse,io,json,warnings
from pathlib import Path
import numpy as np,pandas as pd,requests

warnings.filterwarnings("ignore")

STATE=Path("state/paper_v438.json")
OUT=Path("results"); OUT.mkdir(exist_ok=True)
STATE.parent.mkdir(exist_ok=True)

SYMBOL="SOLUSDT"; TP=3.; SL=1.5; HOLD=36
FEE=.0005; SLIP=.00030
UA={"User-Agent":"Mozilla/5.0"}
COLS=["time","open","high","low","close","volume","ct","qv","trades","tbv","tqv","x"]

def log(x): print(x,flush=True)

def read_zip(b):
    z=pd.read_csv(io.BytesIO(b),compression="zip")
    if "open_time" in z.columns:
        z=z.rename(columns={"open_time":"time"}).iloc[:,:12]
    else:
        z=pd.read_csv(io.BytesIO(b),compression="zip",header=None).iloc[:,:12]
    z.columns=COLS
    z.time=pd.to_numeric(z.time,errors="coerce")
    z=z.dropna(subset=["time"])
    z.time=pd.to_datetime(z.time,unit="ms",utc=True)
    for c in ["open","high","low","close","volume"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")
    return z.dropna(subset=["open","high","low","close"])

def get(url):
    try:
        r=requests.get(url,headers=UA,timeout=30)
        return read_zip(r.content) if r.status_code==200 else None
    except Exception:
        return None

def fetch(symbol,interval,days):
    end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=days)
    base="https://data.binance.vision/data/futures/um"
    rows=[]; p=start.to_period("M")
    q=end.to_period("M")
    while p<=q:
        fn=f"{symbol}-{interval}-{p.year}-{p.month:02d}.zip"
        z=get(f"{base}/monthly/klines/{symbol}/{interval}/{fn}")
        if z is not None: rows.append(z)
        elif p==q:
            d=p.start_time.tz_localize("UTC")
            while d<=end:
                fn=f"{symbol}-{interval}-{d:%Y-%m-%d}.zip"
                z=get(f"{base}/daily/klines/{symbol}/{interval}/{fn}")
                if z is not None: rows.append(z)
                d+=pd.Timedelta(days=1)
        p+=1
    if not rows: raise RuntimeError("No data")
    z=pd.concat(rows,ignore_index=True)
    return z[(z.time>=start)&(z.time<=end)].drop_duplicates("time").sort_values("time").reset_index(drop=True)

def atr(x,n=14):
    tr=pd.concat([
        x.high-x.low,
        (x.high-x.close.shift()).abs(),
        (x.low-x.close.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def build(x,h):
    x=x.copy(); h=h.copy()
    x["dc20"]=x.high.rolling(20).max().shift(1)

    for n in [20,50,200]:
        h[f"e{n}"]=h.close.ewm(span=n,adjust=False).mean()

    step=h.time.diff().mode().iloc[0]
    h["time"]+=step
    h=h[["time","close","e20","e50","e200"]]
    x=pd.merge_asof(x.sort_values("time"),h.sort_values("time"),on="time",
                    direction="backward")
    x["trend"]=np.where((x.e20>x.e50)&(x.e50>x.e200),"trend",
                np.where((x.e20<x.e50)&(x.e50<x.e200),"down","range"))
    x["sig"]=(x.close>x.dc20).fillna(False)
    return x

def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {
        "cash":10000.,
        "equity":10000.,
        "peak":10000.,
        "position":None,
        "trades":[],
        "last_bar":None,
        "started":str(pd.Timestamp.now(tz="UTC"))
    }

def save(s):
    STATE.write_text(json.dumps(s,indent=2,default=str))

def close_trade(s,t,price,reason,time):
    entry=t["entry"]
    ret=(price/entry-1)-2*FEE
    pnl=s["cash"]*ret
    s["cash"]+=pnl
    t.update(exit=float(price),exit_time=str(time),reason=reason,
             ret=float(ret*100),pnl=float(pnl))
    s["trades"].append(t)
    s["position"]=None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=10)
    a=ap.parse_args()

    log("V438 | PAPER FORWARD | SOL DONCHIAN LONG")
    log("TP=3% SL=1.5% HOLD=36h | ALL_TAKER | PAPER ONLY")

    s=load()
    x=fetch(SYMBOL,"1h",a.days)
    h=fetch(SYMBOL,"4h",a.days+10)
    d=build(x,h)

    bar=d.iloc[-1]
    bt=str(bar.time)

    if s["last_bar"]==bt:
        log(f"SKIP | already processed {bt}")
        return

    s["last_bar"]=bt

    # Position ouverte
    if s["position"]:
        p=s["position"]
        age=(bar.time-pd.Timestamp(p["entry_time"])).total_seconds()/3600
        hi=float(bar.high); lo=float(bar.low)

        if lo<=p["sl"]:
            close_trade(s,p,p["sl"],"SL",bar.time)
            log(f"EXIT SL | {p['entry']:.3f}->{p['sl']:.3f}")

        elif hi>=p["tp"]:
            close_trade(s,p,p["tp"],"TP",bar.time)
            log(f"EXIT TP | {p['entry']:.3f}->{p['tp']:.3f}")

        elif age>=HOLD:
            close_trade(s,p,float(bar.close),"TIME",bar.time)
            log(f"EXIT TIME | {bar.close:.3f}")

    # Nouvelle entrée
    if s["position"] is None and bool(bar.sig):
        entry=float(bar.close)*(1+SLIP)
        s["position"]={
            "entry_time":bt,
            "entry":entry,
            "tp":entry*(1+TP/100),
            "sl":entry*(1-SL/100)
        }
        log(f"ENTRY | {bt} | {entry:.3f} | TP={s['position']['tp']:.3f} SL={s['position']['sl']:.3f}")

    s["equity"]=s["cash"]
    if s["position"]:
        s["equity"]*=float(bar.close)/s["position"]["entry"]
    s["peak"]=max(s["peak"],s["equity"])
    dd=(s["equity"]/s["peak"]-1)*100

    tr=pd.DataFrame(s["trades"])
    wins=(tr.ret>0).sum() if not tr.empty else 0
    pf=(tr.loc[tr.ret>0,"ret"].sum()/-tr.loc[tr.ret<0,"ret"].sum()
        if not tr.empty and (tr.ret<0).any() else np.nan)

    log(f"STATUS | BAR={bt} | EQ={s['equity']:.2f} | "
        f"TRADES={len(tr)} | WIN={wins} | PF={pf:.3f} | DD={dd:.2f}%")

    save(s)

    pd.DataFrame(s["trades"]).to_csv(
        OUT/"paper_trades_v438.csv",index=False)

    Path(OUT/"paper_summary_v438.md").write_text(
        f"# V4.3.8\n\n"
        f"- Equity: {s['equity']:.2f}\n"
        f"- Trades: {len(tr)}\n"
        f"- Win rate: {(wins/len(tr)*100 if len(tr) else 0):.1f}%\n"
        f"- PF: {pf:.3f}\n"
        f"- DD: {dd:.2f}%\n"
        f"- Position: {'OPEN' if s['position'] else 'FLAT'}\n",
        encoding="utf-8")

if __name__=="__main__":
    main()
