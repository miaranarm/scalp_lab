from __future__ import annotations
import argparse,io,json,warnings
from pathlib import Path
import numpy as np,pandas as pd,requests

warnings.filterwarnings("ignore")

SYMBOL="SOLUSDT";TP=3.;SL=1.5;HOLD=36
CAPITAL=10000.;FEE=.0005;SLIP=.00030
STATE=Path("state/paper_v438.json")
OUT=Path("results")
STATE.parent.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
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
    z["time"]=pd.to_numeric(z.time,errors="coerce")
    z=z.dropna(subset=["time"])
    z["time"]=pd.to_datetime(z.time,unit="ms",utc=True)
    for c in ["open","high","low","close","volume"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")
    return z.dropna(subset=["open","high","low","close"])

def vision(symbol,interval,days):
    end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=days)
    base="https://data.binance.vision/data/futures/um"
    rows=[];p=start.to_period("M");q=end.to_period("M")

    while p<=q:
        fn=f"{symbol}-{interval}-{p.year}-{p.month:02d}.zip"
        url=f"{base}/monthly/klines/{symbol}/{interval}/{fn}"
        try:
            r=requests.get(url,headers=UA,timeout=30)
            z=read_zip(r.content) if r.status_code==200 else None
        except Exception:z=None

        if z is not None: rows.append(z)
        elif p==q:
            d=p.start_time.tz_localize("UTC")
            while d<=end:
                fn=f"{symbol}-{interval}-{d:%Y-%m-%d}.zip"
                url=f"{base}/daily/klines/{symbol}/{interval}/{fn}"
                try:
                    r=requests.get(url,headers=UA,timeout=20)
                    z=read_zip(r.content) if r.status_code==200 else None
                except Exception:z=None
                if z is not None: rows.append(z)
                d+=pd.Timedelta(days=1)
        p+=1

    if not rows:return pd.DataFrame()
    z=pd.concat(rows,ignore_index=True)
    return z[(z.time>=start)&(z.time<=end)].drop_duplicates("time").sort_values("time").reset_index(drop=True)

def fetch_live(symbol,interval,days=10):
    end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=days)
    rows=[]

    try:
        r=requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={
                "symbol":symbol,"interval":interval,
                "startTime":int(start.timestamp()*1000),
                "endTime":int(end.timestamp()*1000),
                "limit":1500
            },
            headers=UA,timeout=30
        )
        if r.status_code==200:
            for k in r.json():
                rows.append([k[0],k[1],k[2],k[3],k[4],k[5],
                             k[6],k[7],k[8],k[9],k[10],k[11]])
    except Exception as e:
        log(f"REST fallback | {e}")

    if rows:
        z=pd.DataFrame(rows,columns=COLS)
        z["time"]=pd.to_datetime(pd.to_numeric(z.time),unit="ms",utc=True)
        for c in ["open","high","low","close","volume"]:
            z[c]=pd.to_numeric(z[c],errors="coerce")
        z=z.dropna(subset=["open","high","low","close"])
        log(f"LIVE | REST {len(z)} candles")
        return z.sort_values("time").reset_index(drop=True)

    log("LIVE | REST unavailable -> Vision")
    z=vision(symbol,interval,days)
    log(f"LIVE | VISION {len(z)} candles")
    return z

def build(x,h):
    x=x.copy();h=h.copy()
    x["dc20"]=x.high.rolling(20).max().shift(1)

    for n in [20,50,200]:
        h[f"e{n}"]=h.close.ewm(span=n,adjust=False).mean()

    step=h.time.diff().mode().iloc[0]
    h["time"]+=step
    h=h[["time","close","e20","e50","e200"]].rename(columns={"close":"ctx_close"})

    x=pd.merge_asof(
        x.sort_values("time"),
        h.sort_values("time"),
        on="time",direction="backward"
    )

    x["trend"]=np.where(
        (x.e20>x.e50)&(x.e50>x.e200),"trend",
        np.where((x.e20<x.e50)&(x.e50<x.e200),"down","range")
    )
    x["sig"]=(x.close>x.dc20).fillna(False)
    return x

def load():
    if STATE.exists():return json.loads(STATE.read_text())
    return {
        "cash":CAPITAL,"equity":CAPITAL,"peak":CAPITAL,
        "position":None,"trades":[],"last_bar":None,
        "started":str(pd.Timestamp.now(tz="UTC"))
    }

def save(s):
    STATE.write_text(json.dumps(s,indent=2,default=str))

def close_trade(s,p,price,reason,time):
    entry=p["entry"]
    gross=price/entry-1
    net=gross-2*FEE
    pnl=s["cash"]*net
    s["cash"]+=pnl

    p.update({
        "exit":float(price),
        "exit_time":str(time),
        "reason":reason,
        "gross_pct":gross*100,
        "ret_pct":net*100,
        "pnl":pnl
    })

    s["trades"].append(p)
    s["position"]=None

def process_bar(s,bar):
    bt=str(bar.time)

    if s["position"]:
        p=s["position"]
        age=(pd.Timestamp(bar.time)-pd.Timestamp(p["entry_time"])).total_seconds()/3600
        lo=float(bar.low);hi=float(bar.high)

        if lo<=p["sl"]:
            close_trade(s,p,p["sl"],"SL",bar.time)
            log(f"EXIT SL | {bt} | {p['sl']:.3f}")
        elif hi>=p["tp"]:
            close_trade(s,p,p["tp"],"TP",bar.time)
            log(f"EXIT TP | {bt} | {p['tp']:.3f}")
        elif age>=HOLD:
            close_trade(s,p,float(bar.close),"TIME",bar.time)
            log(f"EXIT TIME | {bt} | {bar.close:.3f}")

    if s["position"] is None and bool(bar.sig):
        entry=float(bar.open)*(1+SLIP)
        p={
            "entry_time":bt,
            "entry":entry,
            "tp":entry*(1+TP/100),
            "sl":entry*(1-SL/100)
        }
        s["position"]=p
        log(f"ENTRY | {bt} | {entry:.3f} | TP={p['tp']:.3f} | SL={p['sl']:.3f}")

    s["last_bar"]=bt

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=10)
    a=ap.parse_args()

    log("V438.1 | PAPER FORWARD")
    log("SOLUSDT | DONCHIAN20 | LONG")
    log("TP=3% | SL=1.5% | HOLD=36h | ALL_TAKER")

    s=load()
    x=fetch_live(SYMBOL,"1h",a.days)
    h=fetch_live(SYMBOL,"4h",a.days+10)

    if len(x)<30 or len(h)<200:
        raise RuntimeError(f"Insufficient data: 1h={len(x)} 4h={len(h)}")

    d=build(x,h)
    now=pd.Timestamp.now(tz="UTC").floor("h")
    closed=d[d.time<now].copy()

    if closed.empty:raise RuntimeError("No closed candle")

    if s["last_bar"]:
        last=pd.Timestamp(s["last_bar"])
        todo=closed[closed.time>last]
    else:
        todo=closed.tail(1)

    log(f"DATA | 1h={len(x)} 4h={len(h)}")
    log(f"PROCESS | {len(todo)} closed bars")

    for _,bar in todo.iterrows():
        log(f"BAR | {bar.time}")
        process_bar(s,bar)

    last=closed.iloc[-1]
    s["equity"]=s["cash"]

    if s["position"]:
        s["equity"]*=float(last.close)/s["position"]["entry"]

    s["peak"]=max(s["peak"],s["equity"])
    dd=(s["equity"]/s["peak"]-1)*100

    tr=pd.DataFrame(s["trades"]);n=len(tr)

    if n:
        wins=int((tr.ret_pct>0).sum())
        gains=tr.loc[tr.ret_pct>0,"ret_pct"].sum()
        losses=-tr.loc[tr.ret_pct<0,"ret_pct"].sum()
        pf=gains/losses if losses else np.inf
    else:
        wins=0;pf=np.nan

    log(
        f"STATUS | EQ={s['equity']:.2f} | CASH={s['cash']:.2f} | "
        f"TRADES={n} | WIN={wins} | PF={pf:.3f} | DD={dd:.2f}% | "
        f"POS={'OPEN' if s['position'] else 'FLAT'}"
    )

    save(s)

    if n:
        tr.to_csv(OUT/"paper_trades_v438.csv",index=False)

    Path(OUT/"paper_summary_v438.md").write_text(
        "\n".join([
            "# SCALP LAB V4.3.8.1",
            "",
            "- SOLUSDT / Donchian20 / LONG",
            "- TP 3% / SL 1.5% / HOLD 36h",
            "- ALL_TAKER / PAPER ONLY",
            f"- Equity: {s['equity']:.2f}",
            f"- Cash: {s['cash']:.2f}",
            f"- Trades: {n}",
            f"- Win rate: {wins/n*100 if n else 0:.1f}%",
            f"- PF: {pf:.3f}",
            f"- DD: {dd:.2f}%",
            f"- Position: {'OPEN' if s['position'] else 'FLAT'}",
            f"- Last bar: {s['last_bar']}"
        ]),
        encoding="utf-8"
    )

    log("DONE V438.1")

if __name__=="__main__":
    main()
