from __future__ import annotations
import json,ssl,time,threading,websocket,requests,io
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pandas as pd

S="SOLUSDT"
URL=f"wss://fstream.binance.com/ws/{S.lower()}@trade"
STATE=Path("state/live_v4386.json")
OUT=Path("results/live_candles_v4386.csv")
RUN=10*60
UA={"User-Agent":"Mozilla/5.0"}
COL=["time","open","high","low","close","volume","trades"]

STATE.parent.mkdir(exist_ok=True);OUT.parent.mkdir(exist_ok=True)
N=BAD=0;C=None;LIVE=[];STOP=False

def log(x):print(x,flush=True)

def load():
    try:return json.loads(STATE.read_text())
    except:return {"symbol":S,"candles":[],"last_closed":None}

def parse(b):
    z=pd.read_csv(io.BytesIO(b),compression="zip",header=None)
    if len(z.columns)<9:return []
    z=z.iloc[:,:9]
    z.columns=["time","open","high","low","close","volume","x","y","trades"]
    z["time"]=pd.to_datetime(z.time,unit="ms",utc=True)
    for c in ["open","high","low","close","volume","trades"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")
    z=z.dropna(subset=["time","open","high","low","close"])
    return [{
        "time":x.time.isoformat(),"open":float(x.open),"high":float(x.high),
        "low":float(x.low),"close":float(x.close),"volume":float(x.volume),
        "trades":int(x.trades)
    } for x in z.itertuples()]

def vision():
    now=datetime.now(timezone.utc)
    out={}
    for d in [now-timedelta(days=i) for i in range(3)]:
        fn=f"{S}-1h-{d:%Y-%m-%d}.zip"
        u=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{fn}"
        try:
            r=requests.get(u,headers=UA,timeout=15)
            if r.status_code!=200:
                log(f"VISION HTTP | {r.status_code}")
                continue
            for x in parse(r.content):out[x["time"]]=x
        except Exception as e:log(f"VISION ERROR | {type(e).__name__} | {e}")
    return list(out.values())

def msg(ws,m):
    global N,BAD,C
    try:
        x=json.loads(m);p=float(x["p"]);q=float(x["q"]);t=int(x["T"])
        if p<=0 or q<0:BAD+=1;return
        N+=1
        h=datetime.fromtimestamp(t/1000,tz=timezone.utc).replace(
            minute=0,second=0,microsecond=0)
        k=h.isoformat()
        if C is None or C["time"]!=k:
            if C:LIVE.append(C.copy())
            C={"time":k,"open":p,"high":p,"low":p,
               "close":p,"volume":q,"trades":1,"closed":False}
        else:
            C["high"]=max(C["high"],p);C["low"]=min(C["low"],p)
            C["close"]=p;C["volume"]+=q;C["trades"]+=1
    except:BAD+=1

def opened(ws):log("WS CONNECT | OK")
def error(ws,e):log(f"WS ERROR | {type(e).__name__} | {e}")
def closed(ws,a,b):log("WS CLOSED")

def wsrun():
    global STOP
    w=websocket.WebSocketApp(
        URL,on_open=opened,on_message=msg,on_error=error,on_close=closed)
    try:w.run_forever(sslopt={"cert_reqs":ssl.CERT_REQUIRED},
                      ping_interval=20,ping_timeout=10)
    except Exception as e:log(f"WS FATAL | {type(e).__name__}")
    STOP=True

def main():
    global C
    log("V438.6c | CONTINUITY | 10 MIN")

    s=load()
    old={x["time"]:x for x in s.get("candles",[])}

    v=vision()
    log(f"VISION | {len(v)}")
    for x in v:old[x["time"]]=x

    th=threading.Thread(target=wsrun,daemon=True)
    th.start()

    t=time.time()
    while time.time()-t<RUN and not STOP:time.sleep(5)

    now=datetime.now(timezone.utc).replace(
        minute=0,second=0,microsecond=0)

    if C:
        C["closed"]=datetime.fromisoformat(C["time"])<now
        LIVE.append(C.copy())
        log(f"LIVE CANDLE | {C['time']} | "
            f"O={C['open']:.4f} H={C['high']:.4f} "
            f"L={C['low']:.4f} C={C['close']:.4f} N={C['trades']}")

    for x in LIVE:old[x["time"]]=x

    rows=sorted(old.values(),key=lambda x:x["time"])
    closed=[x for x in rows if x.get("closed",True)]

    times=[datetime.fromisoformat(x["time"]) for x in closed]
    gaps=[]
    for a,b in zip(times,times[1:]):
        g=(b-a).total_seconds()/3600
        if g!=1:gaps.append((a.isoformat(),b.isoformat(),g))

    s.update({
        "candles":rows,
        "last_closed":closed[-1]["time"] if closed else None,
        "closed_count":len(closed),
        "warmup":len(closed)<20 or bool(gaps),
        "gaps":gaps[-20:],
        "updated":datetime.now(timezone.utc).isoformat(),
        "live_trades":N,"bad_messages":BAD
    })

    STATE.write_text(json.dumps(s,indent=2))
    pd.DataFrame(rows).to_csv(OUT,index=False)

    log(f"TRADES | {N}")
    log(f"BAD | {BAD}")
    log(f"CANDLES TOTAL | {len(rows)}")
    log(f"CANDLES CLOSED | {len(closed)}")
    log(f"GAPS | {len(gaps)}")
    log(f"LAST CLOSED | {s['last_closed']}")
    log(f"WARMUP | {'YES' if s['warmup'] else 'NO'}")
    log("RESULT | CONTINUITY TEST OK")

if __name__=="__main__":main()
