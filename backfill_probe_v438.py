import requests,zipfile,io
from datetime import datetime,timezone,timedelta

S="SOLUSDT"
D=datetime(2026,9,29,tzinfo=timezone.utc)

URLS=[
 f"https://data.binance.vision/data/futures/um/daily/trades/{S}/{S}-trades-{D:%Y-%m-%d}.zip",
 f"https://data.binance.vision/data/futures/um/daily/aggTrades/{S}/{S}-aggTrades-{D:%Y-%m-%d}.zip",
 f"https://data.binance.vision/data/futures/um/monthly/trades/{S}/{S}-trades-{D:%Y-%m}.zip",
 f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{S}/{S}-aggTrades-{D:%Y-%m}.zip",
]

def test(u):
 try:
  r=requests.get(u,timeout=20)
  print("SOURCE",u)
  print("HTTP",r.status_code,"SIZE",len(r.content))
  if r.status_code!=200:return
  z=zipfile.ZipFile(io.BytesIO(r.content))
  print("ZIP",z.namelist()[:3])
 except Exception as e:
  print("ERROR",type(e).__name__,e)

print("V438 | SOURCE PROBE")
for u in URLS:test(u)
print("DONE")
