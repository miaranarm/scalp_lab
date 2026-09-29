import json,io,zipfile,requests
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; DATE="2026-09-29"; H=3600000

def dt(ms):
    return datetime.fromtimestamp(int(ms)/1000,timezone.utc)

def get(c,*keys):
    for k in keys:
        if k in c:return c[k]
    return None

st=json.loads(STATE.read_text())
cs=[c for c in st["candles"] if c.get("closed",True)]

# Compatible avec les schémas possibles du collector
last=max(
    int(get(c,"open_time","timestamp","t","time"))
    for c in cs
)

target=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp()*1000)
want=list(range(last+H,target,H))

print("V438 | BACKFILL")
print("LAST",dt(last))
print("MISSING",len(want))

if not want:
    print("NOTHING TO BACKFILL")
    raise SystemExit(0)

url=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{S}-1h-{DATE}.zip"
r=requests.get(url,timeout=30)

print("VISION",r.status_code,len(r.content))

if r.status_code!=200:
    print("WAIT | ARCHIVE NOT YET AVAILABLE")
    raise SystemExit(2)

z=zipfile.ZipFile(io.BytesIO(r.content))
rows=[]

import csv
with z.open(z.namelist()[0]) as f:
    for r in csv.reader(io.TextIOWrapper(f,encoding="utf-8")):
        if not r or not r[0].isdigit(): continue
        t=int(r[0])
        if t not in want: continue

        # Reprend exactement le schéma existant
        template=cs[-1].copy()
        old=get(template,"open_time","timestamp","t","time")

        key=(
            "open_time" if "open_time" in template else
            "timestamp" if "timestamp" in template else
            "t" if "t" in template else "time"
        )

        template[key]=t

        for k,v in [
            ("open",float(r[1])),
            ("high",float(r[2])),
            ("low",float(r[3])),
            ("close",float(r[4])),
            ("volume",float(r[5])),
            ("close_time",int(r[6])),
            ("trades",int(r[8]))
        ]:
            if k in template:
                template[k]=v

        template["closed"]=True
        rows.append(template)

print("FOUND",len(rows))

if len(rows)!=len(want):
    print("ERROR | INCOMPLETE BACKFILL")
    raise SystemExit(3)

# Fusion sans doublons
allc={int(get(c,"open_time","timestamp","t","time")):c for c in cs}

for c in rows:
    allc[int(get(c,"open_time","timestamp","t","time"))]=c

st["candles"]=[allc[k] for k in sorted(allc)]

# Recalcule réellement l'écart
last_closed=max(
    int(get(c,"open_time","timestamp","t","time"))
    for c in st["candles"]
    if c.get("closed",True)
)

live=max(
    int(get(c,"open_time","timestamp","t","time"))
    for c in st["candles"]
)

gap=max(0,(live-last_closed)//H)

st["last_closed"]=dt(last_closed).isoformat()
st["gap_to_live_hours"]=gap
st["continuous20"]=len(st["candles"])>=20

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("CANDLES",len(st["candles"]))
print("LAST CLOSED",st["last_closed"])
print("GAP TO LIVE",gap,"h")
print("CONTINUOUS20",st["continuous20"])
