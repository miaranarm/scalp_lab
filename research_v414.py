from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests,time
import pandas as pd
import numpy as np

O=Path("results"); SRC=O/"v44_trades_oos.csv"
BASES=[
 "https://fapi.binance.com/fapi/v1/klines",
 "https://www.binance.com/fapi/v1/klines",
 "https://data-api.binance.vision/fapi/v1/klines"]
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

def ms(x): return {"5m":300000,"15m":900000}[x]

def fetch(k):
    sym,it=k
    z=d[(d.symbol==sym)&(d.interval==it)]
    st=z.entry_time.min()-pd.Timedelta(ms(it)*WARM,unit="ms")
    en=z.entry_time.max()+pd.Timedelta(ms(it)*50,unit="ms")
    s0=int(st.timestamp()*1000); end=int(en.timestamp()*1000)

    for base in BASES:
        try:
            cur=s0; rows=[]; s=requests.Session()
            while cur<end:
                for n in range(4):
                    try:
                        r=s.get(base,params={
                            "symbol":sym,"interval":it,
                            "startTime":cur,"endTime":end,"limit":MAX},
                            timeout=30)
                        if r.status_code==200:
                            a=r.json(); break
                        if r.status_code in (418,429,500,502,503,504):
                            time.sleep(1+n); continue
                        raise RuntimeError(f"HTTP {r.status_code}")
                    except Exception:
                        if n==3: raise
                        time.sleep(1+n)
                if not a: break
                rows+=a; nxt=a[-1][0]+ms(it)
                if nxt<=cur: break
                cur=nxt
                if len(a)<MAX: break

            if not rows: continue
            q=pd.DataFrame(rows,columns=[
                "ts","open","high","low","close","vol","close_ts",
                "quote","trades","tb","tq","x"]).drop_duplicates("ts")
            q.ts=pd.to_datetime(q.ts,unit="ms",utc=True)
            for c in ["open","high","low","close"]:
                q[c]=pd.to_numeric(q[c],errors="coerce")
            q=q.set_index("ts")[["open","high","low","close"]]
            tr=pd.concat([
                q.high-q.low,
                (q.high-q.close.shift()).abs(),
                (q.low-q.close.shift()).abs()],axis=1).max(axis=1)
            q["atr"]=tr.ewm(alpha=1/ATR_N,adjust=False,
                            min_periods=ATR_N).mean()
            print("DATA",sym,it,len(q),base)
            return k,q
        except Exception as e:
            print("FALLBACK",sym,it,base,e)
    raise RuntimeError(f"IMPOSSIBLE {sym} {it}")

print("V4.14 | B1 FILTER STABILITY")
print("TRADES",len(d))

data={}
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    fs=[ex.submit(fetch,k) for k in d.groupby(["symbol","interval"]).groups]
    for f in as_completed(fs):
        k,q=f.result(); data[k]=q

# None = B1_ALL ; 0/.10/.25/.50 = maximum allowed adverse gap in ATR.
MODES={"ORIGINAL":None,"B1_ALL":None,
       "GAP0":0.0,"GAP10":-.10,"GAP25":-.25,"GAP50":-.50}

def replay(r,mode):
    q=data[(r.symbol,r.interval)]
    t=r.entry_time; side=str(r.side).upper()
    slip=SLIP.get(str(r.symbol),.0002)

    if mode=="ORIGINAL":
        ts=t; e=float(r.entry_price)
        tp=float(r.tp_price); sl=float(r.sl_price)
    else:
        f=q[q.index>t]
        if f.empty:return None
        row=f.iloc[0]; ts=f.index[0]; e=float(row.open)
        p=q.index.get_loc(ts)
        if p<1:return None
        atr=float(q.iloc[p-1].atr)
        if not np.isfinite(atr) or atr<=0:return None

        old=float(r.entry_price)
        gap=(e-old)/atr if side=="LONG" else (old-e)/atr

        if mode!="B1_ALL" and gap<MODES[mode]: return None

        tm=float(r.tp_mult); sm=float(r.sl_mult)
        if side=="LONG": tp=e+tm*atr; sl=e-sm*atr
        else: tp=e-tm*atr; sl=e+sm*atr

    ee=e*(1+slip) if side=="LONG" else e*(1-slip)
    tp_x=tp*(1-slip) if side=="LONG" else tp*(1+slip)
    sl_x=sl*(1-slip) if side=="LONG" else sl*(1+slip)

    fut=q[q.index>=ts].iloc[:int(r.hold)]
    if fut.empty:return None

    reason="TIME"; xp=float(fut.iloc[-1].close); bars=len(fut)
    for i,(_,z) in enumerate(fut.iterrows(),1):
        hi=float(z.high); lo=float(z.low)
        hs=lo<=sl if side=="LONG" else hi>=sl
        ht=hi>=tp if side=="LONG" else lo<=tp
        if hs:
            reason="SL"; xp=sl_x; bars=i; break
        if ht:
            reason="TP"; xp=tp_x; bars=i; break

    xe=xp*(1-slip) if reason=="TIME" and side=="LONG" else xp
    xe=xp*(1+slip) if reason=="TIME" and side=="SHORT" else xe
    gross=xe/ee-1 if side=="LONG" else ee/xe-1
    net=gross-2*FEE

    return {
        "mode":mode,"symbol":r.symbol,"interval":r.interval,
        "fold":r.fold,"signal":r.signal,"regime":r.regime,
        "profile":r.profile,"side":side,"net":net,
        "reason":reason,"bars":bars}

rows=[]
for _,r in d.iterrows():
    for mode in MODES:
        z=replay(r,mode)
        if z: rows.append(z)

x=pd.DataFrame(rows)
x.to_csv(O/"v414_replay.csv",index=False)

def stats(q):
    p=q.loc[q.net>0,"net"].sum()
    n=-q.loc[q.net<0,"net"].sum()
    pf=p/n if n else np.nan
    eq=(1+q.net).cumprod()
    return {
        "n":len(q),"mean":q.net.mean(),"median":q.net.median(),
        "win":(q.net>0).mean(),"pf":pf,
        "dd":(eq/eq.cummax()-1).min(),
        "TP":(q.reason=="TP").sum(),
        "SL":(q.reason=="SL").sum(),
        "TIME":(q.reason=="TIME").sum()}

def table(group_cols):
    a=[]
    for key,q in x.groupby(group_cols,dropna=False):
        z=stats(q)
        if not isinstance(key,tuple): key=(key,)
        z.update(dict(zip(group_cols,key))); a.append(z)
    return pd.DataFrame(a)

S=table(["mode"])
S=S[["mode","n","mean","median","win","pf","dd","TP","SL","TIME"]]

base=S[S["mode"]=="ORIGINAL"].iloc[0]
D=S.copy()
D["delta_mean"]=D["mean"]-base["mean"]
D["delta_win"]=D["win"]-base["win"]
D["delta_pf"]=D["pf"]-base["pf"]
D["delta_dd"]=D["dd"]-base["dd"]

detail=[]
for cols,name in [
    (["mode","symbol","interval"],"market"),
    (["mode","signal"],"signal"),
    (["mode","regime"],"regime")]:
    q=table(cols)
    q.to_csv(O/f"v414_{name}.csv",index=False)
    detail.append((name,q))

S.to_csv(O/"v414_summary.csv",index=False)
D.to_csv(O/"v414_comparison.csv",index=False)

out=[
"# SCALP LAB V4.14 — B1 FILTER STABILITY","",
f"Trades OOS : {len(d)}","Holdout : exclu","",
"## Global",S.to_string(index=False),"",
"## Delta vs ORIGINAL",D.to_string(index=False),""
]

for name,q in detail:
    out += [f"## {name.upper()}",q.to_string(index=False),""]

out += [
"## Méthode",
"- ORIGINAL = entrée V4.4.",
"- B1_ALL = ouverture B1 sans filtre.",
"- GAP0 = gap >= 0 ATR.",
"- GAP10 = gap >= -0.10 ATR.",
"- GAP25 = gap >= -0.25 ATR.",
"- GAP50 = gap >= -0.50 ATR.",
"- Le gap utilise uniquement le prix d'ouverture B1 et l'ATR disponible avant B1.",
"- Aucun nouveau signal.",
"- Même TP/SL/hold/frais/slippage que V4.4.",
"- SL prioritaire en ambiguïté intrabar.",
"- Holdout non utilisé."
]

(O/"summary_v414.md").write_text("\n".join(out),encoding="utf-8")

print("\n===== V4.14 =====")
print(S.to_string(index=False))
print("\n===== DELTA =====")
print(D.to_string(index=False))
print("\nV4.14 TERMINÉ")
