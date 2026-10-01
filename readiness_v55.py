import json,sys
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
START=datetime(2026,9,29,tzinfo=timezone.utc)
END=datetime(2026,10,1,16,tzinfo=timezone.utc)

def dt(x):return datetime.fromisoformat(x.replace("Z","+00:00"))

def main():
 print("V55 | SCALP LAB READINESS")
 try:
  with open(STATE) as f:s=json.load(f)
 except Exception as e:
  print("STATE ERROR",e);sys.exit(1)

 c=[x for x in s.get("candles",[]) if x.get("closed") and x.get("time")]
 c.sort(key=lambda x:x["time"])
 c=[x for x in c if START<=dt(x["time"])<=END]

 exp=[]
 t=START
 while t<=END:exp.append(t.isoformat());t+=timedelta(hours=1)

 times=[x["time"] for x in c]
 checks={
  "COUNT":len(c)==65,
  "FIRST":bool(c) and c[0]["time"]==START.isoformat(),
  "LAST":bool(c) and c[-1]["time"]==END.isoformat(),
  "UNIQUE":len(times)==len(set(times)),
  "FIELDS":all(all(k in x for k in
   ("time","open","high","low","close","volume","trades","closed")) for x in c),
  "OHLC":all(x["high"]>=max(x["open"],x["close"]) and
             x["low"]<=min(x["open"],x["close"]) for x in c),
  "POSITIVE":all(x["open"]>0 and x["high"]>0 and
                 x["low"]>0 and x["close"]>0 and x["volume"]>=0
                 for x in c),
  "CONTINUOUS":all(
   dt(c[i]["time"])-dt(c[i-1]["time"])==timedelta(hours=1)
   for i in range(1,len(c))),
  "CLOSED":all(x["closed"] is True for x in c)
 }

 for k,v in checks.items():print(k,"OK" if v else "FAIL")

 ok=all(checks.values())
 print("CANDLES",len(c))
 print("RANGE",c[0]["time"],"->",c[-1]["time"])
 print("READINESS","READY" if ok else "NOT READY")
 if not ok:sys.exit(1)

if __name__=="__main__":main()
