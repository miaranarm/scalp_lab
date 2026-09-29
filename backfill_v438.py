import json,io,zipfile,requests
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; DATE="2026-09-29"
URL=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{S}-1h-{DATE}.zip"

def ts(x): return datetime.fromtimestamp(int(x)/1000,timezone.utc)

st=json.loads(STATE.read_text())
cs=[c for c in st.get("candles",[]) if c.get("closed") is not False]

last=max((int(c["open_time"]) for c in cs),default=0)
want=list(range(last+3600000,
               int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp()*1000),
               3600000))

print("V438 | BACKFILL")
print("LAST",ts(last))
print("MISSING",len(want))

if not want:
    print("NOTHING TO BACKFILL"); raise SystemExit(0)

r=requests.get(URL,timeout=30)
print("VISION",r.status_code,len(r.content))
if r.status_code!=200:
    print("WAIT | ARCHIVE NOT YET AVAILABLE")
    raise SystemExit(2)

z=zipfile.ZipFile(io.BytesIO(r.content))
name=z.namelist()[0]
rows=[]

with z.open(name) as f:
    import csv
    for row in csv.reader(io.TextIOWrapper(f,encoding="utf-8")):
        if not row or not row[0].isdigit(): continue
        t=int(row[0])
        if t in want:
            rows.append({
                "open_time":t,
                "open":float(row[1]),
                "high":float(row[2]),
                "low":float(row[3]),
                "close":float(row[4]),
                "volume":float(row[5]),
                "close_time":int(row[6]),
                "trades":int(row[8]),
                "closed":True
            })

print("FOUND",len(rows))

if len(rows)!=len(want):
    print("ERROR | INCOMPLETE BACKFILL")
    raise SystemExit(3)

cs.extend(rows)
cs.sort(key=lambda x:int(x["open_time"]))

st["candles"]=cs
st["last_closed"]=ts(max(want)).isoformat()
st["gap_to_live_hours"]=0
st["continuous20"]=len(cs)>=20

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("CANDLES",len(cs))
print("LAST CLOSED",st["last_closed"])
print("CONTINUOUS20",st["continuous20"])
