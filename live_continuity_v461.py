import json,time,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URL="wss://fstream.binance.com/market/ws/solusdt@kline_1h"
LISTEN=75

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def main():
    print("V461 | SOLUSDT 1H LIVE")

    with open(STATE) as f:
        s=json.load(f)

    try:
        ws=websocket.create_connection(
            URL,timeout=10,origin="https://www.binance.com"
        )
        print("CONNECTED")
    except Exception as e:
        print("CONNECT FAIL",e)
        return 1

    bars={}
    end=time.time()+LISTEN

    try:
        while time.time()<end:
            ws.settimeout(max(1,min(10,end-time.time())))
            try:
                raw=ws.recv()
            except Exception:
                continue

            if not raw:
                continue

            try:
                j=json.loads(raw)
                k=j.get("data",j).get("k",{})
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

                bars[t]=x

                print(
                    "BAR",x["time"],
                    "CLOSE",x["close"],
                    "TRADES",x["trades"],
                    "CLOSED",x["closed"]
                )

            except Exception as e:
                print("MSG ERR",e)

    finally:
        ws.close()

    if not bars:
        print("NO DATA")
        return 1

    candles=s.setdefault("candles",[])
    by={
        int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x
    }

    added=updated=0

    for t,x in bars.items():
        if x["closed"]:
            if t in by:
                by[t].update(x)
                updated+=1
            else:
                candles.append(x)
                added+=1
            s["live_candle"]=None
        else:
            s["live_candle"]=x

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=[x for x in s["candles"] if x.get("closed")]
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

    print("EVENTS",len(bars))
    print("ADDED",added)
    print("UPDATED",updated)
    print("LAST CLOSED",s.get("last_closed"))
    print("LIVE",(s.get("live_candle") or {}).get("time"))
    print("CONTINUOUS20",s.get("continuous20"))

    tmp=STATE+".tmp"
    with open(tmp,"w") as f:
        json.dump(s,f,indent=2)
    import os
    os.replace(tmp,STATE)

    print("STATE UPDATED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
