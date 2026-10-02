from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
R=O/"v414_replay.csv"
T=O/"v44_trades_oos.csv"

print("V4.16 | B1 ATTRIBUTION / SURVIVORSHIP")

x=pd.read_csv(R)
o=pd.read_csv(T)

# -----------------------------
# CHECK
# -----------------------------

need_o=[
    "symbol","interval","fold","signal","regime",
    "profile","side","entry_time","entry_price","net"
]
need_x=[
    "mode","symbol","interval","fold","signal",
    "regime","profile","side","net"
]

m=[c for c in need_o if c not in o]
if m:
    raise SystemExit("v44 COLONNES ABSENTES: "+",".join(m))

m=[c for c in need_x if c not in x]
if m:
    raise SystemExit("v414 COLONNES ABSENTES: "+",".join(m))

o["entry_time"]=pd.to_datetime(
    o["entry_time"],utc=True,errors="coerce"
)

if o["entry_time"].isna().any():
    raise SystemExit("entry_time invalide")

print("ORIGINAL SOURCE",len(o))
print("REPLAY",len(x))

# -----------------------------
# TRADE ID
# -----------------------------

K=[
    "symbol","interval","fold","signal",
    "regime","profile","side"
]

o["_rank"]=o.groupby(K).cumcount()

x["_rank"]=x.groupby(
    ["mode"]+K
).cumcount()

o["trade_id"]=[
    f"T{i:05d}" for i in range(len(o))
]

# -----------------------------
# ORIGINAL REPLAY
# -----------------------------

orig=x[x["mode"]=="ORIGINAL"].copy()

orig=orig.merge(
    o[K+["_rank","trade_id","entry_time","entry_price"]],
    on=K+["_rank"],
    how="left",
    validate="one_to_one"
)

if orig["trade_id"].isna().any():
    raise SystemExit("ORIGINAL non apparié")

orig=orig[
    ["trade_id","net"]
].rename(
    columns={"net":"net_original"}
)

# -----------------------------
# B1
# -----------------------------

b=x[x["mode"]!="ORIGINAL"].copy()

b=b.merge(
    o[K+["_rank","trade_id","entry_time","entry_price"]],
    on=K+["_rank"],
    how="left",
    validate="many_to_one"
)

print("B1 ROWS",len(b))
print("B1 MATCHED",b["trade_id"].notna().sum())

b=b[b["trade_id"].notna()].copy()

b=b.merge(
    orig,
    on="trade_id",
    how="left",
    validate="many_to_one"
)

if b["net_original"].isna().any():
    raise SystemExit("ORIGINAL replay absent")

# -----------------------------
# DELTA
# -----------------------------

b["delta_net"]=(
    b["net"]-b["net_original"]
)

# -----------------------------
# GLOBAL
# -----------------------------

rows=[]

for mode,q in b.groupby("mode"):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":d.mean(),
        "delta_median":d.median(),
        "original_win":(q.net_original>0).mean(),
        "b1_win":(q.net>0).mean(),
        "delta_win":
            (q.net>0).mean()-
            (q.net_original>0).mean(),
        "delta_positive_pct":(d>0).mean(),
        "delta_negative_pct":(d<0).mean()
    })

A=pd.DataFrame(rows)
A.to_csv(O/"v416_attribution.csv",index=False)

# -----------------------------
# FOLD
# -----------------------------

def make_table(cols,name):

    rows=[]

    for key,q in b.groupby(cols):

        if not isinstance(key,tuple):
            key=(key,)

        d=q["delta_net"]

        z={
            "n":len(q),
            "original_mean":q.net_original.mean(),
            "b1_mean":q.net.mean(),
            "delta_mean":d.mean(),
            "delta_median":d.median(),
            "delta_positive_pct":(d>0).mean()
        }

        z.update(dict(zip(cols,key)))
        rows.append(z)

    z=pd.DataFrame(rows)

    if len(z):
        z=z[
            cols+
            [
                "n","original_mean","b1_mean",
                "delta_mean","delta_median",
                "delta_positive_pct"
            ]
        ]

    z.to_csv(O/f"v416_{name}.csv",index=False)

    return z

F=make_table(["mode","fold"],"fold")
M=make_table(["mode","symbol","interval"],"market")
S=make_table(["mode","signal"],"signal")
G=make_table(["mode","regime"],"regime")

# -----------------------------
# DISTRIBUTION
# -----------------------------

rows=[]

for mode,q in b.groupby("mode"):

    d=q.delta_net

    rows.append({
        "mode":mode,
        "n":len(q),
        "mean":d.mean(),
        "median":d.median(),
        "p10":d.quantile(.10),
        "p25":d.quantile(.25),
        "p75":d.quantile(.75),
        "p90":d.quantile(.90),
        "positive_pct":(d>0).mean(),
        "negative_pct":(d<0).mean()
    })

D=pd.DataFrame(rows)
D.to_csv(
    O/"v416_delta_distribution.csv",
    index=False
)

# -----------------------------
# TRADE AUDIT
# -----------------------------

cols=[
    "trade_id","mode",
    "symbol","interval","fold",
    "signal","regime","profile","side",
    "entry_time","entry_price",
    "net_original","net","delta_net"
]

b[cols].to_csv(
    O/"v416_trade_audit.csv",
    index=False
)

# -----------------------------
# REPORT
# -----------------------------

out=[
    "# SCALP LAB V4.16 — B1 ATTRIBUTION",
    "",
    f"Original source : {len(o)}",
    f"Replay rows : {len(x)}",
    f"B1 matched : {len(b)}",
    "Holdout : exclu",
    "",
    "## GLOBAL",
    A.to_string(index=False),
    "",
    "## DELTA DISTRIBUTION",
    D.to_string(index=False),
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
    "## METHOD",
    "- ORIGINAL source = v44_trades_oos.csv.",
    "- ORIGINAL replay = v414_replay.csv.",
    "- B1 = V4.14 replay.",
    "- Appariment par dimensions + rang d'apparition.",
    "- entry_time provient de v44_trades_oos.csv.",
    "- delta_net = B1 moins ORIGINAL replay.",
    "- Aucun nouveau signal.",
    "- Aucun nouveau seuil.",
    "- Holdout exclu.",
    "- Les trades exclus par GAP seront étudiés en V4.17."
]

(O/"summary_v416.md").write_text(
    "\n".join(out),
    encoding="utf-8"
)

print()
print("===== GLOBAL =====")
print(A.to_string(index=False))

print()
print("===== DELTA =====")
print(D.to_string(index=False))

print()
print("===== OUTPUTS =====")
for f in [
    "v416_attribution.csv",
    "v416_delta_distribution.csv",
    "v416_fold.csv",
    "v416_market.csv",
    "v416_signal.csv",
    "v416_regime.csv",
    "v416_trade_audit.csv",
    "summary_v416.md"
]:
    print(f)

print()
print("V4.16 TERMINÉ")
