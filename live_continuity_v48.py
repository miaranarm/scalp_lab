import json,time,os,select,websocket
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
URLS=[
 "wss://fstream.binance.com/market/ws/solusdt@kline_1h",
 "wss://fstream.binance.com/market/stream?streams=solusdt@kline_1h"
]
RUN=14*60
SILENCE=15

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def save(s):
    tmp=STATE+".tmp"
    with open(tmp,"w") as f: json.dump(s,f,indent=2)
    os.replace(tmp,STATE)

def main():
    print("V48 | SOLUSDT 1H")

    with open(STATE) as f:
        s=json.load(f)

    candles=s.setdefault("candles",[])
    by={
        int(datetime.fromisoformat(x["time"]).timestamp()*1000):x
        for x in candles if "time" in x
    }

    end=time.time()+RUN
    events=added=updated=0
    closed=False

    while time.time()<end and not closed:
        ws=None

        for url in URLS:
            if time.time()>=end or closed:
                break

            try:
                ws=websocket.create_connection(
                    url,
                    timeout=5,
                    origin="https://www.binance.com"
                )
                print("CONNECTED",url.split("/")[3])
                last=time.time()

                while time.time()<end and not closed:
                    sock=ws.sock
                    if not sock:
                        break

                    wait=min(3,end-time.time())
                    r,_,_=select.select([sock],[],[],wait)

                    if not r:
                        if time.time()-last>=SILENCE:
                            print("SILENCE")
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
                            closed=True

                            print(
                                "CLOSED",
                                x["time"],
                                x["close"]
                            )
                            break

                        s["live_candle"]=x

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
        s["continuous20"]=(len(c)>=20 and all(
            datetime.fromisoformat(c[-i]["time"])-
            datetime.fromisoformat(c[-i-1]["time"])
            ==timedelta(hours=1)
            for i in range(1,20)
        ))
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

    save(s)
    print("STATE UPDATED")

if __name__=="__main__":
    main()
