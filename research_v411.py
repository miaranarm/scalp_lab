from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests,time
import pandas as pd
import numpy as np

O=Path("results")
SRC=O/"v44_trades_oos.csv"
BASES=[
 "https://fapi.binance.com/fapi/v1/klines",
 "https://www.binance.com/fapi/v1/klines",
 "https://data-api.binance.vision/fapi/v1/klines"
]
MAX=1500
WORKERS=6
BARS=6

d=pd.read_csv(SRC)

need=["symbol","interval","entry_time","exit_time","side",
      "entry_price","tp_price","sl_price","net"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","sl_price","net"]:
 d[c]=pd.to_numeric(d[c],errors="coerce")

d.entry_time=pd.to_datetime(d.entry_time,utc=True)
d.exit_time=pd.to_datetime(d.exit_time,utc=True)

def step(x):
 return {"5m":300000,"15m":900000}[x]

def fetch(k):
 sym,it=k
 x=d[(d.symbol==sym)&(d.interval==it)]
 st=int(x.entry_time.min().timestamp()*1000)
 en=int((x.entry_time.max()+pd.Timedelta(step(it)/1000*(BARS+2),"s")).timestamp()*1000)

 for base in BASES:
  try:
   rows=[];cur=st;s=requests.Session()
   while cur<en:
    for z in range(4):
     try:
      r=s.get(base,params={
       "symbol":sym,"interval":it,
       "startTime":cur,"endTime":en,"limit":MAX
      },timeout=30)
      if r.status_code==200:
       a=r.json();break
      if r.status_code in (418,429,500,502,503,504):
       time.sleep(1+z);continue
      raise RuntimeError(f"HTTP {r.status_code}")
     except Exception:
      if z==3: raise
      time.sleep(1+z)
    if not a: break
    rows.extend(a)
    nxt=a[-1][0]+step(it)
    if nxt<=cur: break
    cur=nxt
    if len(a)<MAX: break

   if rows:
    q=pd.DataFrame(rows,columns=[
     "ts","open","high","low","close","vol",
     "close_ts","quote","trades","tb","tq","x"
    ])
    q=q.drop_duplicates("ts")
    q.ts=pd.to_datetime(q.ts,unit="ms",utc=True)
    for c in ["open","high","low","close"]:
     q[c]=pd.to_numeric(q[c],errors="coerce")
    q=q.set_index("ts")[["open","high","low","close"]]
    print("DATA",sym,it,len(q),base)
    return k,q
  except Exception as e:
   print("FALLBACK",sym,it,base,e)

 raise RuntimeError(f"IMPOSSIBLE {sym} {it}")

keys=list(d.groupby(["symbol","interval"]).groups)
data={}

print("V4.11 | ENTRY QUALITY")
print("TRADES",len(d))

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
 fs=[ex.submit(fetch,k) for k in keys]
 for f in as_completed(fs):
  k,q=f.result();data[k]=q

def one(r):
 q=data[(r.symbol,r.interval)]
 e=float(r.entry_price)
 side=str(r.side).upper()
 s=step(r.interval)
 t=r.entry_time

 # bougies suivant l'entrée
 q=q[q.index>t].iloc[:BARS]

 out={}
 if q.empty:return out

 if side=="LONG":
  fav=(q.high/e-1)
  adv=(q.low/e-1)
 else:
  fav=(1-q.low/e)
  adv=(q.high/e-1)

 for i in range(BARS):
  n=i+1
  if i>=len(q):
   for z in ["fav","adv","close","open"]:
    out[f"b{n}_{z}"]=np.nan
   continue
  z=q.iloc[i]
  out[f"b{n}_fav"]=fav.iloc[i]
  out[f"b{n}_adv"]=adv.iloc[i]
  out[f"b{n}_close"]=(z.close/e-1 if side=="LONG" else 1-z.close/e)
  out[f"b{n}_open"]=(z.open/e-1 if side=="LONG" else 1-z.open/e)

 out["max_fav6"]=fav.max()
 out["max_adv6"]=adv.min()

 # premier retour à >= 0% sur close
 close=out.get("b1_close",np.nan)
 out["be_bar"]=np.nan
 for i in range(BARS):
  v=out.get(f"b{i+1}_close",np.nan)
  if pd.notna(v) and v>=0:
   out["be_bar"]=i+1;break

 # entrées contrefactuelles à B1/B2 OPEN
 for lag in [1,2]:
  if lag<=len(q):
   ee=float(q.iloc[lag-1].open)
   if side=="LONG":
    f=(q.iloc[lag-1:]["high"]/ee-1).max()
    a=(q.iloc[lag-1:]["low"]/ee-1).min()
   else:
    f=(1-q.iloc[lag-1:]["low"]/ee).max()
    a=(q.iloc[lag-1:]["high"]/ee-1).min()
   out[f"delay{lag}_fav6"]=f
   out[f"delay{lag}_adv6"]=a

 return out

x=pd.DataFrame([one(r) for _,r in d.iterrows()])
d=pd.concat([d.reset_index(drop=True),x],axis=1)

# Résumé global
g={
 "trades":len(d),
 "mean_net":d.net.mean(),
 "win":(d.net>0).mean(),
 "mean_fav6":d.max_fav6.mean(),
 "mean_adv6":d.max_adv6.mean(),
 "be_rate":d.be_bar.notna().mean()
}

# Barres 1-6
rows=[]
for n in range(1,BARS+1):
 rows.append({
  "bars":n,
  "fav_mean":d[f"b{n}_fav"].mean(),
  "adv_mean":d[f"b{n}_adv"].mean(),
  "close_mean":d[f"b{n}_close"].mean(),
  "fav_pos":(d[f"b{n}_fav"]>0).mean(),
  "adv_pos":(d[f"b{n}_adv"]<0).mean()
})
tim=pd.DataFrame(rows)

# Signal
sig=[]
for k,q in d.groupby("signal",observed=True):
 sig.append({
  "signal":k,"n":len(q),
  "fav6":q.max_fav6.mean(),
  "adv6":q.max_adv6.mean(),
  "net":q.net.mean(),
  "win":(q.net>0).mean(),
  "be":q.be_bar.notna().mean()
})
sig=pd.DataFrame(sig).sort_values("net",ascending=False)

# Marché
mk=[]
for (sym,it),q in d.groupby(["symbol","interval"],observed=True):
 mk.append({
  "symbol":sym,"interval":it,"n":len(q),
  "fav6":q.max_fav6.mean(),
  "adv6":q.max_adv6.mean(),
  "net":q.net.mean(),
  "win":(q.net>0).mean(),
  "be":q.be_bar.notna().mean()
 })
mk=pd.DataFrame(mk)

# Entrées décalées
delay=pd.DataFrame([{
 "mode":"original",
 "fav6":d.max_fav6.mean(),
 "adv6":d.max_adv6.mean()
},{
 "mode":"delay_1_open",
 "fav6":d.delay1_fav6.mean(),
 "adv6":d.delay1_adv6.mean()
},{
 "mode":"delay_2_open",
 "fav6":d.delay2_fav6.mean(),
 "adv6":d.delay2_adv6.mean()
}])

d.to_csv(O/"v411_entry_quality.csv",index=False)
tim.to_csv(O/"v411_timing.csv",index=False)
sig.to_csv(O/"v411_signal_quality.csv",index=False)
mk.to_csv(O/"v411_market_quality.csv",index=False)
delay.to_csv(O/"v411_delay.csv",index=False)

lines=[
"# SCALP LAB V4.11 — ENTRY QUALITY",
"",
f"Trades OOS : {len(d)}",
"Holdout : exclu",
"",
"## Global",
pd.DataFrame([g]).to_string(index=False),
"",
"## Bougies 1-6",
tim.to_string(index=False),
"",
"## Signal",
sig.to_string(index=False),
"",
"## Marché",
mk.to_string(index=False),
"",
"## Entrée originale vs décalée",
delay.to_string(index=False),
"",
"## Méthode",
"- OOS uniquement.",
"- V4.4 inchangée.",
"- OHLC Binance Futures.",
"- B1 = première bougie suivant l'entrée.",
"- fav/adv = excursion intrabougie depuis le prix d'entrée.",
"- delay_1/2 = analyse contrefactuelle, pas nouveau backtest.",
"- Aucune information future utilisée pour modifier les trades."
]

(O/"summary_v411.md").write_text("\n".join(lines),encoding="utf-8")

print("===== V4.11 =====")
print(pd.DataFrame([g]).to_string(index=False))
print("\nTIMING")
print(tim.to_string(index=False))
print("\nSIGNAL")
print(sig.to_string(index=False))
print("\nMARKET")
print(mk.to_string(index=False))
print("\nDELAY")
print(delay.to_string(index=False))
print("\nV4.11 TERMINÉ")
