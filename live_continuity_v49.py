import json,time,os,select,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URLS=[
 "wss://fstream.binance.com/market/ws/solusdt@kline_1h",
 "wss://fstream.binance.com/market/stream?streams=solusdt@kline_1h"
]
MAX=65*60
SILENCE=15

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def save(s):
    tmp=STATE+".tmp"
    with open(tmp,"w") as f: json.dump(s,f,indent=2)
    os.replace(tmp,STATE)

def main():
    print("V49 | SOLUSDT 1H")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x}

    end=time.time()+MAX
    target=None
    events=added=updated=0
    closed=False
    last_report=time.time()

    while time.time()<end and not closed:
        ws=None

        for url in URLS:
            if closed or time.time()>=end:
                break

            try:
                ws=websocket.create_connection(
                    url,timeout=5,
                    origin="https://www.binance.com"
                )
                print("CONNECTED",url)

                last=time.time()

                while time.time()<end and not closed:
                    sock=ws.sock
                    if not sock:
                        break

                    r,_,_=select.select(
                        [sock],[],[],
                        min(3,end-time.time())
                    )

                    if not r:
                        if time.time()-last>=SILENCE:
                            print("SILENCE -> RECONNECT")
                            break
                        continue

                    try:
                        raw=ws.recv()
                    except Exception:
                        break

                    if not raw:
                        break

                    last=time.time()

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

                        events+=1

                        if target is None:
                            target=t/1000+3600+15
                            print(
                                "TARGET CLOSE",
                                datetime.fromtimestamp(
                                    target,timezone.utc
                                ).isoformat()
                            )

                        if x["closed"]:
                            if t in by:
                                by[t].update(x)
                                updated+=1
                            else:
                                candles.append(x)
                                by[t]=x
                                added+=1

                            s["live_candle"]=None
                            closed=True

                            print(
                                "CLOSED",
                                x["time"],
                                x["close"]
                            )
                            break

                        s["live_candle"]=x

                        if time.time()-last_report>=60:
                            print(
                                "LIVE",x["time"],
                                "CLOSE",x["close"],
                                "EVENTS",events
                            )
                            last_report=time.time()

                    except Exception:
                        continue

            except Exception as e:
                print("CONNECT_FAIL",type(e).__name__)

            finally:
                try:
                    if ws: ws.close()
                except Exception:
                    pass

            if not closed:
                time.sleep(1)

    candles.sort(key=lambda x:x["time"])
    s["candles"]=candles[-5000:]

    c=[x for x in candles if x.get("closed")]
    c.sort(key=lambda x:x["time"])

    if c:
        s["last_closed"]=c[-1]["time"]
        s["continuous20"]=(
            len(c)>=20 and all(
                datetime.fromisoformat(c[-i]["time"])-
                datetime.fromisoformat(c[-i-1]["time"])
                ==timedelta(hours=1)
                for i in range(1,20)
            )
        )
    else:
        s["continuous20"]=False

    print(
        "EVENTS",events,
        "ADDED",added,
        "UPDATED",updated,
        "CLOSED",closed
    )
    print(
        "LAST",s.get("last_closed"),
        "LIVE",(s.get("live_candle") or {}).get("time")
    )
    print("CONTINUOUS20",s.get("continuous20"))

    save(s)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
