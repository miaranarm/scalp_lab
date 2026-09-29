import json,time,websocket

URL="wss://fstream.binance.com/market/ws/solusdt@kline_1h"

print("V438 | FUTURES KLINE WS PROBE")
print("URL",URL)

ws=None
n=0

try:
    ws=websocket.create_connection(URL,timeout=10)
    print("CONNECT OK")

    end=time.time()+60

    while time.time()<end:
        try:
            x=json.loads(ws.recv())
            n+=1

            if x.get("e")=="kline":
                k=x["k"]
                print(
                    "KLINE",
                    k["t"],
                    "O",k["o"],
                    "H",k["h"],
                    "L",k["l"],
                    "C",k["c"],
                    "V",k["v"],
                    "X",k["x"]
                )
        except Exception as e:
            print("READ",type(e).__name__,e)
            break

    print("MESSAGES",n)
    print("RESULT","OK" if n else "NO DATA")

except Exception as e:
    print("CONNECT ERROR",type(e).__name__,e)

finally:
    if ws:
        ws.close()

print("DONE")
