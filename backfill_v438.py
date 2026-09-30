import json,io,zipfile,csv,requests,time
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; IV="1h"; H=3600
BASE="https://data.binance.vision/data/futures/um"
DAY="2026-09-29"

def raw(c):
    return c.get("timestamp") or c.get("open_time") or c.get("t") or c.get("time")

def ts(c):
    v=raw(c)
    if v is None: raise ValueError("candle without timestamp")
    if isinstance(v,(int,float)): return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()

def fetch(url):
    for n in range(3):
        try:
            r=requests.get(url,timeout=60)
            print("HTTP",r.status_code,"SIZE",len(r.content))
            if r.status_code==200:
                z=zipfile.ZipFile(io.BytesIO(r.content))
                rows=[]
                for f in z.namelist():
                    with z.open(f) as x:
                        rows+=list(csv.reader(
                            io.TextIOWrapper(x,encoding="utf-8")))
                return rows
            print("WAIT HTTP",r.status_code)
        except Exception as e:
            print("ERROR",e)
        if n<2: time.sleep(20)
    return []

st=json.loads(STATE.read_text())

cs=[]
for c in st["candles"]:
    if not c.get("closed",True): continue
    try: ts(c)
    except: continue
    cs.append(c)

if not cs:
    print("ERROR | NO VALID CLOSED CANDLES")
    raise SystemExit(2)

last=max(ts(c) for c in cs)

end=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp())
want=list(range(last+H,end,H))

print("V438 | SAFE BACKFILL")
print("LAST",iso(last))
print("TARGET",iso(end))
print("MISSING",len(want))

if not want:
    print("NOTHING TO BACKFILL")
    raise SystemExit(0)

url=f"{BASE}/daily/klines/{S}/{IV}/{S}-{IV}-{DAY}.zip"
print("SOURCE",url)

rows=fetch(url)

if not rows:
    print("WAIT | BINANCE ARCHIVE UNAVAILABLE")
    raise SystemExit(2)

got={}

for r in rows:
    try:
        if not r or not r[0].isdigit(): continue
        t=int(r[0])//1000
        if t in want: got[t]=r
    except:
        pass

print("FOUND BARS",len(got),"/",len(want))

if len(got)!=len(want):
    print("WAIT | INCOMPLETE DATA")
    raise SystemExit(2)

template=cs[-1]
allc={}

for c in cs:
    try: allc[ts(c)]=c
    except: pass

for t in want:
    r=got[t]
    c=template.copy()

    key="timestamp" if "timestamp" in c else "open_time"

    if key not in c:
        key="timestamp"

    c[key]=iso(t) if not isinstance(c.get(key),int) else t

    vals={
        "open":float(r[1]),
        "high":float(r[2]),
        "low":float(r[3]),
        "close":float(r[4]),
        "volume":float(r[5]),
        "trades":int(r[8]),
        "closed":True
    }

    for k,v in vals.items():
        if k in c: c[k]=v

    allc[t]=c

ordered=sorted(allc)
st["candles"]=[allc[t] for t in ordered]

closed=sorted(allc)

ok=len(closed)>=20 and all(
    b-a==H for a,b in zip(closed[-20:],closed[-19:])
)

st["last_closed"]=iso(closed[-1])
st["continuous20"]=ok

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("ADDED",len(want))
print("LAST CLOSED",st["last_closed"])
print("CONTINUOUS20",st["continuous20"])
