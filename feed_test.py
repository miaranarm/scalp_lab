import json,sys,ssl,threading,websocket

URL="wss://fstream.binance.com/ws/solusdt@trade"
T=10;N=0;first=last=None

def on_open(ws): print("WS CONNECT | OK",flush=True)
def on_message(ws,msg):
    global N,first,last
    try:
        x=json.loads(msg);N+=1;p=x.get("p");t=x.get("T")
        if first is None:first=(p,t)
        last=(p,t)
    except:pass
def on_error(ws,e): print(f"WS ERROR | {type(e).__name__} | {e}",flush=True)
def on_close(ws,a,b): print(f"WS CLOSE | {a}",flush=True)

def run():
    ws=websocket.WebSocketApp(URL,on_open=on_open,on_message=on_message,
                              on_error=on_error,on_close=on_close)
    try: ws.run_forever(sslopt={"cert_reqs":ssl.CERT_REQUIRED},
                        ping_interval=10,ping_timeout=5)
    except Exception as e: print(f"WS FATAL | {e}",flush=True)

th=threading.Thread(target=run,daemon=True)
th.start();th.join(T)

if th.is_alive(): print(f"TIMEOUT | {T}s",flush=True)

print(f"COUNT | {N}",flush=True)
if first: print(f"FIRST | P={first[0]} | T={first[1]}",flush=True)
if last: print(f"LAST | P={last[0]} | T={last[1]}",flush=True)

if N:
    print("RESULT | FUTURES TRADE DATA OK",flush=True);sys.exit(0)
print("RESULT | NO TRADE DATA",flush=True);sys.exit(2)
