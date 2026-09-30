import json,time,ssl,websocket
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
WS="wss://fstream.binance.com/ws/solusdt@trade"
H=3600; RUN=570

def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()

def ts(c):
    v=c.get("time") or c.get("timestamp")
    if isinstance(v,(int,float)): return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

st=json.loads(STATE.read_text())
cand={}

for c in st.get("candles",[]):
    try:
        t=ts(c); x=dict(c); x["time"]=iso(t); cand[t]=x
    except: pass

bars={}; n=0
print("V443 | CONTINUITY")
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
            p=float(m["p"]); q=float(m["q"])
            t=int(m["T"])//1000
            b=(t//H)*H

            x=bars.setdefault(b,{
                "time":iso(b),"open":p,"high":p,
                "low":p,"close":p,"volume":0,
                "trades":0,"closed":False
            })

            x["high"]=max(x["high"],p)
            x["low"]=min(x["low"],p)
            x["close"]=p
            x["volume"]+=q
            x["trades"]+=1
            n+=1

        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            print("WS ERROR",e)
            break

    ws.close()

except Exception as e:
    print("CONNECT ERROR",e)

now=int(time.time())
current=(now//H)*H
added=0

for b,x in bars.items():
    if b<current and b not in cand:
        x["closed"]=True
        cand[b]=x
        added+=1

if added:
    ordered=sorted(cand)
    closed=[t for t in ordered if cand[t].get("closed",True)]

    st["candles"]=[cand[t] for t in ordered]
    st["last_closed"]=iso(closed[-1])

    st["continuous20"]=(
        len(closed)>=20 and
        all(b-a==H for a,b in zip(
            closed[-20:],closed[-19:]
        ))
    )

    STATE.write_text(json.dumps(st,indent=2)+"\n")

print("TRADES",n)
print("WS HOURS",len(bars))
print("ADDED",added)
print("LAST CLOSED",st.get("last_closed"))
print("CONTINUOUS20",st.get("continuous20"))

if added:
    print("RESULT | NEW CANDLE SAVED")
else:
    print("RESULT | NO NEW CLOSED CANDLE")
