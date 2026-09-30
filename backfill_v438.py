import json,io,zipfile,csv,requests
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; DAY="2026-09-29"; H=3600

def ep(c):
    v=c.get("timestamp",c.get("open_time",c.get("t",c.get("time"))))
    if isinstance(v,(int,float)): return int(v)
    return int(datetime.fromisoformat(v.replace("Z","+00:00")).timestamp())

def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()

st=json.loads(STATE.read_text())
cs=[c for c in st["candles"] if c.get("closed",True)]
last=max(ep(c) for c in cs)
end=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp())
want=list(range(last+H,end,H))

print("V438 | BACKFILL")
print("LAST",iso(last))
print("MISSING",len(want))

def fetch(url):
    try:
        r=requests.get(url,timeout=60)
        print("HTTP",r.status_code,"SIZE",len(r.content))
        if r.status_code!=200:return []
        z=zipfile.ZipFile(io.BytesIO(r.content))
        rows=[]
        for fn in z.namelist():
            with z.open(fn) as f:
                rows += list(csv.reader(io.TextIOWrapper(f,encoding="utf-8")))
        return rows
    except Exception as e:
        print("ERROR",type(e).__name__,e)
        return []

base="https://data.binance.vision/data/futures/um"
urls=[
 f"{base}/daily/klines/{S}/1h/{S}-1h-{DAY}.zip",
 f"{base}/daily/trades/{S}/{S}-trades-{DAY}.zip",
 f"{base}/daily/aggTrades/{S}/{S}-aggTrades-{DAY}.zip"
]

rows=[]
kind=""

for u in urls:
    print("SOURCE",u)
    rows=fetch(u)
    if rows:
        kind=u.split("/daily/")[1].split("/")[0]
        print("FOUND",kind,len(rows))
        break

if not rows:
    print("WAIT | BINANCE ARCHIVE NOT AVAILABLE")
    raise SystemExit(0)

# Klines disponibles
if kind=="klines":
    got={}
    for r in rows:
        try:
            if not r or not r[0].isdigit():continue
            t=int(r[0])//1000
            if t not in want:continue
            got[t]=r
        except:pass

# Trades disponibles
else:
    bars={t:[] for t in want}
    for r in rows:
        try:
            if len(r)<4:continue
            # format trades: id,time,price,qty
            if r[1].isdigit():
                t=int(r[1]); p=float(r[2]); q=float(r[3])
            else:continue
            if t<10_000_000_000:t*=1000
            b=(t//1000//H)*H
            if b in bars:bars[b].append((t,p,q))
        except:pass

    got={}
    for t,x in bars.items():
        if x:
            p=[a[1] for a in x]
            got[t]=[t*1000,p[0],max(p),min(p),p[-1],
                    sum(a[2] for a in x),0,0,0,len(x)]

print("FOUND BARS",len(got),"/",len(want))

if len(got)!=len(want):
    print("WAIT | INCOMPLETE DATA")
    raise SystemExit(0)

template=cs[-1]
out=[]

for t,r in got.items():
    c=template.copy()
    k="timestamp" if "timestamp" in c else "open_time"
    c[k]=iso(t) if isinstance(c[k],str) else t

    vals={
        "open":float(r[1]),"high":float(r[2]),
        "low":float(r[3]),"close":float(r[4]),
        "volume":float(r[5]),"closed":True
    }

    if kind=="klines":
        vals["trades"]=int(r[8])

    else:
        vals["trades"]=int(r[9])

    for name,v in vals.items():
        if name in c:c[name]=v

    out.append(c)

allc={ep(c):c for c in cs}
for c in out:allc[ep(c)]=c

st["candles"]=[allc[t] for t in sorted(allc)]
closed=sorted(ep(c) for c in st["candles"] if c.get("closed",True))
live=max(ep(c) for c in st["candles"])

st["last_closed"]=iso(closed[-1])
st["gap_to_live_hours"]=(live-closed[-1])//H
st["continuous20"]=(len(closed)>=20 and
    all(b-a==H for a,b in zip(closed[-20:],closed[-19:])))

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("LAST CLOSED",st["last_closed"])
print("GAP TO LIVE",st["gap_to_live_hours"],"h")
print("CONTINUOUS20",st["continuous20"])
