import csv,io,json,time,zipfile,requests
from pathlib import Path
from datetime import datetime,timezone,timedelta

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; IV="1h"; H=3600
BASE="https://data.binance.vision/data/futures/um"

def ts(c):
    v=c.get("time") or c.get("timestamp") or c.get("open_time") or c.get("t")
    if v is None:return None
    if isinstance(v,(int,float)):return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()

def get(url):
    print("SOURCE",url)
    for n in range(3):
        try:
            r=requests.get(url,timeout=90)
            print("HTTP",r.status_code,"SIZE",len(r.content))
            if r.status_code==404:return None
            if r.status_code==200:
                return r.content
        except Exception as e: print("ERROR",e)
        if n<2:time.sleep(8)
    return []

def rows_zip(data):
    try:
        z=zipfile.ZipFile(io.BytesIO(data))
        for f in z.namelist():
            with z.open(f) as x:
                for r in csv.reader(io.TextIOWrapper(x,encoding="utf-8")):
                    yield r
    except Exception:
        return

def kline_file(day,monthly=False):
    p="monthly" if monthly else "daily"
    name=day[:7] if monthly else day
    u=f"{BASE}/{p}/klines/{S}/{IV}/{S}-{IV}-{name}.zip"
    d=get(u)
    return [] if d in (None,[]) else list(rows_zip(d))

def trades_file(day):
    u=f"{BASE}/daily/trades/{S}/{S}-trades-{day}.zip"
    d=get(u)
    return [] if d in (None,[]) else rows_zip(d)

def make_kline(r,template,t):
    try:
        if len(r)<9 or not str(r[0]).isdigit():return None
        return {
            **template,
            "time":iso(t),
            "open":float(r[1]),"high":float(r[2]),
            "low":float(r[3]),"close":float(r[4]),
            "volume":float(r[5]),
            "trades":int(r[8]),
            "closed":True
        }
    except:return None

def build_trades(rows,need,template):
    out={}
    for r in rows:
        try:
            if not r or not str(r[0]).isdigit():continue

            # Futures trades:
            # id,price,qty,quoteQty,time,isBuyerMaker,...
            if len(r)<5:continue

            tm=int(r[4])
            tm=tm//1000
            bar=(tm//H)*H
            if bar not in need:continue

            p=float(r[1]); q=float(r[2])

            if bar not in out:
                out[bar]={
                    "time":iso(bar),
                    "open":p,"high":p,"low":p,"close":p,
                    "volume":q,"trades":1,"closed":True
                }
            else:
                x=out[bar]
                x["high"]=max(x["high"],p)
                x["low"]=min(x["low"],p)
                x["close"]=p
                x["volume"]+=q
                x["trades"]+=1

        except:
            pass

    return {
        t:{**template,**v}
        for t,v in out.items()
    }

st=json.loads(STATE.read_text())
raw=st.get("candles",[])

closed={}
opened=[]

for c in raw:
    if not isinstance(c,dict):continue
    t=ts(c)
    if t is None:continue
    c=dict(c);c["time"]=iso(t)
    if c.get("closed",True):closed[t]=c
    else:opened.append(c)

if not closed:
    print("ERROR | NO CLOSED CANDLES")
    raise SystemExit(2)

now=datetime.now(timezone.utc).replace(
    minute=0,second=0,microsecond=0
)
target=int((now-timedelta(hours=1)).timestamp())

lo=min(closed)
hi=max(closed)
end=max(target,hi)

expected=range(lo,end+H,H)
missing={t for t in expected if t not in closed}

print("V44 | HYBRID BACKFILL")
print("FIRST",iso(lo))
print("LAST",iso(hi))
print("TARGET",iso(target))
print("MISSING",len(missing))

if not missing:
    print("NOTHING TO BACKFILL")
    raise SystemExit(0)

template=next(iter(closed.values())).copy()
added={}

# --------------------------------------------------
# 1. DAILY KLINES
# --------------------------------------------------

days=sorted({
    datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")
    for t in missing
})

for day in days:
    rows=kline_file(day)
    if not rows:
        continue

    for r in rows:
        try:
            if not r or not str(r[0]).isdigit():continue
            t=int(r[0])//1000
            if t in missing:
                x=make_kline(r,template,t)
                if x:added[t]=x
        except:
            pass

print("DAILY KLINES",len(added))

# --------------------------------------------------
# 2. MONTHLY KLINES
# --------------------------------------------------

left=missing-set(added)

months=sorted({
    datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m")
    for t in left
})

for month in months:
    rows=kline_file(month+"-01",monthly=True)
    if not rows:
        continue

    for r in rows:
        try:
            if not r or not str(r[0]).isdigit():continue
            t=int(r[0])//1000
            if t in left:
                x=make_kline(r,template,t)
                if x:added[t]=x
        except:
            pass

print("MONTHLY KLINES",len(added))

# --------------------------------------------------
# 3. DAILY TRADES -> 1H
# --------------------------------------------------

left=missing-set(added)

days=sorted({
    datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")
    for t in left
})

for day in days:
    rows=trades_file(day)
    if not rows:continue

    need={
        t for t in left
        if datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")==day
    }

    x=build_trades(rows,need,template)

    for t,v in x.items():
        if t in left:
            added[t]=v

    print("TRADES",day,len(x))

print("FOUND",len(added),"/",len(missing))

# --------------------------------------------------
# SAVE ONLY IF SOMETHING WAS REALLY ADDED
# --------------------------------------------------

if not added:
    print("WAIT | NO SOURCE AVAILABLE")
    print("STATE UNCHANGED")
    raise SystemExit(0)

closed.update(added)
ordered=sorted(closed)

new_candles=[closed[t] for t in ordered]+opened

old_state=json.dumps(st,sort_keys=True)

st["candles"]=new_candles
st["last_closed"]=iso(ordered[-1])

st["continuous20"]=(len(ordered)>=20 and all(
    b-a==H for a,b in zip(ordered[-20:],ordered[-19:])
))

new_state=json.dumps(st,sort_keys=True)

if new_state!=old_state:
    STATE.write_text(json.dumps(st,indent=2)+"\n")

remaining=[t for t in expected if t not in closed]

print("ADDED",len(added))
print("GAPS AFTER",len(remaining))
print("LAST CLOSED",st["last_closed"])
print("CONTINUOUS20",st["continuous20"])

if remaining:
    print("REMAINING",len(remaining))
    for t in remaining[:15]:
        print(" ",iso(t))

if added:
    print("RESULT | BACKFILL UPDATED")
else:
    print("RESULT | NO CHANGE")
