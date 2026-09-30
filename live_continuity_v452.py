import json
from pathlib import Path
from datetime import datetime, timezone
import requests

STATE = Path("state/live_v4386.json")
S = "SOLUSDT"
IV = "1h"

URLS = [
    "https://fapi.binance.com/fapi/v1/klines",
    "https://api.binance.com/fapi/v1/klines",
    "https://api1.binance.com/fapi/v1/klines",
    "https://api2.binance.com/fapi/v1/klines",
    "https://api3.binance.com/fapi/v1/klines",
    "https://api4.binance.com/fapi/v1/klines",
    "https://api-gcp.binance.com/fapi/v1/klines",
]

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

def load():
    return json.loads(STATE.read_text())

def save(x):
    STATE.write_text(json.dumps(x, indent=2, ensure_ascii=False))

def main():
    print("V453 | FUTURES REST FAILOVER")

    st = load()
    by = {}

    for c in st.get("candles", []):
        try:
            t = datetime.fromisoformat(
                c["time"].replace("Z", "+00:00")
            ).timestamp()
            by[int(t)] = c
        except:
            pass

    rows = None
    source = None

    for url in URLS:
        try:
            r = requests.get(
                url,
                params={"symbol": S, "interval": IV, "limit": 6},
                timeout=8
            )
            print("TEST", url, r.status_code)

            if r.ok:
                rows = r.json()
                source = url
                print("SOURCE", url)
                break

        except Exception as e:
            print("FAIL", url, type(e).__name__)

    if rows is None:
        print("RESULT | NO FUTURES SOURCE")
        return

    now = datetime.now(timezone.utc).timestamp()
    added = 0
    live = None

    for x in rows:
        t = int(x[0]) // 1000
        close = int(x[6]) / 1000

        c = {
            "time": iso(int(x[0])),
            "open": float(x[1]),
            "high": float(x[2]),
            "low": float(x[3]),
            "close": float(x[4]),
            "volume": float(x[5]),
            "trades": int(x[8]),
            "closed": close < now
        }

        if c["closed"]:
            if t not in by:
                added += 1
            by[t] = c
        else:
            live = c

    candles = sorted(by.values(), key=lambda x: x["time"])
    st["candles"] = candles
    st["live_candle"] = live

    if candles:
        st["last_closed"] = candles[-1]["time"]

    st["continuous20"] = (
        len(candles) >= 20 and
        all(
            int(datetime.fromisoformat(
                candles[i]["time"].replace("Z", "+00:00")
            ).timestamp()) -
            int(datetime.fromisoformat(
                candles[i-1]["time"].replace("Z", "+00:00")
            ).timestamp()) == 3600
            for i in range(len(candles)-19, len(candles))
        )
    )

    save(st)

    print("ADDED", added)
    print("LAST CLOSED", st.get("last_closed"))
    print("CONTINUOUS20", st.get("continuous20"))

    if live:
        print(
            "LIVE", live["time"],
            "TRADES", live["trades"],
            "CLOSE", live["close"]
        )

    print("RESULT | STATE UPDATED")

if __name__ == "__main__":
    main()
