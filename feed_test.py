import json,time,sys,ssl,threading,websocket

URL="wss://fstream.binance.com/ws/solusdt@trade"
TIMEOUT=30
N=0

print("V438.4b | BINANCE FUTURES TRADE TEST",flush=True)
print(f"URL | {URL}",flush=True)

def on_open(ws):
    print("WS CONNECT | OK",flush=True)

def on_message(ws,msg):
    global N
    N+=1
    try:
        x=json.loads(msg)
        print(
            f"TRADE | {N} | "
            f"S={x.get('s')} | "
            f"P={x.get('p')} | "
            f"Q={x.get('q')} | "
            f"T={x.get('T')}",
            flush=True
        )
    except Exception as e:
        print(f"PARSE | {type(e).__name__} | {e}",flush=True)

def on_error(ws,e):
    print(
        f"WS ERROR | {type(e).__name__} | {e}",
        flush=True
    )

def on_close(ws,a,b):
    print(
        f"WS CLOSE | code={a} | msg={b}",
        flush=True
    )

def run():
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
            ping_interval=10,
            ping_timeout=5
        )
    except Exception as e:
        print(
            f"WS FATAL | {type(e).__name__} | {e}",
            flush=True
        )

t=threading.Thread(target=run,daemon=True)
t.start()
t.join(TIMEOUT)

if t.is_alive():
    print(f"TIMEOUT | {TIMEOUT}s",flush=True)
else:
    print("WS PROCESS | CLOSED",flush=True)

print(f"RESULT | messages={N}",flush=True)

if N:
    print("RESULT | FUTURES TRADE DATA OK",flush=True)
    sys.exit(0)

print("RESULT | NO TRADE DATA",flush=True)
sys.exit(2)
