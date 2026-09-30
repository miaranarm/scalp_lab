import json,io,zipfile,csv,requests
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; DATE="2026-09-29"; H=3600

def key(c):
    for k in ("timestamp","open_time","t","time"):
        if k in c:return k
    raise KeyError("timestamp key not found")

def epoch(c):
    v=c[key(c)]
    if isinstance(v,(int,float)): return int(v)
    return int(datetime.fromisoformat(v.replace("Z","+00:00")).timestamp())

def iso(sec):
    return datetime.fromtimestamp(sec,timezone.utc).isoformat()

st=json.loads(STATE.read_text())
cs=[c for c in st["candles"] if c.get("closed",True)]

last=max(epoch(c) for c in cs)
target=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp())

want=list(range(last+H,target,H))

print("V438 | BACKFILL")
print("LAST",iso(last))
print("MISSING",len(want))

if not want:
    print("NOTHING TO BACKFILL")
    raise SystemExit(0)

url=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{S}-1h-{DATE}.zip"
r=requests.get(url,timeout=30)

print("VISION",r.status_code,len(r.content))

if r.status_code!=200:
    print("WAIT | ARCHIVE NOT AVAILABLE")
    raise SystemExit(2)

z=zipfile.ZipFile(io.BytesIO(r.content))
rows=[]

with z.open(z.namelist()[0]) as f:
    for r in csv.reader(io.TextIOWrapper(f,encoding="utf-8")):
        if not r or not r[0].isdigit(): continue
        t=int(r[0])/1000

        if int(t) not in want: continue

        c=cs[-1].copy()
        k=key(c)

        if isinstance(c[k],str):
            c[k]=iso(int(t))
        else:
            c[k]=int(t)

        for name,value in [
            ("open",float(r[1])),
            ("high",float(r[2])),
            ("low",float(r[3])),
            ("close",float(r[4])),
            ("volume",float(r[5])),
            ("close_time",int(r[6])),
            ("trades",int(r[8]))
        ]:
            if name in c:
                c[name]=value

        c["closed"]=True
        rows.append(c)

print("FOUND",len(rows))

if len(rows)!=len(want):
    print("ERROR | INCOMPLETE BACKFILL")
    raise SystemExit(3)

# Fusion sans doublons
allc={epoch(c):c for c in cs}

for c in rows:
    allc[epoch(c)]=c

st["candles"]=[allc[t] for t in sorted(allc)]

# Dernière bougie fermée
last_closed=max(
    epoch(c) for c in st["candles"]
    if c.get("closed",True)
)

# Bougie live éventuelle
live=max(epoch(c) for c in st["candles"])

st["last_closed"]=iso(last_closed)
st["gap_to_live_hours"]=max(0,(live-last_closed)//H)

# Vérification réelle des 20 dernières bougies
times=sorted(epoch(c) for c in st["candles"] if c.get("closed",True))
st["continuous20"]=(
    len(times)>=20 and
    all(b-a==H for a,b in zip(times[-20:],times[-19:]))
)

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("CANDLES",len(st["candles"]))
print("LAST CLOSED",st["last_closed"])
print("GAP TO LIVE",st["gap_to_live_hours"],"h")
print("CONTINUOUS20",st["continuous20"])
