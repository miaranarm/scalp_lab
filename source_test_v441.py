import requests,time
from datetime import datetime,timezone

S="SOLUSDT"; IV="1h"; LIM=2

URLS=[
 "https://fapi.binance.com/fapi/v1/klines",
 "https://api1.binance.com/fapi/v1/klines",
 "https://api2.binance.com/fapi/v1/klines",
 "https://api3.binance.com/fapi/v1/klines",
 "https://api4.binance.com/fapi/v1/klines",
 "https://data-api.binance.vision/api/v3/klines"
]

print("V441 | SOURCE TEST")
print("TIME",datetime.now(timezone.utc).isoformat())
print("SYMBOL",S,"INTERVAL",IV)

for u in URLS:
    print("\nSOURCE",u)
    try:
        t=time.time()
        r=requests.get(
            u,
            params={"symbol":S,"interval":IV,"limit":LIM},
            timeout=15
        )
        print("HTTP",r.status_code)
        print("SECONDS",round(time.time()-t,2))
        print("SIZE",len(r.content))

        if r.status_code==200:
            try:
                x=r.json()
                print("RESULT OK")
                print("ROWS",len(x))
                if x:
                    print("FIRST",datetime.fromtimestamp(
                        x[0][0]/1000,timezone.utc
                    ).isoformat())
                    print("LAST",datetime.fromtimestamp(
                        x[-1][0]/1000,timezone.utc
                    ).isoformat())
            except Exception as e:
                print("JSON ERROR",e)
        else:
            print("BODY",r.text[:300])

    except Exception as e:
        print("ERROR",type(e).__name__,str(e))

    time.sleep(1)

print("\nV441 | TEST FINISHED")
