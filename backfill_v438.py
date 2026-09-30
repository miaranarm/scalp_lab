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
start=last+H
end=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp())

want=list(range(start,end,H))
print("V438 | TRADE BACKFILL")
print("LAST",iso(last))
print("MISSING",len(want))

def get(url):
    try:
        r=requests.get(url,timeout=60)
        print("SOURCE",url)
        print("HTTP",r.status_code,"SIZE",len(r.content))
        if r.status_code!=200:return []
        z=zipfile.ZipFile(io.BytesIO(r.content))
        out=[]
        for fn in z.namelist():
            with z.open(fn) as f:
                for row in csv.reader(io.TextIOWrapper(f,encoding="utf-8")):
                    if not row or not row[0].isdigit():continue
                    try:
                        t=int(row[0])
                    except:continue
                    out.append(row)
        return out
    except Exception as e:
        print("ERROR",type(e).__name__,e)
        return []

base="https://data.binance.vision/data/futures/um"

sources=[
    f"{base}/daily/trades/{S}/{S}-trades-{DAY}.zip",
    f"{base}/daily/aggTrades/{S}/{S}-aggTrades-{DAY}.zip"
]

rows=[]
for u in sources:
    rows=get(u)
    if rows:break

if not rows:
    print("NO TRADE DATA")
    raise SystemExit(2)

print("ROWS",len(rows))

# Détection simple du format trades / aggTrades
trades=[]
for r in rows:
    try:
        if len(r)>=6:
            # trades: id,time,price,qty,...
            if len(r[1])>=12:
                tid=int(r[0]); t=int(r[1]); p=float(r[2]); q=float(r[3])
                trades.append((t,p,q))
        if len(r)>=5:
            # aggTrades: aggId,price,qty,firstId,lastId,time,...
            pass
    except:
        continue

if not trades:
    print("NO PARSEABLE TRADES")
    raise SystemExit(3)

print("TRADES",len(trades))

# Binance trades : timestamp généralement ms
bars={t:[] for t in want}

for t,p,q in trades:
    if t<10_000_000_000:t*=1000
    sec=t//1000
    b=(sec//H)*H
    if b in bars:
        bars[b].append((t,p,q))

print("BARS FOUND",sum(bool(v) for v in bars.values()),"/",len(want))

if any(not bars[t] for t in want):
    print("INCOMPLETE")
    for t in want:
        if not bars[t]:
            print("MISSING",iso(t))
    raise SystemExit(4)

template=cs[-1]
out=[]

for t in want:
    x=bars[t]
    prices=[a[1] for a in x]
    qty=sum(a[2] for a in x)

    c=template.copy()
    k="timestamp" if "timestamp" in c else "open_time"

    c[k]=iso(t) if isinstance(c[k],str) else t
    vals={
        "open":prices[0],
        "high":max(prices),
        "low":min(prices),
        "close":prices[-1],
        "volume":qty,
        "trades":len(x),
        "closed":True
    }

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

st["continuous20"]=(
    len(closed)>=20 and
    all(b-a==H for a,b in zip(closed[-20:],closed[-19:]))
)

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL OK")
print("CANDLES",len(st["candles"]))
print("LAST CLOSED",st["last_closed"])
print("GAP TO LIVE",st["gap_to_live_hours"],"h")
print("CONTINUOUS20",st["continuous20"])
