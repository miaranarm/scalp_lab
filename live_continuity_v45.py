import json,time,ssl,websocket
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
WS="wss://fstream.binance.com/ws/solusdt@kline_1h"
RUN=570

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

st=json.loads(STATE.read_text())
cand={}

for c in st.get("candles",[]):
    try:
        t=c.get("time") or c.get("timestamp")
        if isinstance(t,(int,float)):
            t=int(t)//1000
        else:
            t=int(datetime.fromisoformat(
                str(t).replace("Z","+00:00")
            ).timestamp())
        x=dict(c)
        x["time"]=iso(t*1000)
        cand[t]=x
    except:
        pass

live=st.get("live_candle")
if live:
    try:
        t=live.get("time") or live.get("timestamp")
        if isinstance(t,(int,float)):
            t=int(t)//1000
        else:
            t=int(datetime.fromisoformat(
                str(t).replace("Z","+00:00")
            ).timestamp())
        live["time"]=iso(t*1000)
    except:
        live=None

added=0
events=0          # BUGFIX : compte desormais TOUT message recu, meme sans "k"
kline_events=0    # nouveau : nombre de messages qui etaient bien des klines
non_kline=0       # nouveau : messages recus mais sans cle "k" (diagnostic)
closed_seen=0
first_non_kline=None

print("V45.1 | KLINE CONTINUITY")
print("START",datetime.now(timezone.utc).isoformat())

try:
    ws=websocket.create_connection(
        WS,timeout=10,
        sslopt={"cert_reqs":ssl.CERT_REQUIRED}
    )
    print("WS CONNECT | OK")

    start=time.time()

    while time.time()-start<RUN:
        try:
            raw=ws.recv()
            events+=1  # BUGFIX : compte tout message, pas seulement les klines

            m=json.loads(raw)
            k=m.get("k",{})
            if not k:
                non_kline+=1
                if first_non_kline is None:
                    # diagnostic : que renvoie vraiment le flux si ce n'est
                    # pas une kline ? (tronque pour ne pas polluer le log)
                    first_non_kline=raw[:300]
                continue

            kline_events+=1
            t=int(k["t"])//1000

            x={
                "time":iso(int(k["t"])),
                "open":float(k["o"]),
                "high":float(k["h"]),
                "low":float(k["l"]),
                "close":float(k["c"]),
                "volume":float(k["v"]),
                "trades":int(k["n"]),
                "closed":bool(k["x"])
            }

            if x["closed"]:
                if t not in cand:
                    added+=1
                cand[t]=x
                closed_seen+=1
                live=None
            else:
                live=x

        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            print("WS ERROR",e)
            break

    ws.close()

except Exception as e:
    print("CONNECT ERROR",e)

# BUGFIX : l'ancien "if closed_seen: live=None" effacait aussi une bougie
# fraichement demarree des qu'une cloture avait eu lieu PENDANT ce run
# (frequent : toute execution qui traverse une frontiere d'heure). Le
# suivi dans la boucle est deja correct (live=None au moment precis de la
# cloture, live=x des la premiere mise a jour de la bougie suivante) --
# rien a refaire ici.

ordered=sorted(cand)

st["candles"]=[cand[t] for t in ordered]

closed=[t for t in ordered if cand[t].get("closed",True)]

if closed:
    st["last_closed"]=iso(closed[-1]*1000)
    st["continuous20"]=(
        len(closed)>=20 and
        all(b-a==3600 for a,b in zip(closed[-20:],closed[-19:]))
    )

if live:
    st["live_candle"]=live
elif "live_candle" in st:
    del st["live_candle"]

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("EVENTS",events,"(kline:",kline_events,"| non-kline:",non_kline,")")
print("ADDED",added)
print("LAST CLOSED",st.get("last_closed"))
print("CONTINUOUS20",st.get("continuous20"))

if first_non_kline:
    print("FIRST NON-KLINE MESSAGE",first_non_kline)

if live:
    print(
        "LIVE",live["time"],
        "TRADES",live["trades"],
        "CLOSE",live["close"]
    )

if events==0:
    print("WARNING | AUCUN MESSAGE RECU EN",RUN,"SECONDES -- verifier la connexion/le flux")

print("RESULT | STATE UPDATED")
