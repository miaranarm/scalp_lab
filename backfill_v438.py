import json,requests
from pathlib import Path
from datetime import datetime,timezone,timedelta

S="SOLUSDT"
STATE=Path("state/live_v438.json")

def log(x): print(x,flush=True)

def D(x):
    return datetime.fromisoformat(x)

def load():
    s=json.loads(STATE.read_text())
    old={}

    def scan(x):
        if isinstance(x,dict):
            t=x.get("time")
            if t and all(k in x for k in("open","high","low","close")):
                old[t]=x
            for v in x.values(): scan(v)
        elif isinstance(x,list):
            for v in x: scan(v)

    scan(s)
    live=s.get("live")
    return old,live

def get(a,b):
    p={"symbol":S,"interval":"1h","startTime":a,
       "endTime":b,"limit":1000}

    for h in [
        "fapi.binance.com",
        "fapi1.binance.com",
        "fapi2.binance.com",
        "fapi3.binance.com",
        "fapi4.binance.com"
    ]:
        try:
            u=f"https://{h}/fapi/v1/klines"
            r=requests.get(u,params=p,timeout=12)
            log(f"API {r.status_code} | {h}")
            if r.status_code==200:
                return r.json()
        except Exception as e:
            log(f"ERR | {h} | {type(e).__name__}")
    return []

def main():
    log("V438.BACKFILL V2 | START")

    if not STATE.exists():
        log("STATE MISSING")
        return

    old,live=load()

    log(f"FOUND CANDLES | {len(old)}")

    if not old:
        log("NO HISTORY")
        return

    ts=sorted(old)
    last=D(ts[-1])

    if not live:
        log("NO LIVE")
        return

    lt=D(live["time"])

    log(f"LAST | {last.isoformat()}")
    log(f"LIVE | {lt.isoformat()}")

    miss=[]
    t=last+timedelta(hours=1)

    while t<lt:
        if t.isoformat() not in old:
            miss.append(t)
        t+=timedelta(hours=1)

    log(f"MISSING | {len(miss)}")

    if not miss:
        log("BACKFILL | NOTHING")
        return

    a=int(miss[0].timestamp()*1000)
    b=int((miss[-1]+timedelta(hours=1)).timestamp()*1000)-1

    rows=get(a,b)

    if not rows:
        log("BACKFILL | NO DATA")
        return

    n=0
    for r in rows:
        try:
            t=datetime.fromtimestamp(int(r[0])/1000,timezone.utc).isoformat()
            if t in {x.isoformat() for x in miss}:
                old[t]={
                    "time":t,
                    "open":float(r[1]),
                    "high":float(r[2]),
                    "low":float(r[3]),
                    "close":float(r[4]),
                    "volume":float(r[5]),
                    "trades":int(r[8]),
                    "closed":True
                }
                n+=1
        except:
            pass

    log(f"FILLED | {n}/{len(miss)}")

    if n:
        s=json.loads(STATE.read_text())

        def put(x):
            if isinstance(x,dict):
                for k,v in list(x.items()):
                    if k=="live": continue
                    if isinstance(v,dict) and v.get("time") in old:
                        continue
                    put(v)
            elif isinstance(x,list):
                x[:]=[v for v in x if not(
                    isinstance(v,dict) and v.get("time") in old
                )]

        # conserver la structure 6f et ajouter l'historique
        s["backfill"]=old
        STATE.write_text(json.dumps(s,indent=2))

    allts=sorted(old)
    gaps=0

    for a,b in zip(allts,allts[1:]):
        x=D(a);y=D(b)
        gaps+=max(0,int((y-x).total_seconds()/3600)-1)

    last=D(allts[-1])
    gap=max(0,int((lt-last).total_seconds()/3600)-1)

    log(f"TOTAL | {len(allts)}")
    log(f"GAPS INTERNAL | {gaps}")
    log(f"GAP TO LIVE | {gap}h")
    log(f"CONTINUOUS20 | {gaps==0 and gap==0 and len(allts)>=20}")

if __name__=="__main__":
    main()
