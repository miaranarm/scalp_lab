import json,time,os,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URL="wss://fstream.binance.com/market/ws/solusdt@kline_1h"

MAX=12*60
RETRY=8
SILENCE=20

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def main():
    print("V472 | SOLUSDT 1H")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={
        int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x
    }

    start=time.time()
    events=added=updated=0
    closed_seen=False

    while time.time()-start<MAX and not closed_seen:
        ws=None

        try:
            ws=websocket.create_connection(
                URL,timeout=10,origin="https://www.binance.com"
            )
            print("CONNECTED")

            last_msg=time.time()

            while time.time()-start<MAX and time.time()-last_msg<SILENCE:
                try:
                    ws.settimeout(5)
                    raw=ws.recv()
                except Exception:
                    continue

                if not raw:
                    continue

                last_msg=time.time()

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

                    if x["closed"]:
                        if t in by:
                            by[t].update(x)
                            updated+=1
                        else:
                            candles.append(x)
                            by[t]=x
                            added+=1

                        s["live_candle"]=None
                        closed_seen=True
                        print("CLOSED",x["time"],x["close"])
                        break

                    s["live_candle"]=x

                except Exception:
                    continue

            if not closed_seen:
                print("SILENCE -> RECONNECT")

        except Exception as e:
            print("FAIL -> RECONNECT")

        finally:
            try:
                if ws:
                    ws.close()
            except Exception:
                pass

        if not closed_seen:
            time.sleep(RETRY)

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    closed=[x for x in candles if x.get("closed")]
    closed.sort(key=lambda x:x["time"])

    if closed:
        s["last_closed"]=closed[-1]["time"]
        s["continuous20"]=(
            len(closed)>=20 and all(
                datetime.fromisoformat(closed[-i]["time"])-
                datetime.fromisoformat(closed[-i-1]["time"])
                ==timedelta(hours=1)
                for i in range(1,20)
            )
        )
    else:
        s["continuous20"]=False

    print("EVENTS",events,"ADDED",added,"UPDATED",updated)
    print("CLOSED",closed_seen)
    print("LAST",s.get("last_closed"))
    print("LIVE",(s.get("live_candle") or {}).get("time"))

    tmp=STATE+".tmp"
    with open(tmp,"w") as f:
        json.dump(s,f,indent=2)
    os.replace(tmp,STATE)

    print("STATE UPDATED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
