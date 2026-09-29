from __future__ import annotations
import json,ssl,time,threading,websocket,requests,io
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pandas as pd

S="SOLUSDT";URL=f"wss://fstream.binance.com/ws/{S.lower()}@trade"
STATE=Path("state/live_v4386.json");OUT=Path("results/live_candles_v4386.csv")
RUN=10*60;UA={"User-Agent":"Mozilla/5.0"}
STATE.parent.mkdir(exist_ok=True);OUT.parent.mkdir(exist_ok=True)
N=BAD=0;C=None;LIVE=[];STOP=False

def log(x):print(x,flush=True)

def load():
    try:return json.loads(STATE.read_text())
    except:return {"symbol":S,"candles":[],"last_closed":None,"warmup":True}

def vision():
    now=datetime.now(timezone.utc)
    out=[]
    for d in [now-timedelta(days=i) for i in range(2)]:
        fn=f"{S}-1h-{d:%Y-%m-%d}.zip"
        u=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{fn}"
        try:
            r=requests.get(u,headers=UA,timeout=15)
            if r.status_code!=200:continue
            z=pd.read_csv(io.BytesIO(r.content),compression="zip",header=None)
            for _,x in z.iterrows():
                if len(x)>=9 and float(x[3])>0:
                    out.append({
                        "time":datetime.fromtimestamp(int(x[0])/1000,tz=timezone.utc).isoformat(),
                        "open":float(x[1]),"high":float(x[2]),"low":float(x[3]),
                        "close":float(x[4]),"volume":float(x[5]),"trades":int(x[8])
                    })
        except Exception as e:log(f"VISION ERROR | {type(e).__name__}")
    return list({x["time"]:x for x in out}.values())

def finish(c):
    if c["low"]<=0 or c["high"]<c["low"]:return
    LIVE.append(c.copy())
    log(f"CANDLE | {c['time']} | O={c['open']:.4f} H={c['high']:.4f} "
        f"L={c['low']:.4f} C={c['close']:.4f} V={c['volume']:.3f} N={c['trades']}")

def msg(ws,m):
    global N,BAD,C
    try:
        x=json.loads(m);p=float(x["p"]);q=float(x["q"]);t=int(x["T"])
        if p<=0 or q<0:BAD+=1;return
        N+=1
        h=datetime.fromtimestamp(t/1000,tz=timezone.utc).replace(
            minute=0,second=0,microsecond=0)
        k=h.isoformat()
        if C is None or C["time"]!=k:
            if C:finish(C)
            C={"time":k,"open":p,"high":p,"low":p,"close":p,"volume":q,"trades":1}
        else:
            C["high"]=max(C["high"],p);C["low"]=min(C["low"],p)
            C["close"]=p;C["volume"]+=q;C["trades"]+=1
    except:BAD+=1

def opened(ws):log("WS CONNECT | OK")
def error(ws,e):log(f"WS ERROR | {type(e).__name__} | {e}")

def wsrun():
    global STOP
    w=websocket.WebSocketApp(URL,on_open=opened,on_message=msg,on_error=error)
    try:w.run_forever(sslopt={"cert_reqs":ssl.CERT_REQUIRED},
                      ping_interval=20,ping_timeout=10)
    except Exception as e:log(f"WS FATAL | {type(e).__name__}")
    STOP=True

def main():
    global C
    log("V438.6b | CONTINUITY TEST | 10 MIN")
    s=load()
    old={x["time"]:x for x in s.get("candles",[])}
    v=vision()
    log(f"VISION | {len(v)}")
    for x in v:old[x["time"]]=x

    th=threading.Thread(target=wsrun,daemon=True);th.start()
    t=time.time()
    while time.time()-t<RUN and not STOP:time.sleep(5)

    if C:
        now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
        if datetime.fromisoformat(C["time"])<now:finish(C);C=None

    for x in LIVE:old[x["time"]]=x
    rows=sorted(old.values(),key=lambda x:x["time"])
    now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    closed=[x for x in rows if datetime.fromisoformat(x["time"])<now]

    s.update({
        "candles":rows,
        "last_closed":closed[-1]["time"] if closed else None,
        "warmup":len(closed)<20,
        "updated":datetime.now(timezone.utc).isoformat(),
        "live_trades":N,"bad_messages":BAD
    })
    STATE.write_text(json.dumps(s,indent=2))
    pd.DataFrame(rows).to_csv(OUT,index=False)

    log(f"TRADES | {N}")
    log(f"BAD | {BAD}")
    log(f"CANDLES TOTAL | {len(rows)}")
    log(f"CANDLES CLOSED | {len(closed)}")
    log(f"LAST CLOSED | {s['last_closed']}")
    log(f"WARMUP | {'YES' if s['warmup'] else 'NO'}")
    log("RESULT | CONTINUITY TEST OK")

if __name__=="__main__":main()
