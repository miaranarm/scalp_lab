import os,json,urllib.request,urllib.parse
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
API="https://fapi.binance.com/fapi/v1/klines"

TARGETS=[
"2026-10-01T00:00:00+00:00",
"2026-10-01T06:00:00+00:00",
"2026-10-01T12:00:00+00:00",
"2026-10-01T13:00:00+00:00"
]

def main():
    print("V52 | SOLUSDT GAP REPAIR")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={x["time"]:x for x in candles if x.get("time")}

    start=int(datetime.fromisoformat(TARGETS[0]).timestamp()*1000)
    end=int((
        datetime.fromisoformat(TARGETS[-1])+
        timedelta(hours=1)
    ).timestamp()*1000)

    q=urllib.parse.urlencode({
        "symbol":"SOLUSDT",
        "interval":"1h",
        "startTime":start,
        "endTime":end,
        "limit":10
    })

    url=f"{API}?{q}"
    print("REQUEST",url)

    req=urllib.request.Request(
        url,headers={"User-Agent":"Mozilla/5.0"}
    )

    data=json.loads(
        urllib.request.urlopen(req,timeout=30).read()
    )

    print("KLINES",len(data))

    added=updated=0

    for p in data:
        k=datetime.fromtimestamp(
            int(p[0])/1000,timezone.utc
        ).isoformat()

        if k not in TARGETS:
            continue

        x={
            "time":k,
            "open":float(p[1]),
            "high":float(p[2]),
            "low":float(p[3]),
            "close":float(p[4]),
            "volume":float(p[5]),
            "trades":int(p[8]),
            "closed":True
        }

        if k in by:
            by[k].update(x)
            updated+=1
        else:
            candles.append(x)
            by[k]=x
            added+=1

        print("REPAIRED",k,x["close"])

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=sorted(
        [x for x in candles if x.get("closed")],
        key=lambda x:x["time"]
    )

    times={x["time"] for x in closed}
    missing=[x for x in TARGETS if x not in times]

    last20=closed[-20:]
    continuous20=(
        len(last20)==20 and all(
            datetime.fromisoformat(last20[i]["time"])-
            datetime.fromisoformat(last20[i-1]["time"])
            ==timedelta(hours=1)
            for i in range(1,20)
        )
    )

    print("ADDED",added)
    print("UPDATED",updated)
    print("CLOSED",len(closed))
    print("MISSING",len(missing))

    for x in missing:
        print("MISSING",x)

    print("LAST",closed[-1]["time"])
    print("CONTINUOUS20",continuous20)

    if missing:
        print("REPAIR INCOMPLETE")
        return

    s["last_closed"]=closed[-1]["time"]
    s["continuous20"]=continuous20

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)
    print("STATE UPDATED")
    print("REPAIR COMPLETE")

if __name__=="__main__":
    main()
