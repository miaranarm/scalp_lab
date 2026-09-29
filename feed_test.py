import json,time,sys,ssl,websocket

S="solusdt"
URL=f"wss://fstream.binance.com/ws/{S}@kline_1h"
T=time.time();N=0

print("V438.4 | BINANCE FUTURES WS TEST",flush=True)
print(f"URL | {URL}",flush=True)

def on_open(ws):
    print("WS CONNECT | OK",flush=True)

def on_message(ws,msg):
    global N
    N+=1
    try:
        x=json.loads(msg)
        k=x.get("k",{})
        print(
            f"WS MESSAGE | {N} | "
            f"symbol={k.get('s')} | "
            f"interval={k.get('i')} | "
            f"closed={k.get('x')} | "
            f"close={k.get('c')} | "
            f"time={k.get('T')}",
            flush=True
        )
    except Exception as e:
        print(f"WS PARSE | {e}",flush=True)

def on_error(ws,e):
    print(f"WS ERROR | {type(e).__name__} | {e}",flush=True)

def on_close(ws,a,b):
    print(f"WS CLOSE | code={a} | msg={b}",flush=True)

ws=websocket.WebSocketApp(
    URL,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

try:
    ws.run_forever(
        sslopt={"cert_reqs":ssl.CERT_REQUIRED},
        ping_interval=20,
        ping_timeout=10
    )
except Exception as e:
    print(f"WS FATAL | {type(e).__name__} | {e}",flush=True)

print(f"RESULT | messages={N} | elapsed={time.time()-T:.1f}s",flush=True)

if N:
    print("RESULT | WEBSOCKET ACCESSIBLE",flush=True)
    sys.exit(0)

print("RESULT | NO MARKET DATA RECEIVED",flush=True)
sys.exit(2)
