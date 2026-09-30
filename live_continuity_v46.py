import json,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URL="wss://fstream.binance.com/market/ws/solusdt@kline_1h"

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def main():
    print("V46 | BINANCE FUTURES MARKET WS")

    with open(STATE) as f:
        s=json.load(f)

    try:
        ws=websocket.create_connection(
            URL,
            timeout=12,
            origin="https://www.binance.com"
        )
        print("WS CONNECTED")
    except Exception as e:
        print("WS FAIL",e)
        return 1

    bars={}
    last=None

    try:
        for _ in range(6):
            ws.settimeout(5)
            raw=ws.recv()
            if not raw: continue

            j=json.loads(raw)
            k=j.get("data",j).get("k",{})
            if not k: continue

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
            last=x
            print(
                "BAR",x["time"],
                "CLOSE",x["close"],
                "TRADES",x["trades"],
                "CLOSED",x["closed"]
            )

    except Exception as e:
        print("WS END",type(e).__name__,e)

    ws.close()

    if not bars:
        print("NO DATA")
        return 1

    candles=s.setdefault("candles",[])
    by={int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x}

    added=updated=0

    for t,x in bars.items():
        if x["closed"]:
            if t not in by:
                candles.append(x)
                added+=1
            else:
                by[t].update(x)
                updated+=1
        else:
            s["live_candle"]=x

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=[x for x in s["candles"] if x.get("closed")]
    closed.sort(key=lambda x:x["time"])

    if closed:
        s["last_closed"]=closed[-1]["time"]

        ok=True
        if len(closed)>=20:
            for i in range(1,20):
                a=datetime.fromisoformat(closed[-i]["time"])
                b=datetime.fromisoformat(closed[-i-1]["time"])
                if a-b!=timedelta(hours=1):
                    ok=False
                    break
            s["continuous20"]=ok

    print("EVENTS",len(bars))
    print("ADDED",added)
    print("UPDATED",updated)
    print("LAST CLOSED",s.get("last_closed"))
    print("LIVE",s.get("live_candle",{}).get("time"))
    print("CONTINUOUS20",s.get("continuous20"))

    with open(STATE,"w") as f:
        json.dump(s,f,indent=2)

    print("STATE UPDATED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
