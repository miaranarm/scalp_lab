import json,websocket
from pathlib import Path
from datetime import datetime,timedelta,timezone

S="SOLUSDT"
STATE=Path("state/live_v4386.json")
OUT=Path("results/live_candles_v438.csv")
WS="wss://ws-fapi.binance.com/ws-fapi/v1"

def dt(x):return datetime.fromisoformat(x).astimezone(timezone.utc)
def iso(x):return x.strftime("%Y-%m-%dT%H:%M:%S+00:00")

def load():
 if not STATE.exists():
  print("STATE MISSING");raise SystemExit(1)
 return json.loads(STATE.read_text())

def ws_klines(start,end):
 print("WS API | CONNECT")
 try:
  w=websocket.create_connection(WS,timeout=20)
  p={
   "id":"v438-backfill",
   "method":"klines",
   "params":{
    "symbol":S,"interval":"1h",
    "startTime":int(start.timestamp()*1000),
    "endTime":int(end.timestamp()*1000)-1,
    "limit":100
   }
  }
  w.send(json.dumps(p))
  r=json.loads(w.recv())
  w.close()

  print("WS API STATUS |",r.get("status"))
  if r.get("status")!=200:
   print("WS API ERROR |",r.get("error"))
   return []

  rows=r.get("result",[])
  print("WS API KLINES |",len(rows))

  out=[]
  for p in rows:
   try:
    t=datetime.fromtimestamp(int(p[0])/1000,timezone.utc)
    out.append({
     "time":iso(t),
     "open":float(p[1]),"high":float(p[2]),
     "low":float(p[3]),"close":float(p[4]),
     "volume":float(p[5]),"trades":int(p[8]),
     "closed":True
    })
   except:pass
  return out

 except Exception as e:
  print("WS API ERROR |",type(e).__name__,str(e))
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
 print("V438.BACKFILL V3 | WS API")

 s=load()
 cs={c["time"]:c for c in s.get("candles",[])}
 live=s.get("live")

 for k in list(cs):
  if not cs[k].get("closed",True):
   print("REMOVE PARTIAL |",k)
   del cs[k]

 last=max(cs)
 lt=dt(live["time"]) if live else dt(last)+timedelta(hours=1)

 a=dt(last)+timedelta(hours=1)
 need=[]
 while a<lt:
  need.append(iso(a))
  a+=timedelta(hours=1)

 print("LAST CLOSED |",last)
 print("LIVE |",live["time"] if live else None)
 print("MISSING |",len(need))

 if not need:
  print("NOTHING TO BACKFILL")
  return

 rows=ws_klines(dt(need[0]),dt(need[-1])+timedelta(hours=1))
 found={x["time"]:x for x in rows if x["time"] in need}

 print("FOUND |",len(found),"/",len(need))

 missing=[x for x in need if x not in found]
 if missing:
  print("MISSING |",len(missing))
  for x in missing:print(" ",x)
  print("RESULT | BACKFILL INCOMPLETE")
  raise SystemExit(2)

 cs.update(found)
 if live:cs.pop(live["time"],None)

 vals=sorted(cs.values(),key=lambda x:x["time"])
 gaps=[]

 for a,b in zip(vals,vals[1:]):
  h=int((dt(b["time"])-dt(a["time"])).total_seconds()/3600)-1
  if h>0:
   gaps += [
    iso(dt(a["time"])+timedelta(hours=i))
    for i in range(1,h+1)
   ]

 gap=0
 if live:
  gap=max(0,int(
   (dt(live["time"])-dt(vals[-1]["time"])).total_seconds()/3600)-1)

 s.update({
  "candles":vals,
  "last_closed":vals[-1]["time"],
  "closed_count":len(vals),
  "gaps":gaps,
  "gap_to_live_hours":gap,
  "warmup":not(len(vals)>=20 and not gaps and gap==0),
  "continuous20":len(vals)>=20 and not gaps and gap==0,
  "updated":datetime.now(timezone.utc).isoformat()
 })

 save(s)

 print("CANDLES AFTER |",len(vals))
 print("GAPS INTERNAL |",len(gaps))
 print("GAP TO LIVE |",gap,"h")
 print("CONTINUOUS20 |",s["continuous20"])
 print("RESULT |","BACKFILL OK" if s["continuous20"]
       else "BACKFILL INCOMPLETE")

 if not s["continuous20"]:raise SystemExit(2)

if __name__=="__main__":main()
