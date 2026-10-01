import json
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"

def dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def main():
    print("V49.1 | CONTINUITY DIAGNOSTIC")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.get("candles",[])
    closed=[x for x in candles if x.get("closed") and x.get("time")]

    closed.sort(key=lambda x:dt(x["time"]))

    print("TOTAL",len(candles))
    print("CLOSED",len(closed))

    if not closed:
        print("NO CLOSED CANDLES")
        return

    # Doublons
    times=[x["time"] for x in closed]
    dup=sorted({t for t in times if times.count(t)>1})

    print("DUPLICATES",len(dup))
    for x in dup:
        print("DUP",x)

    first=dt(closed[0]["time"])
    last=dt(closed[-1]["time"])

    print("FIRST",closed[0]["time"])
    print("LAST",closed[-1]["time"])

    # Dernières 30 bougies
    recent=closed[-30:]

    print("\nLAST 30")
    for x in recent:
        print(x["time"],x["close"])

    # Trous entre bougies
    missing=[]

    for a,b in zip(recent,recent[1:]):
        ta,tb=dt(a["time"]),dt(b["time"])
        gap=tb-ta

        if gap!=timedelta(hours=1):
            t=ta+timedelta(hours=1)
            while t<tb:
                missing.append(t.isoformat())
                t+=timedelta(hours=1)

    print("\nMISSING",len(missing))
    for x in missing:
        print("MISSING",x)

    # Continuité des 20 dernières
    c20=len(recent)>=20 and all(
        dt(recent[i]["time"])-
        dt(recent[i-1]["time"])
        ==timedelta(hours=1)
        for i in range(1,len(recent))
    )

    last20=closed[-20:]
    c20=len(last20)==20 and all(
        dt(last20[i]["time"])-
        dt(last20[i-1]["time"])
        ==timedelta(hours=1)
        for i in range(1,20)
    )

    print("\nLAST20_CONTINUOUS",c20)

    # Diagnostic transition Sep 30 -> Oct 1
    print("\nSEP30-OCT01")

    start=datetime(2026,9,30,tzinfo=timezone.utc)
    end=datetime(2026,10,2,tzinfo=timezone.utc)

    for x in closed:
        t=dt(x["time"])
        if start<=t<end:
            print(
                x["time"],
                "CLOSE",x["close"]
            )

if __name__=="__main__":
    main()
