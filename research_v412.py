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
ATR_N=14
WARM=40
FEE=0.0005
SLIP={"BTCUSDT":0.00010,"ETHUSDT":0.00015,"SOLUSDT":0.00030}

d=pd.read_csv(SRC)

need=["symbol","interval","entry_time","side","entry_price",
      "tp_price","sl_price","tp_mult","sl_mult","hold","net"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","sl_price","tp_mult","sl_mult","hold","net"]:
 d[c]=pd.to_numeric(d[c],errors="coerce")
d.entry_time=pd.to_datetime(d.entry_time,utc=True)

def ms(it):
 return {"5m":300000,"15m":900000}[it]

def fetch(k):
 sym,it=k
 x=d[(d.symbol==sym)&(d.interval==it)]
 s0=x.entry_time.min()-pd.Timedelta(ms(it)*WARM,unit="ms")
 s1=x.entry_time.max()+pd.Timedelta(ms(it)*50,unit="ms")
 cur=int(s0.timestamp()*1000)
 en=int(s1.timestamp()*1000)

 for base in BASES:
  try:
   rows=[];s=requests.Session()
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
    nxt=a[-1][0]+ms(it)
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

    tr=pd.concat([
     q.high-q.low,
     (q.high-q.close.shift()).abs(),
     (q.low-q.close.shift()).abs()
    ],axis=1).max(axis=1)

    q["atr"]=tr.ewm(
     alpha=1/ATR_N,
     adjust=False,
     min_periods=ATR_N
    ).mean()

    print("DATA",sym,it,len(q),base)
    return k,q

  except Exception as e:
   print("FALLBACK",sym,it,base,e)

 raise RuntimeError(f"IMPOSSIBLE {sym} {it}")

keys=list(d.groupby(["symbol","interval"]).groups)
data={}

print("V4.12 | ENTRY REPLAY")
print("TRADES",len(d))

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
 fs=[ex.submit(fetch,k) for k in keys]
 for f in as_completed(fs):
  k,q=f.result()
  data[k]=q

def replay(r,mode):
 q=data[(r.symbol,r.interval)]
 t=r.entry_time
 side=str(r.side).upper()
 sym=str(r.symbol)
 slip=SLIP.get(sym,0.0002)

 # Original = prix réel V4.4.
 # B1/B2 = ouvertures des bougies suivantes.
 if mode=="ORIGINAL":
  ts=t
  e=float(r.entry_price)
  atr=None
  tp=float(r.tp_price)
  sl=float(r.sl_price)
 else:
  future=q[q.index>t]
  lag=1 if mode=="B1_OPEN" else 2
  if len(future)<lag:return None

  row=future.iloc[lag-1]
  ts=future.index[lag-1]
  e=float(row.open)

  # ATR disponible à l'ouverture = ATR de la bougie précédente.
  pos=q.index.get_loc(ts)
  if pos<1:return None
  atr=float(q.iloc[pos-1].atr)

  if not np.isfinite(atr) or atr<=0:return None

  tm=float(r.tp_mult)
  sm=float(r.sl_mult)

  if side=="LONG":
   tp=e+tm*atr
   sl=e-sm*atr
  else:
   tp=e-tm*atr
   sl=e+sm*atr

 # frais + slippage conservés selon le modèle V4.1
 # Slippage appliqué à l'entrée/sortie dans le sens défavorable.
 if side=="LONG":
  ee=e*(1+slip)
 else:
  ee=e*(1-slip)

 # pour ORIGINAL on utilise directement les niveaux historiques.
 # Pour le replay, niveaux déjà calculés sur le prix d'entrée.
 if side=="LONG":
  tp_exec=tp*(1-slip)
  sl_exec=sl*(1-slip)
 else:
  tp_exec=tp*(1+slip)
  sl_exec=sl*(1+slip)

 hold=int(r.hold)
 future=q[q.index>=ts].iloc[:hold]

 if future.empty:return None

 exit_reason="TIME"
 exit_price=float(future.iloc[-1].close)
 exit_bar=hold

 for i,(idx,z) in enumerate(future.iterrows(),1):
  hi=float(z.high)
  lo=float(z.low)

  if side=="LONG":
   hit_sl=lo<=sl
   hit_tp=hi>=tp
  else:
   hit_sl=hi>=sl
   hit_tp=lo<=tp

  # Même convention que V4.1 : SL prioritaire.
  if hit_sl:
   exit_reason="SL"
   exit_price=sl_exec
   exit_bar=i
   break

  if hit_tp:
   exit_reason="TP"
   exit_price=tp_exec
   exit_bar=i
   break

 if exit_reason=="TIME":
  if side=="LONG":
   xe=exit_price*(1-slip)
  else:
   xe=exit_price*(1+slip)
 else:
  xe=exit_price

 # rendement brut puis frais entrée/sortie
 if side=="LONG":
  gross=xe/ee-1
 else:
  gross=ee/xe-1

 net=gross-2*FEE

 return {
  "mode":mode,
  "symbol":sym,
  "interval":r.interval,
  "fold":r.fold,
  "signal":r.signal,
  "regime":r.regime,
  "profile":r.profile,
  "side":side,
  "entry_time":ts,
  "entry_price":e,
  "tp":tp,
  "sl":sl,
  "exit_price":xe,
  "exit_reason":exit_reason,
  "bars":exit_bar,
  "gross":gross,
  "net":net
 }

rows=[]
for _,r in d.iterrows():
 for mode in ["ORIGINAL","B1_OPEN","B2_OPEN"]:
  z=replay(r,mode)
  if z:rows.append(z)

x=pd.DataFrame(rows)
x.to_csv(O/"v412_entry_replay.csv",index=False)

def stats(q):
 q=q.copy()
 wins=q.net>0
 pos=q.loc[q.net>0,"net"].sum()
 neg=-q.loc[q.net<0,"net"].sum()
 pf=pos/neg if neg else np.nan

 eq=(1+q.net).cumprod()
 peak=eq.cummax()
 dd=eq/peak-1

 return {
  "n":len(q),
  "mean_net":q.net.mean(),
  "median_net":q.net.median(),
  "win":wins.mean(),
  "pf":pf,
  "dd":dd.min(),
  "compound":eq.iloc[-1]-1,
  "TP":(q.exit_reason=="TP").sum(),
  "SL":(q.exit_reason=="SL").sum(),
  "TIME":(q.exit_reason=="TIME").sum()
 }

S=[]
for mode,q in x.groupby("mode",sort=False):
 z=stats(q)
 z["mode"]=mode
 S.append(z)

S=pd.DataFrame(S)[[
 "mode","n","mean_net","median_net","win",
 "pf","dd","compound","TP","SL","TIME"
]]

# comparaison directe B1/B2 contre ORIGINAL
base=S[S.mode=="ORIGINAL"].iloc[0]

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
"2196 trades OOS.",
"Holdout exclu.",
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
"- Analyse contrefactuelle : les signaux V4.4 restent fixes.",
"- Aucun nouveau signal n'est sélectionné."
]

(O/"summary_v412.md").write_text("\n".join(lines),encoding="utf-8")

print("\n===== V4.12 =====")
print(S.to_string(index=False))
print("\n===== DELTA VS ORIGINAL =====")
print(cmp.to_string(index=False))
print("\nV4.12 TERMINÉ")
