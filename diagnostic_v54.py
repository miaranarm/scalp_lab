import json
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
START=datetime(2026,9,29,tzinfo=timezone.utc)
END=datetime(2026,10,1,16,tzinfo=timezone.utc)

def dt(x): return datetime.fromisoformat(x.replace("Z","+00:00"))

def main():
    print("V54 | FINAL DATA DIAGNOSTIC")
    with open(STATE) as f:s=json.load(f)

    c=[x for x in s.get("candles",[]) if x.get("closed") and x.get("time")]
    c.sort(key=lambda x:x["time"])

    exp=[]
    t=START
    while t<=END:
        exp.append(t.isoformat())
        t+=timedelta(hours=1)

    times=[x["time"] for x in c]
    dup=len(times)-len(set(times))
    missing=[x for x in exp if x not in set(times)]
    extra=[x for x in times if START<=dt(x)<=END and x not in set(exp)]

    gaps=[]
    for a,b in zip(c,c[1:]):
        d=dt(b["time"])-dt(a["time"])
        if d!=timedelta(hours=1): gaps.append((a["time"],b["time"],d))

    inrange=[x for x in c if START<=dt(x["time"])<=END]
    last20=inrange[-20:]
    cont20=len(last20)==20 and all(
        dt(last20[i]["time"])-dt(last20[i-1]["time"])==timedelta(hours=1)
        for i in range(1,20))

    ok=(
        len(inrange)==65 and
        not dup and not missing and not extra and not gaps and
        all(x.get("closed") is True for x in inrange) and
        inrange[0]["time"]==START.isoformat() and
        inrange[-1]["time"]==END.isoformat() and
        cont20
    )

    print("EXPECTED",len(exp))
    print("CLOSED",len(inrange))
    print("DUPLICATES",dup)
    print("MISSING",len(missing))
    print("EXTRA",len(extra))
    print("GAPS",len(gaps))
    print("FIRST",inrange[0]["time"] if inrange else None)
    print("LAST",inrange[-1]["time"] if inrange else None)
    print("LAST20_CONTINUOUS",cont20)

    if missing:
        for x in missing: print("MISSING_TIME",x)
    if gaps:
        for x in gaps: print("GAP",x)

    print("FINAL STATUS","PASS" if ok else "FAIL")

    if not ok: raise SystemExit(1)

if __name__=="__main__":main()
