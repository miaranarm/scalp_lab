from __future__ import annotations
import json,ssl,sys,time,threading,websocket,requests,io
from pathlib import Path
from datetime import datetime,timezone

S="SOLUSDT"; URL=f"wss://fstream.binance.com/ws/{S.lower()}@trade"
STATE=Path("state/live_v4386.json"); OUT=Path("results/live_candles_v4386.csv")
RUN=350*60
UA={"User-Agent":"Mozilla/5.0"}

STATE.parent.mkdir(exist_ok=True);OUT.parent.mkdir(exist_ok=True)
lock=threading.Lock();N=BAD=0;C=None;B=[];STOP=False

def log(x):print(x,flush=True)

def load():
    if STATE.exists():
        try:return json.loads(STATE.read_text())
        except:pass
    return {"symbol":S,"candles":[],"last_closed":None,"warmup":True,
            "created":str(datetime.now(timezone.utc))}

def save(s):
    STATE.write_text(json.dumps(s,indent=2))

def vision():
    end=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    start=end
    y=start.year;m=start.month
    fn=f"{S}-1h-{y}-{m:02d}.zip"
    u=f"https://data.binance.vision/data/futures/um/monthly/klines/{S}/1h/{fn}"
    try:
        r=requests.get(u,headers=UA,timeout=20)
        if r.status_code!=200:return []
        z=__import__("pandas").read_csv(io.BytesIO(r.content),compression="zip",
                                         header=None)
        return [{"time":datetime.fromtimestamp(int(x[0])/1000,tz=timezone.utc).isoformat(),
                 "open":float(x[1]),"high":float(x[2]),"low":float(x[3]),
                 "close":float(x[4]),"volume":float(x[5]),"trades":int(x[8])}
                for _,x in z.iterrows() if len(x)>=9]
    except:return []

def finish(c):
    global B
    if c["high"]<c["low"] or c["low"]<=0:return
    B.append(c.copy())
    log(f"CANDLE | {c['time']} | O={c['open']:.4f} H={c['high']:.4f} "
        f"L={c['low']:.4f} C={c['close']:.4f} V={c['volume']:.3f} "
        f"N={c['trades']}")

def msg(ws,msg):
    global N,BAD,C
    try:
        x=json.loads(msg);p=float(x["p"]);q=float(x["q"]);t=int(x["T"])
        if p<=0 or q<0:BAD+=1;return
        N+=1
        h=datetime.fromtimestamp(t/1000,tz=timezone.utc).replace(
            minute=0,second=0,microsecond=0)
        k=h.isoformat()
        with lock:
            if C is None or C["time"]!=k:
                if C:finish(C)
                C={"time":k,"open":p,"high":p,"low":p,"close":p,
                   "volume":q,"trades":1}
            else:
                C["high"]=max(C["high"],p);C["low"]=min(C["low"],p)
                C["close"]=p;C["volume"]+=q;C["trades"]+=1
    except:BAD+=1

def opened(ws):log("WS CONNECT | OK")
def error(ws,e):log(f"WS ERROR | {type(e).__name__} | {e}")
def closed(ws,a,b):log("WS CLOSED")

def runws():
    global STOP
    w=websocket.WebSocketApp(URL,on_open=opened,on_message=msg,
                             on_error=error,on_close=closed)
    try:
        w.run_forever(sslopt={"cert_reqs":ssl.CERT_REQUIRED},
                      ping_interval=20,ping_timeout=10)
    except Exception as e:log(f"WS FATAL | {e}")
    STOP=True

def csvsave(rows):
    import csv
    with OUT.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["time","open","high","low",
                                       "close","volume","trades"])
        w.writeheader();w.writerows(rows)

def main():
    global C,B
    log("")
    log("V438.6 | LIVE CONTINUITY")
    log(f"{S} | TRADE WS | RUN={RUN//60}min")

    s=load()
    old={x["time"]:x for x in s.get("candles",[])}
    v=vision()
    if v:
        log(f"VISION | {len(v)} candles")
        for x in v:old[x["time"]]=x
    else:log("VISION | unavailable")

    th=threading.Thread(target=runws,daemon=True);th.start()
    t0=time.time()

    while time.time()-t0<RUN and not STOP:
        time.sleep(5)
        if C and int(time.time()-t0)%60<5:
            log(f"LIVE | {C['time']} | N={C['trades']}")

    with lock:
        if C:
            now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
            ct=datetime.fromisoformat(C["time"])
            if ct<now:
                finish(C);C=None

    for x in B:old[x["time"]]=x
    rows=sorted(old.values(),key=lambda x:x["time"])

    closed=[]
    now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    for x in rows:
        if datetime.fromisoformat(x["time"])<now:
            closed.append(x)

    s["candles"]=rows
    s["last_closed"]=closed[-1]["time"] if closed else None
    s["warmup"]=len(closed)<20
    s["updated"]=datetime.now(timezone.utc).isoformat()
    s["live_trades"]=N
    s["bad_messages"]=BAD
    save(s);csvsave(rows)

    log(f"TRADES | {N}")
    log(f"BAD | {BAD}")
    log(f"CANDLES TOTAL | {len(rows)}")
    log(f"CANDLES CLOSED | {len(closed)}")
    log(f"LAST CLOSED | {s['last_closed']}")
    log(f"WARMUP | {'YES' if s['warmup'] else 'NO'}")
    log("RESULT | CONTINUITY UPDATE OK")

if __name__=="__main__":
    main()
```

### 2. Workflow GitHub Actions

Remplace le workflow de test `V4385.yml` par celui-ci, par exemple sous :

`.github/workflows/V4386.yml`

```yaml
name: SCALP LAB V4.3.8.6 CONTINUITY

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  live:
    runs-on: ubuntu-latest
    timeout-minutes: 360

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install -q websocket-client requests pandas

      - run: python -u live_continuity_v4386.py

      - name: Save continuity
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add state results
          git diff --cached --quiet || git commit -m "V438.6 continuity update"
          git push
```

### Ce que fait maintenant V4.3.8.6

À chaque lancement :

```text
Vision
  ↓
historique disponible
  ↓
WebSocket @trade
  ↓
reconstruction des bougies 1h
  ↓
fusion + déduplication
  ↓
state/live_v4386.json
  ↓
live_candles_v4386.csv
```

Et surtout :

```text
< 20 bougies 1h continues
        ↓
     WARMUP YES
        ↓
    aucun trading
```

Puis :

```text
≥ 20 bougies continues
        ↓
     WARMUP NO
        ↓
V4.3.8.7 pourra calculer
le Donchian20 réellement continu
```

**Ne lance pas encore le paper trader.** Lance d'abord `V4386` et laisse-le tourner jusqu'au bout. Le résultat qui m'intéresse ensuite est surtout :

```text
CANDLES TOTAL
CANDLES CLOSED
LAST CLOSED
WARMUP
TRADES
BAD

À partir de ce résultat, on vérifiera que la continuité est réellement reconstituée avant de brancher le Donchian20.
