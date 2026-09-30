import json,time,ssl,websocket
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; H=3600
WS="wss://fstream.binance.com/ws/solusdt@trade"
RUN=570

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
        t=ts(c)
        c=dict(c); c["time"]=iso(t)
        cand[t]=c
    except: pass

bars={}
start=time.time()
n=0

print("V442 | CONTINUITY REPAIR")
print("START",datetime.now(timezone.utc).isoformat())

try:
    ws=websocket.create_connection(
        WS,
        timeout=10,
        sslopt={"cert_reqs":ssl.CERT_REQUIRED}
    )
    print("WS CONNECT | OK")

    while time.time()-start<RUN:
        try:
            raw=ws.recv()
            if not raw: continue

            m=json.loads(raw)
            p=float(m["p"])
            q=float(m["q"])
            t=int(m["T"])//1000
            b=(t//H)*H

            if b not in bars:
                bars[b]={
                    "time":iso(b),
                    "open":p,"high":p,"low":p,
                    "close":p,"volume":q,
                    "trades":1,"closed":False
                }
            else:
                x=bars[b]
                x["high"]=max(x["high"],p)
                x["low"]=min(x["low"],p)
                x["close"]=p
                x["volume"]+=q
                x["trades"]+=1

            n+=1

        except websocket.WebSocketTimeoutException:
            print("PING |",round(time.time()-start))
        except Exception as e:
            print("WS ERROR |",e)
            break

    ws.close()

except Exception as e:
    print("CONNECT ERROR |",e)

now=int(time.time())
current=(now//H)*H
added=0

for b,x in bars.items():
    if b<current:
        x["closed"]=True
        if b not in cand:
            cand[b]=x
            added+=1

ordered=sorted(cand)
st["candles"]=[cand[t] for t in ordered]

closed=sorted(
    t for t in ordered
    if cand[t].get("closed",True) and t<current
)

if closed:
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
print("RESULT | V442 OK")
