import csv,json,os,io,zipfile
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen

STATE="state/live_v4386.json"
BASE="https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/1h"
N=20

def iso(ms):
    return datetime.fromtimestamp(
        ms/1000,timezone.utc
    ).isoformat()

def main():
    print("V50 | SOLUSDT 1H BACKFILL")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={x["time"]:x for x in candles if "time" in x}

    closed=sorted(
        [x for x in candles if x.get("closed")],
        key=lambda x:x["time"]
    )

    if not closed:
        print("NO CLOSED DATA")
        return

    last=datetime.fromisoformat(closed[-1]["time"])

    targets=[
        last-timedelta(hours=i)
        for i in range(N)
    ]

    missing=[
        x for x in targets
        if x.isoformat() not in by
    ]

    print("LAST",last.isoformat())
    print("MISSING",len(missing))

    if not missing:
        print("NOTHING TO BACKFILL")
    else:
        dates=sorted({x.date() for x in missing})

        for d in dates:
            name=f"SOLUSDT-1h-{d}.zip"
            url=f"{BASE}/{name}"

            print("DOWNLOAD",d)

            try:
                data=urlopen(url,timeout=30).read()

                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    files=z.namelist()
                    if not files:
                        continue

                    raw=z.read(files[0]).decode()
                    reader=csv.reader(io.StringIO(raw))

                    added=0

                    for r in reader:
                        if not r or not r[0].isdigit():
                            continue

                        t=int(r[0])
                        dt=datetime.fromtimestamp(
                            t/1000,timezone.utc
                        )

                        if dt not in targets:
                            continue

                        x={
                            "time":iso(t),
                            "open":float(r[1]),
                            "high":float(r[2]),
                            "low":float(r[3]),
                            "close":float(r[4]),
                            "volume":float(r[5]),
                            "trades":int(r[8]),
                            "closed":True
                        }

                        by[x["time"]]=x
                        added+=1

                    print("ADDED",added)

            except Exception as e:
                print(
                    "FAIL",
                    d,
                    type(e).__name__,
                    str(e)[:100]
                )

    s["candles"]=sorted(
        by.values(),
        key=lambda x:x["time"]
    )[-5000:]

    c=[x for x in s["candles"] if x.get("closed")]
    c.sort(key=lambda x:x["time"])

    if c:
        s["last_closed"]=c[-1]["time"]

        last20=c[-N:]

        s["continuous20"]=(
            len(last20)==N and
            all(
                datetime.fromisoformat(last20[i]["time"])-
                datetime.fromisoformat(last20[i-1]["time"])
                ==timedelta(hours=1)
                for i in range(1,N)
            )
        )
    else:
        s["continuous20"]=False

    print("LAST",s.get("last_closed"))
    print("CLOSED",len(c))
    print("CONTINUOUS20",s["continuous20"])
    print(
        "TIMES",
        [x["time"] for x in c[-N:]]
    )

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
