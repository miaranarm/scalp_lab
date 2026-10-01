import os,json,urllib.request,urllib.parse
from datetime import datetime,timezone,timedelta

STATE="state/live_v4386.json"
T=[
"2026-10-01T00:00:00+00:00",
"2026-10-01T06:00:00+00:00",
"2026-10-01T12:00:00+00:00",
"2026-10-01T13:00:00+00:00"]
BASES=[
"https://fapi.binance.com/fapi/v1/klines",
"https://fapi1.binance.com/fapi/v1/klines",
"https://fapi2.binance.com/fapi/v1/klines",
"https://fapi3.binance.com/fapi/v1/klines",
"https://fapi4.binance.com/fapi/v1/klines",
"https://www.binance.com/fapi/v1/klines"]

def main():
 print("V53 | SOLUSDT FUTURES GAP REPAIR")
 with open(STATE) as f:s=json.load(f)
 q=[int(datetime.fromisoformat(x).timestamp()*1000) for x in T]
 a=min(q);b=max(q)+3599999
 found={}
 params=urllib.parse.urlencode({
  "symbol":"SOLUSDT","interval":"1h",
  "startTime":a,"endTime":b,"limit":20})
 for base in BASES:
  u=base+"?"+params
  print("TRY",base)
  try:
   r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
   z=json.loads(urllib.request.urlopen(r,timeout=15).read())
   if not isinstance(z,list):raise ValueError("BAD RESPONSE")
   for x in z:
    if len(x)>=9:
     k=datetime.fromtimestamp(int(x[0])/1000,timezone.utc).isoformat()
     if k in T:
      found[k]={
       "time":k,"open":float(x[1]),"high":float(x[2]),
       "low":float(x[3]),"close":float(x[4]),
       "volume":float(x[5]),"trades":int(x[8]),"closed":True}
   print("FOUND",len(found),"/",len(T))
   if len(found)==len(T):break
  except Exception as e:
   print("FAIL",type(e).__name__,str(e)[:100])

 if len(found)!=len(T):
  print("REPAIR INCOMPLETE")
  for x in T:
   if x not in found:print("MISSING",x)
  print("STATE NOT MODIFIED")
  return

 candles=s.setdefault("candles",[])
 by={x["time"]:x for x in candles if x.get("time")}
 for k in T:
  by[k]=found[k]
 candles=list(by.values())
 candles.sort(key=lambda x:x["time"])
 candles=candles[-5000:]
 c=[x for x in candles if x.get("closed")]
 c.sort(key=lambda x:x["time"])
 last20=c[-20:]
 ok=len(last20)==20 and all(
  datetime.fromisoformat(last20[i]["time"])-
  datetime.fromisoformat(last20[i-1]["time"])==timedelta(hours=1)
  for i in range(1,20))
 print("CLOSED",len(c))
 print("LAST",c[-1]["time"])
 print("CONTINUOUS20",ok)
 if not ok:
  print("CONTINUITY CHECK FAILED")
  print("STATE NOT MODIFIED")
  return

 s["candles"]=candles
 s["last_closed"]=c[-1]["time"]
 s["continuous20"]=True
 with open(STATE+".tmp","w") as f:json.dump(s,f,indent=2)
 os.replace(STATE+".tmp",STATE)
 print("STATE UPDATED")
 print("REPAIR COMPLETE")

if __name__=="__main__":main()
