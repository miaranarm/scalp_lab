import json,time,requests
from pathlib import Path
from datetime import datetime,timezone,timedelta

S="SOLUSDT"
STATE=Path("state/live_v438.json")
OUT=Path("results/live_candles_v438.csv")
TF=3600000

def log(x): print(x,flush=True)

def dt(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc)

def load():
    if not STATE.exists(): return {},None
    s=json.loads(STATE.read_text())
    return s.get("candles",{}),s.get("live")

def save(old,live):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(
        {"candles":old,"live":live},
        indent=2,sort_keys=True
    ))

def api(url,p):
    try:
        r=requests.get(url,params=p,timeout=15)
        log(f"API {r.status_code} | {url.split('/')[2]}")
        if r.status_code==200:
            return r.json()
    except Exception as e:
        log(f"API ERR | {type(e).__name__}")
    return []

def get_klines(a,b):
    p={
        "symbol":S,"interval":"1h",
        "startTime":a,"endTime":b,
        "limit":1000
    }

    hosts=[
        "https://fapi.binance.com/fapi/v1/klines",
        "https://fapi1.binance.com/fapi/v1/klines",
        "https://fapi2.binance.com/fapi/v1/klines",
        "https://fapi3.binance.com/fapi/v1/klines",
        "https://fapi4.binance.com/fapi/v1/klines",
    ]

    for u in hosts:
        x=api(u,p)
        if x:
            return x,"REST"

    return [],None

def normalize(rows):
    out={}
    for r in rows:
        try:
            t=int(r[0])
            if len(r)<6: continue
            out[dt(t).isoformat()]={
                "time":dt(t).isoformat(),
                "open":float(r[1]),
                "high":float(r[2]),
                "low":float(r[3]),
                "close":float(r[4]),
                "volume":float(r[5]),
                "trades":int(r[8]) if len(r)>8 else 0,
                "closed":True
            }
        except: pass
    return out

def main():
    log("V438.BACKFILL | START")

    old,live=load()

    if not old:
        log("NO HISTORY")
        return

    times=sorted(old)
    last=datetime.fromisoformat(times[-1])
    log(f"LAST CLOSED | {last.isoformat()}")

    if not live:
        log("NO LIVE")
        return

    lt=datetime.fromisoformat(live["time"])
    log(f"LIVE | {lt.isoformat()}")

    missing=[]
    t=last+timedelta(hours=1)

    while t<lt:
        if t.isoformat() not in old:
            missing.append(t)
        t+=timedelta(hours=1)

    log(f"MISSING | {len(missing)}")

    if not missing:
        log("BACKFILL | NOTHING")
        return

    a=int(missing[0].timestamp()*1000)
    b=int((missing[-1]+timedelta(hours=1)).timestamp()*1000)-1

    log(f"REQUEST | {missing[0].isoformat()} -> {missing[-1].isoformat()}")

    rows,src=get_klines(a,b)

    if not rows:
        log("BACKFILL | NO DATA")
        return

    got=normalize(rows)
    log(f"BACKFILL | {len(got)} CANDLES | {src}")

    n=0
    for t in missing:
        k=t.isoformat()
        if k in got:
            old[k]=got[k]
            n+=1

    save(old,live)

    times=sorted(old)
    gaps=0
    for a,b in zip(times,times[1:]):
        x=datetime.fromisoformat(a)
        y=datetime.fromisoformat(b)
        gaps+=max(0,int((y-x).total_seconds()/3600)-1)

    last=datetime.fromisoformat(times[-1])
    lt=datetime.fromisoformat(live["time"])
    gap=max(0,int((lt-last).total_seconds()/3600)-1)

    log(f"FILLED | {n}/{len(missing)}")
    log(f"GAPS INTERNAL | {gaps}")
    log(f"GAP TO LIVE | {gap}h")
    log(f"CLOSED | {len(times)}")
    log(f"CONTINUOUS20 | {gaps==0 and gap==0 and len(times)>=20}")

if __name__=="__main__":
    main()
