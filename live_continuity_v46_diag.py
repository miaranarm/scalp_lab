import requests,time,json,websocket

S="SOLUSDT"

REST=[
 "https://fapi.binance.com/fapi/v1/klines",
 "https://api.binance.com/fapi/v1/klines",
 "https://api-gcp.binance.com/fapi/v1/klines",
]

WS=[
 f"wss://fstream.binance.com/public/ws/{S.lower()}@kline_1h",
 f"wss://fstream.binance.com/market/ws/{S.lower()}@kline_1h",
 f"wss://fstream.binance.com/public/stream?streams={S.lower()}@kline_1h",
 f"wss://fstream.binance.com/market/stream?streams={S.lower()}@kline_1h",
]

print("V46 DIAG | BINANCE FUTURES")
print("SYMBOL",S)

print("\n--- REST ---")

for u in REST:
    try:
        r=requests.get(
            u,
            params={"symbol":S,"interval":"1h","limit":5},
            timeout=8
        )
        print("REST",r.status_code,u)
        if r.status_code==200:
            x=r.json()
            print("OK BARS",len(x))
            if x:
                print("LAST",x[-1][0],x[-1][4])
    except Exception as e:
        print("REST FAIL",type(e).__name__,str(e)[:120])

print("\n--- WEBSOCKET ---")

for u in WS:
    print("WS TEST",u)
    try:
        ws=websocket.create_connection(
            u,
            timeout=5,
            origin="https://www.binance.com"
        )
        print("CONNECTED")

        ws.settimeout(4)
        msg=ws.recv()

        if msg:
            print("MESSAGE",len(msg),msg[:300])
        else:
            print("EMPTY")

        ws.close()

    except Exception as e:
        print("WS FAIL",type(e).__name__,str(e)[:180])

print("\nDIAG COMPLETE")
