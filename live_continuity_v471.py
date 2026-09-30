import json,time,os,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URL="wss://fstream.binance.com/market/ws/solusdt@kline_1h"
MAX=12*60
REPORT=30

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def main():
    print("V471 | SOLUSDT 1H")

    with open(STATE) as f:
        s=json.load(f)

    try:
        ws=websocket.create_connection(
            URL,timeout=15,origin="https://www.binance.com"
        )
        print("CONNECTED")
    except Exception as e:
        print("CONNECT FAIL",e)
        return 1

    candles=s.setdefault("candles",[])
    by={
        int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x
    }

    added=updated=events=0
    start=time.time()
    report=0
    closed_seen=False

    try:
        while time.time()-start<MAX:
            try:
                ws.settimeout(15)
                raw=ws.recv()
            except Exception:
                continue

            if not raw:
                continue

            try:
                k=json.loads(raw).get("data",{}).get("k",{})
                if not k:
                    continue

                t=int(k["t"])
                x={
                    "time":iso(t),
                    "open":float(k["o"]),
                    "high":float(k["h"]),
                    "low":float(k["l"]),
                    "close":float(k["c"]),
                    "volume":float(k["v"]),
                    "trades":int(k["n"]),
                    "closed":bool(k["x"])
                }

                events+=1

                if not x["closed"]:
                    s["live_candle"]=x

                    if time.time()-report>=REPORT:
                        print(
                            "LIVE",x["time"],
                            "|",x["close"],
                            "| TRADES",x["trades"]
                        )
                        report=time.time()

                else:
                    if t in by:
                        by[t].update(x)
                        updated+=1
                    else:
                        candles.append(x)
                        by[t]=x
                        added+=1

                    s["live_candle"]=None
                    closed_seen=True
                    print(
                        "CLOSED",x["time"],
                        "|",x["close"],
                        "| TRADES",x["trades"]
                    )
                    break

            except Exception:
                continue

    finally:
        ws.close()

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=[x for x in candles if x.get("closed")]
    closed.sort(key=lambda x:x["time"])

    if closed:
        s["last_closed"]=closed[-1]["time"]

        if len(closed)>=20:
            s["continuous20"]=all(
                datetime.fromisoformat(closed[-i]["time"])-
                datetime.fromisoformat(closed[-i-1]["time"])
                ==timedelta(hours=1)
                for i in range(1,20)
            )
        else:
            s["continuous20"]=False

    print("EVENTS",events)
    print("ADDED",added,"UPDATED",updated)
    print("CLOSED SEEN",closed_seen)
    print("LAST CLOSED",s.get("last_closed"))
    print("LIVE",(s.get("live_candle") or {}).get("time"))
    print("CONTINUOUS20",s.get("continuous20"))

    tmp=STATE+".tmp"
    with open(tmp,"w") as f:
        json.dump(s,f,indent=2)
    os.replace(tmp,STATE)

    print("STATE UPDATED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
