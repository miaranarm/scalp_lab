import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
import numpy as np

OUT=Path("results")
SRC=OUT/"v44_trades_oos.csv"
BASES=[
    "https://fapi.binance.com/fapi/v1/klines",
    "https://www.binance.com/fapi/v1/klines",
    "https://data-api.binance.vision/fapi/v1/klines",
]
MAX=1500
WORKERS=6

d=pd.read_csv(SRC)

need=["symbol","interval","entry_time","exit_time","side",
      "entry_price","tp_price","sl_price","exit_reason","net","mfe","mae"]
miss=[c for c in need if c not in d]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","sl_price","net","mfe","mae"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

d.entry_time=pd.to_datetime(d.entry_time,utc=True)
d.exit_time=pd.to_datetime(d.exit_time,utc=True)

def ims(x):
    return {"5m":300000,"15m":900000}[x]

def fetch_one(key):
    symbol,interval=key
    x=d[(d.symbol==symbol)&(d.interval==interval)]
    start=int(x.entry_time.min().timestamp()*1000)
    end=int(x.exit_time.max().timestamp()*1000)+ims(interval)

    for base in BASES:
        try:
            rows=[]
            cur=start
            s=requests.Session()

            while cur<end:
                ok=False

                for z in range(4):
                    try:
                        r=s.get(
                            base,
                            params={
                                "symbol":symbol,
                                "interval":interval,
                                "startTime":cur,
                                "endTime":end,
                                "limit":MAX
                            },
                            timeout=30
                        )

                        if r.status_code==200:
                            a=r.json()
                            ok=True
                            break

                        if r.status_code in (418,429,500,502,503,504):
                            time.sleep(2+z*2)
                            continue

                        raise RuntimeError(
                            f"HTTP {r.status_code}"
                        )

                    except Exception:
                        if z==3: raise
                        time.sleep(2+z*2)

                if not ok or not a:
                    break

                rows.extend(a)
                nxt=a[-1][0]+ims(interval)

                if nxt<=cur:
                    break

                cur=nxt

                if len(a)<MAX:
                    break

            if rows:
                q=pd.DataFrame(rows,columns=[
                    "ts","open","high","low","close","vol",
                    "close_ts","quote","trades","tb","tq","x"
                ])
                q=q.drop_duplicates("ts")
                q.ts=pd.to_datetime(q.ts,unit="ms",utc=True)

                for c in ["open","high","low","close"]:
                    q[c]=pd.to_numeric(q[c])

                q=q.set_index("ts")[["open","high","low","close"]]

                print("DATA",symbol,interval,len(q),base)
                return key,q

        except Exception as e:
            print("FALLBACK",symbol,interval,base,e)

    raise RuntimeError(
        f"IMPOSSIBLE {symbol} {interval}: tous les endpoints ont échoué"
    )

keys=list(d.groupby(["symbol","interval"]).groups)
data={}

print("V4.8 | PATH FORENSICS")
print("TRADES",len(d))
print("DATASETS",len(keys))

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    fs=[ex.submit(fetch_one,k) for k in keys]

    for f in as_completed(fs):
        k,q=f.result()
        data[k]=q

def path(row):
    q=data[(row.symbol,row.interval)]
    q=q[(q.index>=row.entry_time)&(q.index<=row.exit_time)]

    if q.empty:
        return {}

    side=str(row.side).upper()
    e=float(row.entry_price)
    tp=float(row.tp_price)
    sl=float(row.sl_price)

    if side=="LONG":
        tpdist=tp/e-1
        sldist=1-sl/e
    else:
        tpdist=1-tp/e
        sldist=sl/e-1

    lev={
        "tp50":tpdist*.5,
        "tp75":tpdist*.75,
        "tp100":tpdist,
        "sl50":sldist*.5,
        "sl75":sldist*.75,
        "sl100":sldist
    }

    out={}

    for n in lev:
        out[n+"_time"]=pd.NaT
        out[n+"_bar"]=np.nan

    for i,(ts,r) in enumerate(q.iterrows()):
        if side=="LONG":
            fav=r.high/e-1
            adv=1-r.low/e
        else:
            fav=1-r.low/e
            adv=r.high/e-1

        for n in ["tp50","tp75","tp100"]:
            if pd.isna(out[n+"_time"]) and fav>=lev[n]:
                out[n+"_time"]=ts
                out[n+"_bar"]=i

        for n in ["sl50","sl75","sl100"]:
            if pd.isna(out[n+"_time"]) and adv>=lev[n]:
                out[n+"_time"]=ts
                out[n+"_bar"]=i

    out["path_bars"]=len(q)

    def first(names):
        a=[out[n+"_bar"] for n in names
           if pd.notna(out[n+"_bar"])]
        return min(a) if a else np.nan

    out["first_favorable_bar"]=first(["tp50","tp75","tp100"])
    out["first_adverse_bar"]=first(["sl50","sl75","sl100"])

    return out

rows=[path(r) for _,r in d.iterrows()]
d=pd.concat([d.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

for c in ["tp50_time","tp75_time","tp100_time",
          "sl50_time","sl75_time","sl100_time"]:
    d[c]=pd.to_datetime(d[c],utc=True,errors="coerce")

d["tp50_before_sl50"]=(d.tp50_time.notna()&
    (d.sl50_time.isna()|(d.tp50_time<d.sl50_time)))

d["tp75_before_sl50"]=(d.tp75_time.notna()&
    (d.sl50_time.isna()|(d.tp75_time<d.sl50_time)))

d["tp100_before_sl50"]=(d.tp100_time.notna()&
    (d.sl50_time.isna()|(d.tp100_time<d.sl50_time)))

d["sl50_before_tp50"]=(d.sl50_time.notna()&
    (d.tp50_time.isna()|(d.sl50_time<d.tp50_time)))

d["path_class"]=np.select([
    d.tp50_before_sl50&d.tp75_before_sl50,
    d.tp50_before_sl50,
    d.sl50_before_tp50,
    d.tp50_time.notna()&d.sl50_time.notna()
],[
    "FAVORABLE_PATH",
    "EARLY_FAVORABLE",
    "EARLY_ADVERSE",
    "AMBIGUOUS_PATH"
],"NO_TOUCH")

for n in ["tp50","tp75","tp100","sl50","sl75","sl100"]:
    d["bars_to_"+n]=d[n+"_bar"]

d.to_csv(OUT/"v48_trade_paths.csv",index=False)

def agg(cols,file):
    x=d.groupby(cols,observed=True).agg(
        n=("net","size"),
        mean_net=("net","mean"),
        win=("net",lambda x:(x>0).mean()),
        mean_mfe=("mfe","mean"),
        mean_mae=("mae","mean"),
        tp50=("tp50_time","count"),
        tp75=("tp75_time","count"),
        tp100=("tp100_time","count"),
        sl50=("sl50_time","count"),
        sl75=("sl75_time","count"),
        sl100=("sl100_time","count")
    ).reset_index()
    x.to_csv(OUT/file,index=False)

agg(["path_class"],"v48_path_class.csv")
agg(["exit_reason","path_class"],"v48_exit_path.csv")
agg(["signal","path_class"],"v48_signal_path.csv")
agg(["symbol","interval","path_class"],"v48_market_path.csv")

g=pd.DataFrame([{
    "trades":len(d),
    "tp50":d.tp50_time.notna().sum(),
    "tp75":d.tp75_time.notna().sum(),
    "tp100":d.tp100_time.notna().sum(),
    "sl50":d.sl50_time.notna().sum(),
    "sl75":d.sl75_time.notna().sum(),
    "sl100":d.sl100_time.notna().sum(),
    "tp50_before_sl50":d.tp50_before_sl50.sum(),
    "tp75_before_sl50":d.tp75_before_sl50.sum(),
    "tp100_before_sl50":d.tp100_before_sl50.sum(),
    "sl50_before_tp50":d.sl50_before_tp50.sum()
}])

g.to_csv(OUT/"v48_global.csv",index=False)

def pct(n):
    return f"{n/len(d):.2%}"

lines=[
"# SCALP LAB V4.8 — TRADE PATH FORENSICS","",
f"- Trades OOS : {len(d)}",
"- FINAL HOLDOUT : exclu",
"- Source : V4.4 trade-level + Binance Futures OHLC",
"- Stratégie V4.4 : inchangée","",
"## Touches","",
f"- TP 50% : {d.tp50_time.notna().sum()} ({pct(d.tp50_time.notna().sum())})",
f"- TP 75% : {d.tp75_time.notna().sum()} ({pct(d.tp75_time.notna().sum())})",
f"- TP 100% : {d.tp100_time.notna().sum()} ({pct(d.tp100_time.notna().sum())})",
f"- SL 50% : {d.sl50_time.notna().sum()} ({pct(d.sl50_time.notna().sum())})",
f"- SL 75% : {d.sl75_time.notna().sum()} ({pct(d.sl75_time.notna().sum())})",
f"- SL 100% : {d.sl100_time.notna().sum()} ({pct(d.sl100_time.notna().sum())})","",
"## Ordre du chemin","",
f"- TP50 avant SL50 : {d.tp50_before_sl50.sum()}",
f"- TP75 avant SL50 : {d.tp75_before_sl50.sum()}",
f"- TP100 avant SL50 : {d.tp100_before_sl50.sum()}",
f"- SL50 avant TP50 : {d.sl50_before_tp50.sum()}","",
"## Classes","",
d.path_class.value_counts().to_string(),"",
"## Méthode","",
"- Aucun signal ou paramètre modifié.",
"- Niveaux identiques à V4.4.",
"- Analyse OOS uniquement.",
"- Une même bougie peut toucher TP et SL.",
"- L'ordre intrabougie reste inconnu."
]

(OUT/"summary_v48.md").write_text(
    "\n".join(lines),encoding="utf-8"
)

print("===== V4.8 =====")
print("TRADES",len(d))
print("TP50",d.tp50_time.notna().sum())
print("TP75",d.tp75_time.notna().sum())
print("TP100",d.tp100_time.notna().sum())
print("SL50",d.sl50_time.notna().sum())
print("SL75",d.sl75_time.notna().sum())
print("SL100",d.sl100_time.notna().sum())
print("TP50_BEFORE_SL50",d.tp50_before_sl50.sum())
print("SL50_BEFORE_TP50",d.sl50_before_tp50.sum())
print("V4.8 TERMINÉ")
