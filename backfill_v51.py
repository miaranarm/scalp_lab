import os,json,zipfile,io,urllib.request
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
BASE="https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/1h"
START=datetime(2026,9,29,tzinfo=timezone.utc)

def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def iso(d): return d.isoformat()

def main():
    print("V51 | SOLUSDT 1H SMART BACKFILL")

    with open(STATE) as f:s=json.load(f)

    candles=s.setdefault("candles",[])
    by={x["time"]:x for x in candles if x.get("time")}
    closed=[x for x in candles if x.get("closed")]
    last=max((dt(x["time"]) for x in closed),default=START)

    need=[]
    t=START
    while t<=last:
        if iso(t) not in by: need.append(t)
        t+=timedelta(hours=1)

    print("LAST",iso(last))
    print("MISSING",len(need))

    added=0

    for day in sorted({x.date() for x in need}):
        url=f"{BASE}/SOLUSDT-1h-{day}.zip"
        print("DOWNLOAD",day)

        try:
            data=urllib.request.urlopen(url,timeout=30).read()

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                raw=z.read(z.namelist()[0]).decode()

            for line in raw.splitlines():
                p=line.split(",")
                if len(p)<11: continue

                # Ignore Binance CSV header
                if p[0].strip().lower()=="open_time":
                    continue

                try:
                    t=datetime.fromtimestamp(
                        int(p[0])/1000,timezone.utc
                    )
                except (ValueError,TypeError):
                    continue

                k=iso(t)

                if k not in by and t<=last:
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
                    candles.append(x)
                    by[k]=x
                    added+=1

            print("OK",day)

        except Exception as e:
            print("PENDING",day,type(e).__name__,e)

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=sorted(
        [x for x in candles if x.get("closed")],
        key=lambda x:x["time"]
    )

    if closed:
        s["last_closed"]=closed[-1]["time"]
        recent=closed[-20:]
        s["continuous20"]=(len(recent)==20 and all(
            dt(recent[i]["time"])-
            dt(recent[i-1]["time"])==timedelta(hours=1)
            for i in range(1,20)
        ))
    else:
        s["continuous20"]=False

    missing=[]
    if closed:
        a=dt(closed[0]["time"])
        b=dt(closed[-1]["time"])
        seen={x["time"] for x in closed}
        t=a

        while t<=b:
            if iso(t) not in seen: missing.append(iso(t))
            t+=timedelta(hours=1)

    s["backfill_pending"]=missing

    print("ADDED",added)
    print("CLOSED",len(closed))
    print("PENDING",len(missing))
    print("LAST",s.get("last_closed"))
    print("CONTINUOUS20",s["continuous20"])

    with open(STATE+".tmp","w") as f:
        json.dump(s,f,indent=2)

    os.replace(STATE+".tmp",STATE)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
