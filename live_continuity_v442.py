import json,time,ssl,websocket
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; H=3600
WS="wss://fstream.binance.com/ws/solusdt@trade"

def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()

def ts(c):
    v=c.get("time") or c.get("timestamp")
    if isinstance(v,(int,float)):return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

st=json.loads(STATE.read_text())
raw=st.get("candles",[])

cand={}
for c in raw:
    if not isinstance(c,dict):continue
    try:
        t=ts(c); c=dict(c); c["time"]=iso(t); cand[t]=c
    except:pass

trades={}
start=time.time()
last=0

def add(msg):
    global last

    p=float(msg["p"])
    q=float(msg["q"])
    t=int(msg["T"])//1000
    b=(t//H)*H

    if b not in trades:
        trades[b]={
            "time":iso(b),"open":p,"high":p,
            "low":p,"close":p,"volume":q,
            "trades":1,"closed":False
        }
    else:
        x=trades[b]
        x["high"]=max(x["high"],p)
        x["low"]=min(x["low"],p)
        x["close"]=p
        x["volume"]+=q
        x["trades"]+=1

    last=t

def on_open(ws):
    print("WS CONNECT | OK")

def on_message(ws,msg):
    try:add(json.loads(msg))
    except Exception as e:print("BAD",e)

def on_error(ws,e):
    print("WS ERROR",e)

def on_close(ws,*a):
    print("WS CLOSE")

print("V442 | CONTINUITY REPAIR")
print("START",datetime.now(timezone.utc).isoformat())

ws=websocket.WebSocketApp(
    WS,on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

# 10 minutes maximum
while time.time()-start<600:
    try:
        ws.run_forever(
            sslopt={"cert_reqs":ssl.CERT_REQUIRED},
            ping_interval=20,
            ping_timeout=10
        )
    except Exception as e:
        print("RECONNECT",e)
    if time.time()-start<600:
        time.sleep(2)

# Close completed hours only.
now=int(time.time())
current=(now//H)*H

added=0

for b,x in sorted(trades.items()):
    if b>=current:continue

    x["closed"]=True

    # WebSocket reconstruction is only used
    # when the candle is absent.
    if b not in cand:
        cand[b]=x
        added+=1

# Preserve existing open candles and sort.
st["candles"]=[
    cand[t] for t in sorted(cand)
]

closed=sorted(
    t for t,c in cand.items()
    if c.get("closed",True) and t<current
)

if closed:
    st["last_closed"]=iso(closed[-1])
    st["continuous20"]=(
        len(closed)>=20 and
        all(b-a==H for a,b in zip(
            closed[-20:],closed[-19:]
        ))
    )

STATE.write_text(
    json.dumps(st,indent=2)+"\n"
)

print("TRADES",sum(x["trades"] for x in trades.values()))
print("WS HOURS",len(trades))
print("ADDED",added)
print("LAST CLOSED",st.get("last_closed"))
print("CONTINUOUS20",st.get("continuous20"))
print("RESULT | V442 OK")
