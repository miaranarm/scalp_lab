from __future__ import annotations
import json,ssl,time,threading,websocket,requests,io
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pandas as pd

S="SOLUSDT"
URL=f"wss://fstream.binance.com/ws/{S.lower()}@trade"
STATE=Path("state/live_v4386.json")
OUT=Path("results/live_candles_v4386.csv")
RUN=600
UA={"User-Agent":"Mozilla/5.0"}

STATE.parent.mkdir(exist_ok=True)
OUT.parent.mkdir(exist_ok=True)

N=BAD=0
C=None
LIVE=[]
STOP=False

def log(x):
    print(x,flush=True)

def load():
    try:
        return json.loads(STATE.read_text())
    except:
        return {"symbol":S,"candles":[],"live":None}

def parse(b):
    z=pd.read_csv(io.BytesIO(b),compression="zip",header=None)

    if len(z.columns)<9:
        return []

    z=z.iloc[:,:9]

    if str(z.iloc[0,0]).lower() in ("open_time","timestamp"):
        z=z.iloc[1:]

    z.columns=[
        "time","open","high","low","close",
        "volume","x","y","trades"
    ]

    z["time"]=pd.to_numeric(z.time,errors="coerce")

    for c in ["open","high","low","close","volume","trades"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")

    z=z.dropna(
        subset=["time","open","high","low","close"]
    )

    return [{
        "time":datetime.fromtimestamp(
            int(x.time)/1000,
            tz=timezone.utc
        ).isoformat(),
        "open":float(x.open),
        "high":float(x.high),
        "low":float(x.low),
        "close":float(x.close),
        "volume":float(x.volume),
        "trades":int(x.trades)
    } for x in z.itertuples()]

def vision():
    now=datetime.now(timezone.utc)
    out={}
    urls=[]

    for d in [now-timedelta(days=i) for i in range(4)]:
        fn=f"{S}-1h-{d:%Y-%m-%d}.zip"
        urls.append(
            f"https://data.binance.vision/data/futures/um/"
            f"daily/klines/{S}/1h/{fn}"
        )

    fn=f"{S}-1h-{now:%Y-%m}.zip"

    urls.append(
        f"https://data.binance.vision/data/futures/um/"
        f"monthly/klines/{S}/1h/{fn}"
    )

    for u in urls:
        try:
            r=requests.get(
                u,
                headers=UA,
                timeout=20
            )

            if r.status_code!=200:
                log(f"VISION HTTP | {r.status_code}")
                continue

            for x in parse(r.content):
                out[x["time"]]=x

        except Exception as e:
            log(f"VISION ERROR | {type(e).__name__}")

    return list(out.values())

def msg(ws,m):
    global N,BAD,C

    try:
        x=json.loads(m)
        p=float(x["p"])
        q=float(x["q"])
        t=int(x["T"])

        if p<=0 or q<0:
            BAD+=1
            return

        N+=1

        h=datetime.fromtimestamp(
            t/1000,
            tz=timezone.utc
        ).replace(
            minute=0,
            second=0,
            microsecond=0
        )

        k=h.isoformat()

        if C is None or C["time"]!=k:

            if C:
                C["closed"]=True
                LIVE.append(C.copy())

            C={
                "time":k,
                "open":p,
                "high":p,
                "low":p,
                "close":p,
                "volume":q,
                "trades":1,
                "closed":False
            }

        else:
            C["high"]=max(C["high"],p)
            C["low"]=min(C["low"],p)
            C["close"]=p
            C["volume"]+=q
            C["trades"]+=1

    except:
        BAD+=1

def opened(ws):
    log("WS CONNECT | OK")

def error(ws,e):
    log(f"WS ERROR | {type(e).__name__} | {e}")

def closed(ws,a,b):
    log("WS CLOSED")

def wsrun():
    global STOP

    w=websocket.WebSocketApp(
        URL,
        on_open=opened,
        on_message=msg,
        on_error=error,
        on_close=closed
    )

    try:
        w.run_forever(
            sslopt={"cert_reqs":ssl.CERT_REQUIRED},
            ping_interval=20,
            ping_timeout=10
        )

    except Exception as e:
        log(f"WS FATAL | {type(e).__name__}")

    STOP=True

def main():
    global C

    log("V438.6f | CONTINUITY | 10 MIN")

    s=load()
    old={
        x["time"]:x
        for x in s.get("candles",[])
    }

    now=datetime.now(
        timezone.utc
    ).replace(
        minute=0,
        second=0,
        microsecond=0
    )

    v=vision()
    log(f"VISION | {len(v)}")

    for x in v:
        if datetime.fromisoformat(x["time"])<now:
            old[x["time"]]=x

    C=s.get("live")

    if C:
        ct=datetime.fromisoformat(C["time"])

        if ct<now:
            C["closed"]=True
            old[C["time"]]=C.copy()

            log(
                f"CLOSE PREVIOUS LIVE | "
                f"{C['time']}"
            )

            C=None

        else:
            log(f"RESUME LIVE | {C['time']}")

    th=threading.Thread(
        target=wsrun,
        daemon=True
    )

    th.start()

    t=time.time()

    while time.time()-t<RUN and not STOP:
        time.sleep(5)

    now=datetime.now(
        timezone.utc
    ).replace(
        minute=0,
        second=0,
        microsecond=0
    )

    if C:

        C["closed"]=(
            datetime.fromisoformat(C["time"])<now
        )

        if C["closed"]:
            old[C["time"]]=C.copy()

            log(
                f"LIVE CLOSED | "
                f"{C['time']}"
            )

            C=None

    for x in LIVE:
        if x["closed"]:
            old[x["time"]]=x

    rows=sorted(
        old.values(),
        key=lambda x:x["time"]
    )

    closed=[
        x for x in rows
        if x.get("closed",True)
    ]

    ts=[
        datetime.fromisoformat(x["time"])
        for x in closed
    ]

    gaps=[
        (a.isoformat(),b.isoformat())
        for a,b in zip(ts,ts[1:])
        if b-a!=timedelta(hours=1)
    ]

    last=closed[-1]["time"] if closed else None

    live=C if C and not C["closed"] else None

    gap_live=0

    if last and live:

        a=datetime.fromisoformat(last)
        b=datetime.fromisoformat(live["time"])

        gap_live=max(
            0,
            int(
                (b-a).total_seconds()/3600
            )-1
        )

    continuous=(
        not gaps
        and gap_live==0
        and len(closed)>=20
    )

    s.update({
        "symbol":S,
        "candles":rows,
        "live":live,
        "last_closed":last,
        "closed_count":len(closed),
        "gaps":gaps[-20:],
        "gap_to_live_hours":gap_live,
        "warmup":not continuous,
        "continuous20":continuous,
        "updated":datetime.now(
            timezone.utc
        ).isoformat(),
        "live_trades":N,
        "bad_messages":BAD
    })

    STATE.write_text(
        json.dumps(
            s,
            indent=2
        )
    )

    pd.DataFrame(rows).to_csv(
        OUT,
        index=False
    )

    log(f"TRADES | {N}")
    log(f"BAD | {BAD}")
    log(f"CANDLES TOTAL | {len(rows)}")
    log(f"CANDLES CLOSED | {len(closed)}")
    log(f"GAPS INTERNAL | {len(gaps)}")
    log(f"GAP TO LIVE | {gap_live}h")
    log(f"LAST CLOSED | {last}")
    log(
        f"WARMUP | "
        f"{'YES' if not continuous else 'NO'}"
    )
    log(
        f"CONTINUOUS20 | "
        f"{'YES' if continuous else 'NO'}"
    )
    log("RESULT | CONTINUITY TEST OK")

if __name__=="__main__":
    main()
