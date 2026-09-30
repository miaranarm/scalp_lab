import os,json,requests
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
API="https://trader-pro.org/data/v1/candles/binancef/SOLUSDT"
KEY=os.environ["TP_API_KEY"]

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def main():
    print("V46 | TRADER.PRO FUTURES CONTINUITY")

    with open(STATE) as f:
        s=json.load(f)

    h={"X-TP-API-Key":KEY}
    p={"interval":"1h","limit":20}

    try:
        r=requests.get(API,headers=h,params=p,timeout=20)
        print("HTTP",r.status_code)
        r.raise_for_status()
        j=r.json()
    except Exception as e:
        print("API FAIL",type(e).__name__,e)
        return 1

    bars=j.get("bars",[])
    print("BARS",len(bars))

    if not bars:
        print("NO DATA")
        return 1

    candles=s.setdefault("candles",[])
    by={int(x["time"]):x for x in candles if "time" in x}

    added=0
    updated=0

    for b in bars:
        t=int(b["time"])
        x={
            "time":iso(t),
            "open":float(b["open"]),
            "high":float(b["high"]),
            "low":float(b["low"]),
            "close":float(b["close"]),
            "volume":float(b.get("volume",0)),
            "trades":int(b.get("trades",0)),
            "closed":True
        }

        old=by.get(t)
        if old:
            if old.get("trades",0)==0 and x["trades"]>0:
                old.update(x)
                updated+=1
        else:
            by[t]=x
            added+=1

    out=sorted(by.values(),key=lambda x:x["time"])

    # conserve une fenêtre raisonnable du state existant
    s["candles"]=out[-5000:]

    closed=[x for x in s["candles"] if x.get("closed")]
    closed.sort(key=lambda x:x["time"])

    if closed:
        s["last_closed"]=closed[-1]["time"]

        last=datetime.fromisoformat(closed[-1]["time"])
        ok=0
        for i in range(1,min(20,len(closed))):
            a=datetime.fromisoformat(closed[-1-i]["time"])
            if last-a==timedelta(hours=i):
                ok+=1
            else:
                break
        s["continuous20"]=(ok==19)

    # REST ne renvoie que les bougies clôturées
    s["live_candle"]=None

    print("FIRST",s["candles"][0]["time"])
    print("LAST CLOSED",s.get("last_closed"))
    print("ADDED",added,"UPDATED",updated)
    print("CONTINUOUS20",s.get("continuous20"))

    with open(STATE,"w") as f:
        json.dump(s,f,indent=2)

    print("STATE UPDATED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
