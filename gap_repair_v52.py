import os,json,zipfile,io,urllib.request
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
BASE="https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/1h"

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

    day="2026-10-01"
    url=f"{BASE}/SOLUSDT-1h-{day}.zip"

    print("DOWNLOAD",day)

    try:
        data=urllib.request.urlopen(url,timeout=30).read()
    except Exception as e:
        print("ARCHIVE NOT AVAILABLE")
        print(type(e).__name__)
        print("STATE NOT MODIFIED")
        return

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            raw=z.read(z.namelist()[0]).decode()
    except Exception as e:
        print("ARCHIVE ERROR",type(e).__name__)
        print("STATE NOT MODIFIED")
        raise SystemExit(1)

    found={}

    for line in raw.splitlines():
        p=line.split(",")

        if len(p)<9 or p[0].lower()=="open_time":
            continue

        try:
            t=datetime.fromtimestamp(
                int(p[0])/1000,timezone.utc
            ).isoformat()
        except Exception:
            continue

        if t not in TARGETS:
            continue

        found[t]={
            "time":t,
            "open":float(p[1]),
            "high":float(p[2]),
            "low":float(p[3]),
            "close":float(p[4]),
            "volume":float(p[5]),
            "trades":int(p[8]),
            "closed":True
        }

    print("FOUND",len(found),"/",len(TARGETS))

    missing=[x for x in TARGETS if x not in found]

    for x in missing:
        print("MISSING",x)

    if missing:
        print("REPAIR INCOMPLETE")
        print("STATE NOT MODIFIED")
        raise SystemExit(1)

    added=updated=0

    for k in TARGETS:
        x=found[k]

        if k in by:
            by[k].update(x)
            updated+=1
        else:
            candles.append(x)
            by[k]=x
            added+=1

        print("REPAIRED",k,x["close"])

    candles.sort(key=lambda x:x["time"])
    new_candles=candles[-5000:]

    closed=sorted(
        [x for x in new_candles if x.get("closed")],
        key=lambda x:x["time"]
    )

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
    print("LAST",closed[-1]["time"])
    print("CONTINUOUS20",continuous20)

    if not continuous20:
        print("CONTINUITY CHECK FAILED")
        print("STATE NOT MODIFIED")
        raise SystemExit(1)

    s["candles"]=new_candles
    s["last_closed"]=closed[-1]["time"]
    s["continuous20"]=True

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)

    print("STATE UPDATED")
    print("REPAIR COMPLETE")

if __name__=="__main__":
    main()
