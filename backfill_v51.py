import os,json,zipfile,io,urllib.request
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
BASE="https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/1h"
START=datetime(2026,9,29,tzinfo=timezone.utc)
CUTOFF=datetime(2026,9,30,23,tzinfo=timezone.utc)

def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def iso(d): return d.isoformat()

def main():
    print("V51 | SOLUSDT 1H SMART BACKFILL")
    print("CUTOFF",iso(CUTOFF))

    with open(STATE) as f:s=json.load(f)

    candles=s.setdefault("candles",[])
    by={x["time"]:x for x in candles if x.get("time")}

    expected=[]
    t=START
    while t<=CUTOFF:
        expected.append(iso(t))
        t+=timedelta(hours=1)

    print("TARGET",iso(CUTOFF))
    print("EXPECTED",len(expected))

    added=updated=0

    # Toujours vérifier les 2 archives historiques
    for day in (START.date(),CUTOFF.date()):
        url=f"{BASE}/SOLUSDT-1h-{day}.zip"
        print("DOWNLOAD",day)

        try:
            data=urllib.request.urlopen(url,timeout=30).read()

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                raw=z.read(z.namelist()[0]).decode()

            for line in raw.splitlines():
                p=line.split(",")
                if len(p)<11 or p[0].strip().lower()=="open_time":
                    continue

                try:
                    t=datetime.fromtimestamp(
                        int(p[0])/1000,timezone.utc
                    )
                except (ValueError,TypeError):
                    continue

                if not START<=t<=CUTOFF:
                    continue

                k=iso(t)
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

            print("OK",day)

        except Exception as e:
            print("ERROR",day,type(e).__name__,e)

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    hist=sorted([
        x for x in candles
        if x.get("closed")
        and START<=dt(x["time"])<=CUTOFF
    ],key=lambda x:x["time"])

    seen={x["time"] for x in hist}
    pending=[x for x in expected if x not in seen]

    recent=hist[-20:]
    continuous20=(
        len(recent)==20 and all(
            dt(recent[i]["time"])-
            dt(recent[i-1]["time"])==timedelta(hours=1)
            for i in range(1,20)
        )
    )

    s["backfill_last_closed"]=hist[-1]["time"] if hist else None
    s["backfill_pending"]=pending
    s["backfill_continuous20"]=continuous20

    print("ADDED",added)
    print("UPDATED",updated)
    print("CLOSED",len(hist),"/",len(expected))
    print("PENDING",len(pending))
    if pending: print("MISSING_TIMES",pending)
    print("BACKFILL_LAST",s["backfill_last_closed"])
    print("BACKFILL_CONTINUOUS20",continuous20)

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
