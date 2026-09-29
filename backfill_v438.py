import io,json,zipfile,requests
from pathlib import Path
from datetime import datetime,timedelta,timezone

S="SOLUSDT"
STATE=Path("state/live_v4386.json")
OUT=Path("results/live_candles_v438.csv")

def dt(x): return datetime.fromisoformat(x).astimezone(timezone.utc)
def iso(x): return x.strftime("%Y-%m-%dT%H:%M:%S+00:00")

def load():
    if not STATE.exists():
        print("STATE MISSING"); raise SystemExit(1)
    s=json.loads(STATE.read_text())
    return s

def vision(day):
    u=f"https://data.binance.vision/data/futures/um/daily/klines/{S}/1h/{S}-1h-{day:%Y-%m-%d}.zip"
    try:
        r=requests.get(u,timeout=20)
        print("VISION",day.date(),r.status_code)
        if r.status_code!=200:return []
        z=zipfile.ZipFile(io.BytesIO(r.content))
        f=z.open(z.namelist()[0])
        rows=[]
        for x in f:
            p=x.decode().strip().split(",")
            if not p or p[0].lower() in ("open_time","timestamp"):continue
            try:
                t=datetime.fromtimestamp(int(p[0])/1000,timezone.utc)
                rows.append({
                    "time":iso(t),"open":float(p[1]),"high":float(p[2]),
                    "low":float(p[3]),"close":float(p[4]),
                    "volume":float(p[5]),"trades":int(p[8]),"closed":True
                })
            except: pass
        return rows
    except Exception as e:
        print("VISION ERROR",type(e).__name__)
        return []

def save(s):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s,indent=2))
    OUT.parent.mkdir(exist_ok=True)
    cs=sorted(s["candles"],key=lambda x:x["time"])
    with OUT.open("w") as f:
        f.write("time,open,high,low,close,volume,trades,closed\n")
        for c in cs:
            f.write(",".join(str(c.get(k,"")) for k in
                ["time","open","high","low","close","volume","trades","closed"])+"\n")

def main():
    print("V438.BACKFILL | START")
    s=load()

    cs={c["time"]:c for c in s.get("candles",[])}
    live=s.get("live")

    # Retire les éventuelles bougies live incomplètes présentes dans candles.
    for k in list(cs):
        if not cs[k].get("closed",True):
            print("REMOVE PARTIAL |",k)
            del cs[k]

    last=max(cs) if cs else None
    if not last:
        print("NO HISTORY"); raise SystemExit(1)

    # Le live actuel est la référence de fin.
    lt=dt(live["time"]) if live else None
    end=lt or dt(last)+timedelta(hours=1)

    # Bougies attendues entre la dernière historique et le live.
    a=dt(last)+timedelta(hours=1)
    need=[]
    while a<end:
        need.append(iso(a))
        a+=timedelta(hours=1)

    print("LAST CLOSED |",last)
    print("LIVE |",live["time"] if live else None)
    print("MISSING |",len(need))

    found={}
    if need:
        days={dt(x).date() for x in need}
        for d in sorted(days):
            for c in vision(datetime.combine(d,datetime.min.time(),tzinfo=timezone.utc)):
                if c["time"] in need:
                    found[c["time"]]=c

    print("BACKFILL FOUND |",len(found))

    missing=[x for x in need if x not in found]
    if missing:
        print("BACKFILL MISSING |",len(missing))
        for x in missing: print("  ",x)
        print("RESULT | BACKFILL INCOMPLETE")
        raise SystemExit(2)

    cs.update(found)

    # Le live ne doit jamais entrer dans candles.
    if live:
        cs.pop(live["time"],None)

    vals=sorted(cs.values(),key=lambda x:x["time"])
    gaps=[]
    for a,b in zip(vals,vals[1:]):
        h=int((dt(b["time"])-dt(a["time"])).total_seconds()/3600)-1
        if h>0:gaps.extend(
            iso(dt(a["time"])+timedelta(hours=i))
            for i in range(1,h+1))

    gap_live=0
    if live:
        gap_live=max(0,int(
            (dt(live["time"])-dt(vals[-1]["time"])).total_seconds()/3600)-1)

    s["candles"]=vals
    s["last_closed"]=vals[-1]["time"]
    s["closed_count"]=len(vals)
    s["gaps"]=gaps
    s["gap_to_live_hours"]=gap_live
    s["warmup"]=not(len(vals)>=20 and not gaps and gap_live==0)
    s["continuous20"]=len(vals)>=20 and not gaps and gap_live==0
    s["updated"]=datetime.now(timezone.utc).isoformat()

    save(s)

    print("CANDLES AFTER |",len(vals))
    print("GAPS INTERNAL |",len(gaps))
    print("GAP TO LIVE |",gap_live,"h")
    print("CONTINUOUS20 |",s["continuous20"])
    print("RESULT |","BACKFILL OK" if s["continuous20"] else "BACKFILL INCOMPLETE")

    if not s["continuous20"]:raise SystemExit(2)

if __name__=="__main__":
    main()
