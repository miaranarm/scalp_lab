import json,io,zipfile,csv,requests
from pathlib import Path
from datetime import datetime,timezone

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; H=3600
END=int(datetime(2026,9,29,15,tzinfo=timezone.utc).timestamp())

def ep(c):
    v=c.get("timestamp",c.get("open_time",c.get("t",c.get("time"))))
    return int(v) if isinstance(v,(int,float)) else int(
        datetime.fromisoformat(v.replace("Z","+00:00")).timestamp())

def iso(t): return datetime.fromtimestamp(t,timezone.utc).isoformat()

st=json.loads(STATE.read_text())
cs=[c for c in st["candles"] if c.get("closed",True)]
last=max(map(ep,cs))
want=list(range(last+H,END,H))

print("V438 | BACKFILL")
print("LAST",iso(last))
print("MISSING",len(want))

got={}

# 1. Binance Data Vision
day=iso(want[0])[:10]
url=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{S}-1h-{day}.zip"

try:
    r=requests.get(url,timeout=60)
    print("ARCHIVE HTTP",r.status_code,"SIZE",len(r.content))
    if r.status_code==200:
        z=zipfile.ZipFile(io.BytesIO(r.content))
        for fn in z.namelist():
            with z.open(fn) as f:
                for x in csv.reader(io.TextIOWrapper(f,encoding="utf-8")):
                    try:
                        t=int(x[0])//1000
                        if t in want: got[t]=x
                    except: pass
except Exception as e:
    print("ARCHIVE ERROR",e)

# 2. Binance Futures API
if len(got)<len(want):
    print("FALLBACK | Binance API")
    try:
        p={"symbol":S,"interval":"1h",
           "startTime":want[0]*1000,
           "endTime":END*1000-1,"limit":100}
        r=requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params=p,timeout=30)
        print("API HTTP",r.status_code)
        if r.status_code==200:
            for x in r.json():
                t=int(x[0])//1000
                if t in want: got[t]=x
        else:
            print("API ERROR",r.text[:250])
    except Exception as e:
        print("API ERROR",e)

# 3. Static klines fallback
if len(got)<len(want):
    print("FALLBACK | STATIC KLINES")
    try:
        # One monthly 1h file: <=744 candles
        month=iso(want[0])[:7]
        url=(
            f"https://raw.githubusercontent.com/finom/static-klines/"
            f"main/data/{S}/1h/{month}.json"
        )
        r=requests.get(url,timeout=30)
        print("STATIC HTTP",r.status_code,"SIZE",len(r.content))

        if r.status_code==200:
            data=r.json()
            for x in data:
                t=int(x[0])
                if t>10_000_000_000:t//=1000
                if t in want: got[t]=x
    except Exception as e:
        print("STATIC ERROR",e)

print("FOUND BARS",len(got),"/",len(want))

if len(got)!=len(want):
    print("WAIT | DATA INCOMPLETE")
    raise SystemExit(2)

template=cs[-1]
out=[]

for t in sorted(want):
    r=got[t]
    c=template.copy()

    k="timestamp" if "timestamp" in c else "open_time"
    c[k]=iso(t) if isinstance(c[k],str) else t

    o,h,l,cl,v,tr=(
        float(r[1]),float(r[2]),float(r[3]),
        float(r[4]),float(r[5]),int(r[8])
    )

    vals={"open":o,"high":h,"low":l,
          "close":cl,"volume":v,
          "trades":tr,"closed":True}

    for n,v in vals.items():
        if n in c:c[n]=v

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
