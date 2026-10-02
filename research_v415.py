from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
SRC=O/"v414_replay.csv"
x=pd.read_csv(SRC)
x=x[x.mode!="ORIGINAL"].copy()

print("V4.15 | B1 OOS STABILITY")
print("ROWS",len(x))

def st(q):
    if len(q)==0:return {"n":0,"mean":np.nan,"win":np.nan,"pf":np.nan}
    p=q.loc[q.net>0,"net"].sum(); n=-q.loc[q.net<0,"net"].sum()
    return {"n":len(q),"mean":q.net.mean(),
            "win":(q.net>0).mean(),"pf":p/n if n else np.nan}

# fold = temporal unit already present in V4.4 replay
# We compare each B1 filter to the ORIGINAL trade universe
# on the same fold/market/signal/regime.
orig=pd.read_csv(O/"v44_trades_oos.csv")

keys=["fold","symbol","interval","signal","regime","profile"]

# ORIGINAL reference reconstructed from V4.14
o=pd.read_csv(SRC)
o=o[o.mode=="ORIGINAL"].copy()

# fold-level global stability
rows=[]
for fold,q in x.groupby("fold"):
    for mode,z in q.groupby("mode"):
        a=st(z)
        oo=o[o.fold==fold]
        b=st(oo)
        a.update({"fold":fold,"mode":mode,
                  "delta_mean":a["mean"]-b["mean"],
                  "delta_win":a["win"]-b["win"],
                  "delta_pf":a["pf"]-b["pf"]})
        rows.append(a)

F=pd.DataFrame(rows)
F.to_csv(O/"v415_fold.csv",index=False)

# market / interval
rows=[]
for (mode,sym,it),q in x.groupby(["mode","symbol","interval"]):
    a=st(q)
    oo=o[(o.symbol==sym)&(o.interval==it)]
    b=st(oo)
    a.update({"mode":mode,"symbol":sym,"interval":it,
              "delta_mean":a["mean"]-b["mean"],
              "delta_win":a["win"]-b["win"],
              "delta_pf":a["pf"]-b["pf"]})
    rows.append(a)
M=pd.DataFrame(rows)
M.to_csv(O/"v415_market.csv",index=False)

# signal
rows=[]
for (mode,sig),q in x.groupby(["mode","signal"]):
    a=st(q)
    oo=o[o.signal==sig]
    b=st(oo)
    a.update({"mode":mode,"signal":sig,
              "delta_mean":a["mean"]-b["mean"],
              "delta_win":a["win"]-b["win"],
              "delta_pf":a["pf"]-b["pf"]})
    rows.append(a)
S=pd.DataFrame(rows)
S.to_csv(O/"v415_signal.csv",index=False)

# regime
rows=[]
for (mode,reg),q in x.groupby(["mode","regime"]):
    a=st(q)
    oo=o[o.regime==reg]
    b=st(oo)
    a.update({"mode":mode,"regime":reg,
              "delta_mean":a["mean"]-b["mean"],
              "delta_win":a["win"]-b["win"],
              "delta_pf":a["pf"]-b["pf"]})
    rows.append(a)
R=pd.DataFrame(rows)
R.to_csv(O/"v415_regime.csv",index=False)

# stability by fold: positive delta and positive absolute mean
stab=[]
for mode,q in F.groupby("mode"):
    stab.append({
        "mode":mode,
        "folds":len(q),
        "delta_mean_avg":q.delta_mean.mean(),
        "delta_mean_median":q.delta_mean.median(),
        "delta_mean_positive_folds":(q.delta_mean>0).sum(),
        "delta_pf_positive_folds":(q.delta_pf>0).sum(),
        "absolute_positive_folds":(q["mean"]>0).sum(),
        "mean_positive_pct":(q["mean"]>0).mean()
    })
T=pd.DataFrame(stab)
T.to_csv(O/"v415_stability.csv",index=False)

# Do not rank a winner: report stability only.
out=[
"# SCALP LAB V4.15 — B1 OOS STABILITY",
"",
"Trades: V4.14 replayable OOS universe",
"Holdout: excluded",
"",
"## STABILITY BY FOLD",
T.to_string(index=False),
"",
"## FOLD DETAILS",
F.to_string(index=False),
"",
"## MARKET / INTERVAL",
M.to_string(index=False),
"",
"## SIGNAL",
S.to_string(index=False),
"",
"## REGIME",
R.to_string(index=False),
"",
"## RULES",
"- No new signal.",
"- No holdout selection.",
"- ORIGINAL is the V4.4 entry reference.",
"- B1 filters use only B1 opening price and pre-B1 ATR.",
"- Same exits, fees and slippage.",
"- Positive fold count is descriptive, not a ranking.",
"- A filter is considered more stable only if its effect persists across folds."
]
(O/"summary_v415.md").write_text("\n".join(out),encoding="utf-8")

print("\n===== STABILITY =====")
print(T.to_string(index=False))
print("\nV4.15 TERMINÉ")
