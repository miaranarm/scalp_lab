import json, time, ssl
from pathlib import Path
from datetime import datetime, timezone
import requests

STATE = Path("state/live_v4386.json")
S = "SOLUSDT"
IV = "1h"
H = 3600

REST = "https://fapi.binance.com/fapi/v1/klines"
WS = f"wss://fstream.binance.com/ws/{S.lower()}@kline_1h"

def now():
    return datetime.now(timezone.utc)

def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()

def load():
    if not STATE.exists():
        return {"candles": [], "live_candle": None}
    return json.loads(STATE.read_text())

def save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False))

def normalize(x):
    return {
        "time": iso(int(x[0]) / 1000),
        "open": float(x[1]),
        "high": float(x[2]),
        "low": float(x[3]),
        "close": float(x[4]),
        "volume": float(x[5]),
        "trades": int(x[8]),
        "closed": False
    }

def continuous(candles):
    if len(candles) < 20:
        return False
    ts = [int(datetime.fromisoformat(c["time"].replace("Z","+00:00")).timestamp()) for c in candles[-20:]]
    return all(ts[i] - ts[i-1] == H for i in range(1, len(ts)))

def rest():
    r = requests.get(
        REST,
        params={"symbol": S, "interval": IV, "limit": 6},
        timeout=15
    )
    r.raise_for_status()
    return r.json()

def ws_fallback():
    try:
        import websocket
        ws = websocket.create_connection(
            WS,
            timeout=8,
            sslopt={"cert_reqs": ssl.CERT_REQUIRED}
        )
        end = time.time() + 8
        while time.time() < end:
            try:
                m = json.loads(ws.recv())
                if m.get("e") == "kline":
                    ws.close()
                    return m["k"]
            except Exception:
                break
        ws.close()
    except Exception as e:
        print("WS | FAIL", type(e).__name__)
    return None

print("V452 | REST-FIRST CONTINUITY")
print("START", now().isoformat())

st = load()
candles = st.get("candles", [])
live_old = st.get("live_candle")

by_ts = {}

for c in candles:
    try:
        t = int(datetime.fromisoformat(
            c["time"].replace("Z", "+00:00")
        ).timestamp())
        by_ts[t] = c
    except Exception:
        pass

added = 0
updated = 0
source = "REST"

try:
    rows = rest()
    print("REST | OK", len(rows))

    current = int(now().timestamp())

    for x in rows:
        t = int(x[0]) // 1000
        close_time = int(x[6]) // 1000
        closed = close_time < current

        c = normalize(x)
        c["closed"] = closed

        if closed:
            if t not in by_ts:
                added += 1
            else:
                updated += 1
            by_ts[t] = c
        else:
            live_old = c

except Exception as e:
    print("REST | FAIL", type(e).__name__, str(e)[:120])
    source = "WS"

    k = ws_fallback()

    if k:
        t = int(k["t"]) // 1000
        c = {
            "time": iso(t),
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
            "trades": int(k["n"]),
            "closed": bool(k["x"])
        }

        if c["closed"]:
            if t not in by_ts:
                added += 1
            by_ts[t] = c
            live_old = None
        else:
            live_old = c

        print("WS | FALLBACK OK")
    else:
        print("WS | FALLBACK FAILED")

closed = sorted(by_ts.values(), key=lambda x: x["time"])

st["candles"] = closed
st["live_candle"] = live_old

if closed:
    st["last_closed"] = closed[-1]["time"]
    st["continuous20"] = continuous(closed)

save(st)

print("SOURCE", source)
print("ADDED", added, "UPDATED", updated)
print("LAST CLOSED", st.get("last_closed"))
print("CONTINUOUS20", st.get("continuous20"))
if live_old:
    print(
        "LIVE",
        live_old["time"],
        "TRADES", live_old["trades"],
        "CLOSE", live_old["close"]
    )
else:
    print("LIVE NONE")

print("RESULT | STATE UPDATED")
