from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
T=O/"v44_trades_oos.csv"
R=O/"v414_replay.csv"

print("V4.17 | TRUE SURVIVORSHIP AUDIT")

o=pd.read_csv(T)
r=pd.read_csv(R)

K=["symbol","interval","fold","signal","regime","profile","side"]

need=[*K,"entry_time"]
for c in need:
    if c not in o:
        raise SystemExit("v44 COLONNE ABSENTE: "+c)
for c in ["mode","net",*K]:
    if c not in r:
        raise SystemExit("v414 COLONNE ABSENTE: "+c)

o["entry_time"]=pd.to_datetime(
    o["entry_time"],utc=True,errors="coerce"
)
if o.entry_time.isna().any():
    raise SystemExit("entry_time invalide")

# Identifiant déterministe des trades originaux
o["_rank"]=o.groupby(K).cumcount()
o["trade_id"]=[f"T{i:05d}" for i in range(len(o))]

# ORIGINAL replay = référence exacte V4.14
orig=r[r.mode=="ORIGINAL"].copy()
orig["_rank"]=orig.groupby(K).cumcount()

orig=orig.merge(
    o[K+["_rank","trade_id","entry_time","entry_price"]],
    on=K+["_rank"],how="left",validate="one_to_one"
)

if orig.trade_id.isna().any():
    raise SystemExit("ORIGINAL non apparié")

orig=orig[["trade_id","net"]].rename(
    columns={"net":"original_net"}
)

print("ORIGINAL",len(orig))

# Analyse de chaque filtre
MODES=["B1_ALL","GAP0","GAP10","GAP25","GAP50"]
all_rows=[]

for mode in MODES:
    b=r[r.mode==mode].copy()
    b["_rank"]=b.groupby(K).cumcount()

    b=b.merge(
        o[K+["_rank","trade_id"]],
        on=K+["_rank"],how="left",
        validate="many_to_one"
    )

    if b.trade_id.isna().any():
        raise SystemExit(f"{mode}: trade non apparié")

    b=b.merge(orig,on="trade_id",how="left")
    b["mode"]=mode
    all_rows.append(b)

b=pd.concat(all_rows,ignore_index=True)

# ---------- GLOBAL ----------
rows=[]

for mode,q in b.groupby("mode"):
    retained=set(q.trade_id)
    base=orig.copy()
    base["status"]=np.where(
        base.trade_id.isin(retained),"RETAINED","EXCLUDED"
    )

    rr=base[base.status=="RETAINED"]
    xx=base[base.status=="EXCLUDED"]

    z=q.merge(
        base[["trade_id","status"]],
        on="trade_id",how="left"
    )

    rb=z[z.status=="RETAINED"]

    n=len(base)
    nr=len(rr)
    ne=len(xx)

    # Contribution par trade candidat
    baseline_sum=base.original_net.sum()
    retained_orig_sum=rr.original_net.sum()
    b1_sum=rb.net.sum()

    selection=(retained_orig_sum-baseline_sum)/n
    entry=(b1_sum-retained_orig_sum)/n
    total=(b1_sum-baseline_sum)/n

    rows.append({
        "mode":mode,
        "original_n":n,
        "retained_n":nr,
        "excluded_n":ne,
        "retained_pct":nr/n,
        "excluded_pct":ne/n,

        "all_original_mean":base.original_net.mean(),
        "retained_original_mean":rr.original_net.mean(),
        "excluded_original_mean":xx.original_net.mean(),
        "retained_b1_mean":rb.net.mean(),

        "selection_contribution":selection,
        "entry_contribution":entry,
        "total_contribution":total,

        "excluded_win":(xx.original_net>0).mean(),
        "excluded_loss_pct":(xx.original_net<0).mean(),
        "retained_original_win":
            (rr.original_net>0).mean(),
        "retained_b1_win":
            (rb.net>0).mean()
    })

A=pd.DataFrame(rows)
A.to_csv(O/"v417_survivorship.csv",index=False)

# ---------- FOLD ----------
rows=[]
for (mode,fold),q in b.groupby(["mode","fold"]):
    ids=set(q.trade_id)
    base=orig.copy()
    rr=base[base.trade_id.isin(ids)]
    xx=base[~base.trade_id.isin(ids)]
    rb=q[q.trade_id.isin(ids)]

    rows.append({
        "mode":mode,"fold":fold,
        "original_n":len(base),
        "retained_n":len(rr),
        "excluded_n":len(xx),
        "retained_pct":len(rr)/len(base),
        "original_mean":base.original_net.mean(),
        "retained_original_mean":rr.original_net.mean(),
        "excluded_original_mean":
            xx.original_net.mean() if len(xx) else np.nan,
        "b1_mean":rb.net.mean(),
        "selection_contribution":
            (rr.original_net.sum()-
             base.original_net.sum())/len(base),
        "entry_contribution":
            (rb.net.sum()-
             rr.original_net.sum())/len(base)
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
        (orig.trade_id.isin(ids)) |
        (orig.symbol==sym)&
        (orig.interval==it)
    ]

    base=orig[
        (orig.symbol==sym)&
        (orig.interval==it)
    ]

    rr=base[base.trade_id.isin(ids)]
    xx=base[~base.trade_id.isin(ids)]
    rb=q

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
        "b1_mean":rb.net.mean()
    })

M=pd.DataFrame(rows)
M.to_csv(O/"v417_market.csv",index=False)

# ---------- SIGNAL ----------
def table(cols,name):
    rows=[]
    for key,q in b.groupby(cols):
        if not isinstance(key,tuple): key=(key,)
        ids=set(q.trade_id)

        mask=np.ones(len(orig),dtype=bool)
        for c,v in zip(cols,key):
            mask &= orig[c].eq(v)

        base=orig[mask]
        rr=base[base.trade_id.isin(ids)]
        xx=base[~base.trade_id.isin(ids)]

        z={
            "original_n":len(base),
            "retained_n":len(rr),
            "excluded_n":len(xx),
            "retained_pct":
                len(rr)/len(base) if len(base) else np.nan,
            "original_mean":base.original_net.mean(),
            "retained_original_mean":
                rr.original_net.mean(),
            "excluded_original_mean":
                xx.original_net.mean()
                if len(xx) else np.nan,
            "b1_mean":q.net.mean()
        }
        z.update(dict(zip(cols,key)))
        rows.append(z)

    z=pd.DataFrame(rows)
    z.to_csv(O/f"v417_{name}.csv",index=False)
    return z

S=table(["mode","signal"],"signal")
G=table(["mode","regime"],"regime")

# ---------- AUDIT TRADE PAR TRADE ----------
audit=[]

for mode,q in b.groupby("mode"):
    ids=set(q.trade_id)

    for _,z in orig.iterrows():
        tid=z.trade_id
        hit=q[q.trade_id==tid]

        if len(hit):
            b1=float(hit.iloc[0].net)
            status="RETAINED"
        else:
            b1=np.nan
            status="EXCLUDED"

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
            "delta_net":
                b1-z.original_net
                if np.isfinite(b1) else np.nan
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
"## INTERPRETATION",
"- selection_contribution = effet du rejet des trades.",
"- entry_contribution = effet du changement d'entrée B1 sur les trades retenus.",
"- total_contribution = effet combiné par trade candidat.",
"- EXCLUDED = trade absent du filtre.",
"- RETAINED = trade conservé par le filtre.",
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
