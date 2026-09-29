import json,sys,ssl,threading,time,websocket
from datetime import datetime,timezone

URL="wss://fstream.binance.com/ws/solusdt@trade"
T=30
N=0;C=None

def iso(ms):
    return datetime.fromtimestamp(ms/1000,tz=timezone.utc).isoformat()

def on_open(ws):
    print("WS CONNECT | OK",flush=True)

def on_message(ws,msg):
    global N,C
    try:
        x=json.loads(msg);p=float(x["p"]);q=float(x["q"]);t=int(x["T"])
        N+=1
        h=datetime.fromtimestamp(t/1000,tz=timezone.utc).replace(
            minute=0,second=0,microsecond=0)
        key=h.isoformat()
        if C is None or C["time"]!=key:
            if C:
                print(
                    f"CANDLE | {C['time']} | "
                    f"O={C['open']:.4f} H={C['high']:.4f} "
                    f"L={C['low']:.4f} C={C['close']:.4f} "
                    f"V={C['volume']:.3f} N={C['trades']}",
                    flush=True)
            C={"time":key,"open":p,"high":p,"low":p,
               "close":p,"volume":q,"trades":1}
        else:
            C["high"]=max(C["high"],p)
            C["low"]=min(C["low"],p)
            C["close"]=p
            C["volume"]+=q
            C["trades"]+=1
    except Exception:
        pass

def on_error(ws,e):
    print(f"WS ERROR | {type(e).__name__} | {e}",flush=True)

def run():
    ws=websocket.WebSocketApp(
        URL,on_open=on_open,on_message=on_message,
        on_error=on_error)
    try:
        ws.run_forever(
            sslopt={"cert_reqs":ssl.CERT_REQUIRED},
            ping_interval=10,ping_timeout=5)
    except Exception as e:
        print(f"WS FATAL | {e}",flush=True)

th=threading.Thread(target=run,daemon=True)
th.start();th.join(T)

print(f"COUNT | {N}",flush=True)

if C:
    print(
        f"LIVE CANDLE | {C['time']} | "
        f"O={C['open']:.4f} H={C['high']:.4f} "
        f"L={C['low']:.4f} C={C['close']:.4f} "
        f"V={C['volume']:.3f} N={C['trades']}",
        flush=True)
    print("RESULT | CANDLE BUILDER OK",flush=True)
    sys.exit(0)

print("RESULT | NO CANDLE DATA",flush=True)
sys.exit(2)
