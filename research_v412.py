from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests,time
import pandas as pd
import numpy as np

O=Path("results"); SRC=O/"v44_trades_oos.csv"
BASES=[
 "https://fapi.binance.com/fapi/v1/klines",
 "https://www.binance.com/fapi/v1/klines",
 "https://data-api.binance.vision/fapi/v1/klines"
]
MAX=1500; WORKERS=6; ATR_N=14; WARM=40; FEE=.0005
SLIP={"BTCUSDT":.00010,"ETHUSDT":.00015,"SOLUSDT":.00030}

d=pd.read_csv(SRC)
need=["symbol","interval","entry_time","side","entry_price",
      "tp_price","sl_price","tp_mult","sl_mult","hold","net"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","sl_price","tp_mult","sl_mult","hold","net"]:
 d[c]=pd.to_numeric(d[c],errors="coerce")
d.entry_time=pd.to_datetime(d.entry_time,utc=True)

def ms(it): return {"5m":300000,"15m":900000}[it]

def fetch(k):
 sym,it=k
 x=d[(d.symbol==sym)&(d.interval==it)]
 st=x.entry_time.min()-pd.Timedelta(ms(it)*WARM,unit="ms")
 en=x.entry_time.max()+pd.Timedelta(ms(it)*50,unit="ms")
 cur=int(st.timestamp()*1000); end=int(en.timestamp()*1000)

 for base in BASES:
  try:
   rows=[]; s=requests.Session()
   while cur<end:
    for z in range(4):
     try:
      r=s.get(base,params={
       "symbol":sym,"interval":it,
       "startTime":cur,"endTime":end,"limit":MAX
      },timeout=30)
      if r.status_code==200:
       a=r.json(); break
      if r.status_code in (418,429,500,502,503,504):
       time.sleep(1+z); continue
      raise RuntimeError(f"HTTP {r.status_code}")
     except Exception:
      if z==3: raise
      time.sleep(1+z)
    if not a: break
    rows+=a
    nxt=a[-1][0]+ms(it)
    if nxt<=cur: break
    cur=nxt
    if len(a)<MAX: break

   if rows:
    q=pd.DataFrame(rows,columns=[
     "ts","open","high","low","close","vol",
     "close_ts","quote","trades","tb","tq","x"
    ]).drop_duplicates("ts")
    q.ts=pd.to_datetime(q.ts,unit="ms",utc=True)
    for c in ["open","high","low","close"]:
     q[c]=pd.to_numeric(q[c],errors="coerce")
    q=q.set_index("ts")[["open","high","low","close"]]

    tr=pd.concat([
     q.high-q.low,
     (q.high-q.close.shift()).abs(),
     (q.low-q.close.shift()).abs()
    ],axis=1).max(axis=1)
    q["atr"]=tr.ewm(
     alpha=1/ATR_N,adjust=False,min_periods=ATR_N
    ).mean()

    print("DATA",sym,it,len(q),base)
    return k,q
  except Exception as e:
   print("FALLBACK",sym,it,base,e)

 raise RuntimeError(f"IMPOSSIBLE {sym} {it}")

data={}
keys=list(d.groupby(["symbol","interval"]).groups)

print("V4.12 | ENTRY REPLAY")
print("TRADES",len(d))

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
 fs=[ex.submit(fetch,k) for k in keys]
 for f in as_completed(fs):
  k,q=f.result(); data[k]=q

def replay(r,mode):
 q=data[(r.symbol,r.interval)]
 t=r.entry_time
 side=str(r.side).upper()
 slip=SLIP.get(str(r.symbol),.0002)

 if mode=="ORIGINAL":
  ts=t
  e=float(r.entry_price)
  tp=float(r.tp_price)
  sl=float(r.sl_price)
 else:
  future=q[q.index>t]
  lag=1 if mode=="B1_OPEN" else 2
  if len(future)<lag:return None

  row=future.iloc[lag-1]
  ts=future.index[lag-1]
  e=float(row.open)

  pos=q.index.get_loc(ts)
  if pos<1:return None
  atr=float(q.iloc[pos-1].atr)
  if not np.isfinite(atr) or atr<=0:return None

  tm=float(r.tp_mult); sm=float(r.sl_mult)

  if side=="LONG":
   tp=e+tm*atr; sl=e-sm*atr
  else:
   tp=e-tm*atr; sl=e+sm*atr

 if side=="LONG":
  ee=e*(1+slip)
  tp_exec=tp*(1-slip)
  sl_exec=sl*(1-slip)
 else:
  ee=e*(1-slip)
  tp_exec=tp*(1+slip)
  sl_exec=sl*(1+slip)

 hold=int(r.hold)
 future=q[q.index>=ts].iloc[:hold]
 if future.empty:return None

 reason="TIME"
 exit_price=float(future.iloc[-1].close)
 exit_bar=len(future)

 for i,(_,z) in enumerate(future.iterrows(),1):
  hi=float(z.high); lo=float(z.low)

  if side=="LONG":
   hit_sl=lo<=sl; hit_tp=hi>=tp
  else:
   hit_sl=hi>=sl; hit_tp=lo<=tp

  if hit_sl:
   reason="SL"; exit_price=sl_exec; exit_bar=i; break
  if hit_tp:
   reason="TP"; exit_price=tp_exec; exit_bar=i; break

 if reason=="TIME":
  xe=exit_price*(1-slip) if side=="LONG" else exit_price*(1+slip)
 else:
  xe=exit_price

 gross=xe/ee-1 if side=="LONG" else ee/xe-1
 net=gross-2*FEE

 return {
  "mode":mode,"symbol":r.symbol,"interval":r.interval,
  "fold":r.fold,"signal":r.signal,"regime":r.regime,
  "profile":r.profile,"side":side,"entry_time":ts,
  "entry_price":e,"tp":tp,"sl":sl,"exit_price":xe,
  "exit_reason":reason,"bars":exit_bar,
  "gross":gross,"net":net
 }

rows=[]
for _,r in d.iterrows():
 for mode in ["ORIGINAL","B1_OPEN","B2_OPEN"]:
  z=replay(r,mode)
  if z: rows.append(z)

x=pd.DataFrame(rows)
x.to_csv(O/"v412_entry_replay.csv",index=False)

def stats(q):
 q=q.copy()
 pos=q.loc[q.net>0,"net"].sum()
 neg=-q.loc[q.net<0,"net"].sum()
 pf=pos/neg if neg else np.nan
 eq=(1+q.net).cumprod()
 dd=eq/eq.cummax()-1

 return {
  "n":len(q),
  "mean_net":q.net.mean(),
  "median_net":q.net.median(),
  "win":(q.net>0).mean(),
  "pf":pf,
  "dd":dd.min(),
  "compound":eq.iloc[-1]-1,
  "TP":(q.exit_reason=="TP").sum(),
  "SL":(q.exit_reason=="SL").sum(),
  "TIME":(q.exit_reason=="TIME").sum()
 }

S=[]
for mode,q in x.groupby("mode",sort=False):
 z=stats(q); z["mode"]=mode; S.append(z)

S=pd.DataFrame(S)[[
 "mode","n","mean_net","median_net","win","pf",
 "dd","compound","TP","SL","TIME"
]]

# IMPORTANT : colonne explicite, pas S.mode
base=S[S["mode"]=="ORIGINAL"].iloc[0]

cmp=[]
for _,z in S.iterrows():
 cmp.append({
  "mode":z["mode"],
  "delta_mean":z.mean_net-base.mean_net,
  "delta_win":z.win-base.win,
  "delta_pf":z.pf-base.pf,
  "delta_dd":z.dd-base.dd
 })
cmp=pd.DataFrame(cmp)

S.to_csv(O/"v412_summary.csv",index=False)
cmp.to_csv(O/"v412_comparison.csv",index=False)

lines=[
"# SCALP LAB V4.12 — ENTRY REPLAY",
"",
"Trades OOS : 2196",
"Holdout : exclu",
"",
"## Comparaison",
S.to_string(index=False),
"",
"## Delta vs ORIGINAL",
cmp.to_string(index=False),
"",
"## Méthode",
"- ORIGINAL = entrée/prix V4.4.",
"- B1_OPEN = ouverture de la bougie suivante.",
"- B2_OPEN = ouverture de la deuxième bougie suivante.",
"- ATR14 Wilder recalculé à l'entrée.",
"- TP = tp_mult × ATR.",
"- SL = sl_mult × ATR.",
"- Même hold que V4.4.",
"- SL prioritaire en cas d'ambiguïté intrabar.",
"- Frais et slippage inclus.",
"- Signaux V4.4 conservés.",
"- Aucun nouveau signal sélectionné."
]

(O/"summary_v412.md").write_text("\n".join(lines),encoding="utf-8")

print("\n===== V4.12 =====")
print(S.to_string(index=False))
print("\n===== DELTA VS ORIGINAL =====")
print(cmp.to_string(index=False))
print("\nV4.12 TERMINÉ")
