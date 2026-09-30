import csv,io,json,time,zipfile,requests
from pathlib import Path
from datetime import datetime,timezone,timedelta

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; IV="1h"; H=3600
BASE="https://data.binance.vision/data/futures/um"

def parse(c):
    v=c.get("time") or c.get("timestamp") or c.get("open_time") or c.get("t")
    if v is None:return None
    if isinstance(v,(int,float)):return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()

def fetch(day):
    u=f"{BASE}/daily/klines/{S}/{IV}/{S}-{IV}-{day}.zip"
    print("SOURCE",u)
    for n in range(3):
        try:
            r=requests.get(u,timeout=60)
            print("HTTP",r.status_code,"SIZE",len(r.content))
            if r.status_code==404:return None
            if r.status_code!=200:
                time.sleep(10);continue
            z=zipfile.ZipFile(io.BytesIO(r.content))
            out=[]
            for f in z.namelist():
                with z.open(f) as x:
                    out+=list(csv.reader(io.TextIOWrapper(x,encoding="utf-8")))
            return out
        except Exception as e:
            print("ERROR",e)
            if n<2:time.sleep(10)
    return []

st=json.loads(STATE.read_text())
raw=st.get("candles",[])

closed={}
open_c=[]

for c in raw:
    if not isinstance(c,dict):continue
    t=parse(c)
    if t is None:continue
    c=dict(c);c["time"]=iso(t)
    if c.get("closed",True):
        closed[t]=c
    else:
        open_c.append(c)

if not closed:
    print("ERROR | NO CLOSED CANDLES")
    raise SystemExit(2)

now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
end=int((now-timedelta(hours=1)).timestamp())

lo=min(closed)
hi=max(closed)
scan_end=max(end,hi)

expected=range(lo,scan_end+H,H)
missing=[t for t in expected if t not in closed]

print("V439 | GAP BACKFILL")
print("FIRST",iso(lo))
print("LAST",iso(hi))
print("TARGET",iso(end))
print("GAPS BEFORE",len(missing))

if not missing:
    st["candles"]=sorted(closed.values(),key=parse)+open_c
    ordered=sorted(closed)
    st["last_closed"]=iso(ordered[-1])
    st["continuous20"]=len(ordered)>=20 and all(
        b-a==H for a,b in zip(ordered[-20:],ordered[-19:])
    )
    STATE.write_text(json.dumps(st,indent=2)+"\n")
    print("NOTHING TO BACKFILL")
    print("LAST CLOSED",st["last_closed"])
    print("CONTINUOUS20",st["continuous20"])
    raise SystemExit(0)

days=sorted({
    datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")
    for t in missing
})

got={}
wait=False

for day in days:
    rows=fetch(day)
    if rows is None:
        print("NOT YET PUBLISHED |",day)
        wait=True
        continue
    if not rows:
        print("FETCH ERROR |",day)
        wait=True
        continue

    for r in rows:
        try:
            if not r or not r[0].isdigit():continue
            t=int(r[0])//1000
            if t not in missing:continue
            got[t]={
                **(next(iter(closed.values())).copy()),
                "time":iso(t),
                "open":float(r[1]),
                "high":float(r[2]),
                "low":float(r[3]),
                "close":float(r[4]),
                "volume":float(r[5]),
                "trades":int(r[8]),
                "closed":True
            }
        except Exception:
            pass

print("FOUND",len(got),"/",len(missing))

closed.update(got)

ordered=sorted(closed)

st["candles"]=[closed[t] for t in ordered]+open_c
st["last_closed"]=iso(ordered[-1])

remaining=[t for t in expected if t not in closed]

st["continuous20"]=len(ordered)>=20 and all(
    b-a==H for a,b in zip(ordered[-20:],ordered[-19:])
)

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("ADDED",len(got))
print("GAPS AFTER",len(remaining))
print("LAST CLOSED",st["last_closed"])
print("CONTINUOUS20",st["continuous20"])

if remaining:
    print("REMAINING:")
    for t in remaining[:20]:print(" ",iso(t))
    if len(remaining)>20:print(" ...",len(remaining)-20,"more")

if wait:
    print("WAIT | SOME ARCHIVES UNAVAILABLE")
