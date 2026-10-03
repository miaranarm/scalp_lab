from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
T=O/"v44_trades_oos.csv"
R=O/"v414_replay.csv"

print("V4.17 | TRUE SURVIVORSHIP AUDIT")

o=pd.read_csv(T)
r=pd.read_csv(R)

K=["symbol","interval","fold","signal","regime","profile","side"]

for c in K+["entry_time"]:
    if c not in o: raise SystemExit("v44 COLONNE ABSENTE: "+c)
for c in ["mode","net"]+K:
    if c not in r: raise SystemExit("v414 COLONNE ABSENTE: "+c)

o["entry_time"]=pd.to_datetime(o["entry_time"],utc=True,errors="coerce")
if o.entry_time.isna().any():
    raise SystemExit("entry_time invalide")

o["_rank"]=o.groupby(K).cumcount()
o["trade_id"]=[f"T{i:05d}" for i in range(len(o))]

orig=r[r["mode"]=="ORIGINAL"].copy()
orig["_rank"]=orig.groupby(K).cumcount()

orig=orig.merge(
    o[K+["_rank","trade_id","entry_time"]],
    on=K+["_rank"],how="left",validate="one_to_one"
)

if orig.trade_id.isna().any():
    raise SystemExit("ORIGINAL non apparié")

orig=orig[["trade_id"]+K+["entry_time","net"]].rename(
    columns={"net":"original_net"}
)

print("ORIGINAL",len(orig))

MODES=["B1_ALL","GAP0","GAP10","GAP25","GAP50"]
all_rows=[]

for mode in MODES:
    q=r[r["mode"]==mode].copy()
    q["_rank"]=q.groupby(K).cumcount()

    q=q.merge(
        o[K+["_rank","trade_id"]],
        on=K+["_rank"],how="left",
        validate="many_to_one"
    )

    if q.trade_id.isna().any():
        raise SystemExit(f"{mode}: trade non apparié")

    q=q.merge(
        orig[["trade_id","original_net"]],
        on="trade_id",how="left",
        validate="one_to_one"
    )
    q["mode"]=mode
    all_rows.append(q)

b=pd.concat(all_rows,ignore_index=True)

def base_group(mask):
    return orig[mask].copy()

# ---------- GLOBAL ----------
rows=[]

for mode,q in b.groupby("mode"):
    ids=set(q.trade_id)
    rr=orig[orig.trade_id.isin(ids)]
    xx=orig[~orig.trade_id.isin(ids)]
    rb=q

    n=len(orig)

    sel=(rr.original_net.sum()-orig.original_net.sum())/n
    ent=(rb.net.sum()-rr.original_net.sum())/n

    rows.append({
        "mode":mode,
        "original_n":n,
        "retained_n":len(rr),
        "excluded_n":len(xx),
        "retained_pct":len(rr)/n,
        "excluded_pct":len(xx)/n,
        "all_original_mean":orig.original_net.mean(),
        "retained_original_mean":rr.original_net.mean(),
        "excluded_original_mean":xx.original_net.mean(),
        "retained_b1_mean":rb.net.mean(),
        "selection_contribution":sel,
        "entry_contribution":ent,
        "total_contribution":sel+ent,
        "excluded_win":(xx.original_net>0).mean(),
        "excluded_loss_pct":(xx.original_net<0).mean(),
        "retained_original_win":(rr.original_net>0).mean(),
        "retained_b1_win":(rb.net>0).mean()
    })

A=pd.DataFrame(rows)
A.to_csv(O/"v417_survivorship.csv",index=False)

# ---------- FOLD ----------
rows=[]

for (mode,fold),q in b.groupby(["mode","fold"]):
    ids=set(q.trade_id)
    rr=orig[(orig.fold==fold)&orig.trade_id.isin(ids)]
    base=orig[orig.fold==fold]
    xx=base[~base.trade_id.isin(ids)]

    rows.append({
        "mode":mode,
        "fold":fold,
        "original_n":len(base),
        "retained_n":len(rr),
        "excluded_n":len(xx),
        "retained_pct":len(rr)/len(base),
        "original_mean":base.original_net.mean(),
        "retained_original_mean":rr.original_net.mean(),
        "excluded_original_mean":
            xx.original_net.mean() if len(xx) else np.nan,
        "b1_mean":q.net.mean(),
        "selection_contribution":
            (rr.original_net.sum()-base.original_net.sum())/len(base),
        "entry_contribution":
            (q.net.sum()-rr.original_net.sum())/len(base)
    })

F=pd.DataFrame(rows)
F.to_csv(O/"v417_fold.csv",index=False)

# ---------- MARKET ----------
rows=[]

for (mode,sym,it),q in b.groupby(
    ["mode","symbol","interval"]
):
    ids=set(q.trade_id)
    base=orig[
        (orig.symbol==sym)&
        (orig.interval==it)
    ]
    rr=base[base.trade_id.isin(ids)]
    xx=base[~base.trade_id.isin(ids)]

    rows.append({
        "mode":mode,
        "symbol":sym,
        "interval":it,
        "original_n":len(base),
        "retained_n":len(rr),
        "excluded_n":len(xx),
        "retained_pct":len(rr)/len(base),
        "original_mean":base.original_net.mean(),
        "retained_original_mean":rr.original_net.mean(),
        "excluded_original_mean":
            xx.original_net.mean() if len(xx) else np.nan,
        "b1_mean":q.net.mean(),
        "selection_contribution":
            (rr.original_net.sum()-base.original_net.sum())/len(base),
        "entry_contribution":
            (q.net.sum()-rr.original_net.sum())/len(base)
    })

M=pd.DataFrame(rows)
M.to_csv(O/"v417_market.csv",index=False)

# ---------- SIGNAL / REGIME ----------
def table(cols,name):
    rows=[]

    for key,q in b.groupby(cols):
        if not isinstance(key,tuple):
            key=(key,)

        mask=np.ones(len(orig),dtype=bool)
        for c,v in zip(cols,key):
            mask &= orig[c].eq(v)

        base=orig[mask]
        ids=set(q.trade_id)
        rr=base[base.trade_id.isin(ids)]
        xx=base[~base.trade_id.isin(ids)]

        z={
            "original_n":len(base),
            "retained_n":len(rr),
            "excluded_n":len(xx),
            "retained_pct":
                len(rr)/len(base) if len(base) else np.nan,
            "original_mean":base.original_net.mean(),
            "retained_original_mean":rr.original_net.mean(),
            "excluded_original_mean":
                xx.original_net.mean() if len(xx) else np.nan,
            "b1_mean":q.net.mean(),
            "selection_contribution":
                (rr.original_net.sum()-base.original_net.sum())/len(base)
                if len(base) else np.nan,
            "entry_contribution":
                (q.net.sum()-rr.original_net.sum())/len(base)
                if len(base) else np.nan
        }

        z.update(dict(zip(cols,key)))
        rows.append(z)

    z=pd.DataFrame(rows)
    z.to_csv(O/f"v417_{name}.csv",index=False)
    return z

S=table(["mode","signal"],"signal")
G=table(["mode","regime"],"regime")

# ---------- TRADE AUDIT ----------
audit=[]

for mode,q in b.groupby("mode"):
    qm=q.set_index("trade_id")

    for _,z in orig.iterrows():
        tid=z.trade_id

        if tid in qm.index:
            h=qm.loc[tid]
            b1=float(h.net)
            status="RETAINED"
            delta=b1-float(z.original_net)
        else:
            b1=np.nan
            status="EXCLUDED"
            delta=np.nan

        audit.append({
            "trade_id":tid,
            "mode":mode,
            "symbol":z.symbol,
            "interval":z.interval,
            "fold":z.fold,
            "signal":z.signal,
            "regime":z.regime,
            "profile":z.profile,
            "side":z.side,
            "entry_time":z.entry_time,
            "original_net":z.original_net,
            "status":status,
            "b1_net":b1,
            "delta_net":delta
        })

AD=pd.DataFrame(audit)
AD.to_csv(O/"v417_trade_audit.csv",index=False)

# ---------- SUMMARY ----------
out=[
"# SCALP LAB V4.17 — TRUE SURVIVORSHIP AUDIT",
"",
f"Original trades : {len(orig)}",
"Holdout : exclu",
"",
"## GLOBAL",
A.to_string(index=False),
"",
"## FOLD",
F.to_string(index=False),
"",
"## MARKET / INTERVAL",
M.to_string(index=False),
"",
"## SIGNAL",
S.to_string(index=False),
"",
"## REGIME",
G.to_string(index=False),
"",
"## METHODE",
"- selection_contribution = effet du rejet des trades.",
"- entry_contribution = effet du changement d'entrée B1.",
"- total_contribution = selection + entry.",
"- EXCLUDED = trade rejeté par le filtre.",
"- RETAINED = trade conservé.",
"- Aucun nouveau signal.",
"- Aucun holdout.",
"- Aucun paramètre optimisé.",
"",
"V4.17 TERMINÉ"
]

(O/"summary_v417.md").write_text(
    "\n".join(out),encoding="utf-8"
)

print()
print("===== V4.17 GLOBAL =====")
print(A.to_string(index=False))
print()
print("===== OUTPUTS =====")
for f in [
    "v417_survivorship.csv",
    "v417_fold.csv",
    "v417_market.csv",
    "v417_signal.csv",
    "v417_regime.csv",
    "v417_trade_audit.csv",
    "summary_v417.md"
]:
    print(f)
print()
print("V4.17 TERMINÉ")
