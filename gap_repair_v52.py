import os,json,zipfile,io,urllib.request
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
DAY=datetime(2026,10,1,tzinfo=timezone.utc)
TARGETS={
    "2026-10-01T00:00:00+00:00",
    "2026-10-01T06:00:00+00:00",
    "2026-10-01T12:00:00+00:00",
    "2026-10-01T13:00:00+00:00"
}
BASE="https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/1h"

def main():
    print("V52 | SOLUSDT GAP REPAIR")
    print("TARGETS",len(TARGETS))

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={x["time"]:x for x in candles if x.get("time")}

    url=f"{BASE}/SOLUSDT-1h-{DAY.date()}.zip"
    print("DOWNLOAD",DAY.date())

    data=urllib.request.urlopen(url,timeout=30).read()

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        raw=z.read(z.namelist()[0]).decode()

    added=updated=0

    for line in raw.splitlines():
        p=line.split(",")
        if len(p)<11 or p[0].lower()=="open_time":
            continue

        try:
            t=datetime.fromtimestamp(int(p[0])/1000,timezone.utc)
        except:
            continue

        k=t.isoformat()

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

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=sorted(
        [x for x in candles if x.get("closed")],
        key=lambda x:x["time"]
    )

    last20=closed[-20:]
    continuous20=len(last20)==20 and all(
        datetime.fromisoformat(last20[i]["time"])-
        datetime.fromisoformat(last20[i-1]["time"])
        ==timedelta(hours=1)
        for i in range(1,20)
    )

    missing=[
        x for x in TARGETS
        if x not in {c["time"] for c in closed}
    ]

    s["last_closed"]=closed[-1]["time"] if closed else None
    s["continuous20"]=continuous20

    print("ADDED",added)
    print("UPDATED",updated)
    print("CLOSED",len(closed))
    print("REMAINING_MISSING",len(missing))

    for x in missing:
        print("MISSING",x)

    print("LAST",s["last_closed"])
    print("CONTINUOUS20",continuous20)

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
