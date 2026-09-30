import json,time,ssl,websocket
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
WS="wss://fstream.binance.com/ws/solusdt@kline_1h"
RUN=570

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

st=json.loads(STATE.read_text())
cand={}

for c in st.get("candles",[]):
    try:
        t=c.get("time") or c.get("timestamp")
        if isinstance(t,(int,float)):
            t=int(t)//1000
        else:
            t=int(datetime.fromisoformat(
                str(t).replace("Z","+00:00")
            ).timestamp())
        x=dict(c)
        x["time"]=iso(t*1000)
        cand[t]=x
    except:
        pass

live=st.get("live_candle")
if live:
    try:
        t=live.get("time") or live.get("timestamp")
        if isinstance(t,(int,float)):
            t=int(t)//1000
        else:
            t=int(datetime.fromisoformat(
                str(t).replace("Z","+00:00")
            ).timestamp())
        live["time"]=iso(t*1000)
    except:
        live=None

added=0
events=0
closed_seen=0
current_live=None

print("V45 | KLINE CONTINUITY")
print("START",datetime.now(timezone.utc).isoformat())

try:
    ws=websocket.create_connection(
        WS,timeout=10,
        sslopt={"cert_reqs":ssl.CERT_REQUIRED}
    )
    print("WS CONNECT | OK")

    start=time.time()

    while time.time()-start<RUN:
        try:
            m=json.loads(ws.recv())
            k=m.get("k",{})
            if not k:
                continue

            events+=1
            t=int(k["t"])//1000

            x={
                "time":iso(int(k["t"])),
                "open":float(k["o"]),
                "high":float(k["h"]),
                "low":float(k["l"]),
                "close":float(k["c"]),
                "volume":float(k["v"]),
                "trades":int(k["n"]),
                "closed":bool(k["x"])
            }

            current_live=x

            if x["closed"]:
                if t not in cand:
                    cand[t]=x
                    added+=1
                else:
                    cand[t]=x
                closed_seen+=1
                live=None
            else:
                live=x

        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            print("WS ERROR",e)
            break

    ws.close()

except Exception as e:
    print("CONNECT ERROR",e)

# Si Binance a confirmé une clôture, elle devient définitive.
if closed_seen:
    live=None

ordered=sorted(cand)

st["candles"]=[cand[t] for t in ordered]

closed=[t for t in ordered if cand[t].get("closed",True)]

if closed:
    st["last_closed"]=iso(closed[-1]*1000)
    st["continuous20"]=(
        len(closed)>=20 and
        all(b-a==3600 for a,b in zip(closed[-20:],closed[-19:]))
    )

if live:
    st["live_candle"]=live
elif "live_candle" in st:
    del st["live_candle"]

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("EVENTS",events)
print("ADDED",added)
print("LAST CLOSED",st.get("last_closed"))
print("CONTINUOUS20",st.get("continuous20"))

if live:
    print(
        "LIVE",live["time"],
        "TRADES",live["trades"],
        "CLOSE",live["close"]
    )

print("RESULT | STATE UPDATED")
