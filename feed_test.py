import json,sys,ssl,threading,websocket
from datetime import datetime,timezone

URL="wss://fstream.binance.com/ws/solusdt@trade";T=30
N=BAD=0;C=None

def on_open(ws):print("WS CONNECT | OK",flush=True)

def on_message(ws,msg):
    global N,BAD,C
    try:
        x=json.loads(msg);p=float(x["p"]);q=float(x["q"]);t=int(x["T"])
        if p<=0 or q<0:BAD+=1;return
        N+=1
        h=datetime.fromtimestamp(t/1000,tz=timezone.utc).replace(
            minute=0,second=0,microsecond=0)
        key=h.isoformat()
        if C is None or C["time"]!=key:
            if C:show(C)
            C={"time":key,"open":p,"high":p,"low":p,
               "close":p,"volume":q,"trades":1}
        else:
            C["high"]=max(C["high"],p)
            C["low"]=min(C["low"],p)
            C["close"]=p
            C["volume"]+=q
            C["trades"]+=1
    except:pass

def show(c):
    print(f"CANDLE | {c['time']} | O={c['open']:.4f} "
          f"H={c['high']:.4f} L={c['low']:.4f} "
          f"C={c['close']:.4f} V={c['volume']:.3f} N={c['trades']}",
          flush=True)

def on_error(ws,e):print(f"WS ERROR | {type(e).__name__} | {e}",flush=True)

def run():
    ws=websocket.WebSocketApp(URL,on_open=on_open,on_message=on_message,
                              on_error=on_error)
    try:ws.run_forever(sslopt={"cert_reqs":ssl.CERT_REQUIRED},
                       ping_interval=10,ping_timeout=5)
    except Exception as e:print(f"WS FATAL | {e}",flush=True)

th=threading.Thread(target=run,daemon=True)
th.start();th.join(T)

print(f"COUNT | {N}",flush=True)
print(f"BAD | {BAD}",flush=True)

if C:
    show(C)
    ok=C["low"]>0 and C["high"]>=C["open"] and C["high"]>=C["close"] \
       and C["low"]<=C["open"] and C["low"]<=C["close"]
    print("OHLC | OK" if ok else "OHLC | ERROR",flush=True)
    print("RESULT | CANDLE BUILDER OK" if ok else
          "RESULT | CANDLE BUILDER ERROR",flush=True)
    sys.exit(0 if ok else 2)

print("RESULT | NO CANDLE DATA",flush=True);sys.exit(2)
