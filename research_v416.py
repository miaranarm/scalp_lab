from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
SRC=O/"v414_replay.csv"
ORG=O/"v44_trades_oos.csv"

x=pd.read_csv(SRC)
o=pd.read_csv(ORG)

print("V4.16 | B1 ATTRIBUTION / SURVIVORSHIP")

# -------------------------------------------------
# VERIFICATION
# -------------------------------------------------

need_o=[
    "symbol","interval","fold","signal","regime",
    "profile","side","entry_time","entry_price","net"
]

miss=[c for c in need_o if c not in o.columns]
if miss:
    raise SystemExit(
        "v44_trades_oos.csv COLONNES ABSENTES: "
        +",".join(miss)
    )

need_x=[
    "mode","symbol","interval","fold","signal",
    "regime","profile","net"
]

miss=[c for c in need_x if c not in x.columns]
if miss:
    raise SystemExit(
        "v414_replay.csv COLONNES ABSENTES: "
        +",".join(miss)
    )

o["entry_time"]=pd.to_datetime(
    o["entry_time"],utc=True,errors="coerce"
)

if o["entry_time"].isna().any():
    raise SystemExit("entry_time invalide dans v44_trades_oos.csv")

print("ORIGINAL OOS",len(o))
print("REPLAY",len(x))

# -------------------------------------------------
# IDENTIFIANT ORIGINAL
# -------------------------------------------------
#
# v44_trades_oos contient l'entrée temporelle.
# On crée un ID déterministe.
#
# -------------------------------------------------

idcols=[
    "symbol","interval","fold","signal",
    "regime","profile","side","entry_time"
]

o["trade_id"]=(
    o["symbol"].astype(str)+"|"+
    o["interval"].astype(str)+"|"+
    o["fold"].astype(str)+"|"+
    o["signal"].astype(str)+"|"+
    o["regime"].astype(str)+"|"+
    o["profile"].astype(str)+"|"+
    o["side"].astype(str)+"|"+
    o["entry_time"].astype(str)
)

if o["trade_id"].duplicated().any():
    raise SystemExit(
        "trade_id ORIGINAL non unique"
    )

# -------------------------------------------------
# REPLAY V4.14
# -------------------------------------------------
#
# v414_replay ne possède pas entry_time.
# On utilise l'ordre d'apparition pour chaque
# combinaison structurelle.
#
# IMPORTANT :
# le replay V4.14 est construit directement en
# itérant sur v44_trades_oos dans son ordre.
#
# On reconstruit donc le même rang.
#
# -------------------------------------------------

basecols=[
    "symbol","interval","fold","signal",
    "regime","profile","side"
]

o["_rank"]=o.groupby(basecols).cumcount()

x["_rank"]=x.groupby(
    ["mode"]+basecols
).cumcount()

# -------------------------------------------------
# ORIGINAL REPLAY
# -------------------------------------------------
#
# Le mode ORIGINAL du replay correspond aux
# trades réellement rejoués.
#
# -------------------------------------------------

xr=x[x["mode"]=="ORIGINAL"].copy()

# Pour retrouver le trade original,
# on apparie par dimensions + rang.
#
xr=xr.merge(
    o[
        basecols+
        ["_rank","trade_id","entry_time",
         "entry_price"]
    ],
    on=basecols+["_rank"],
    how="left",
    validate="one_to_one"
)

if xr["trade_id"].isna().any():
    raise SystemExit(
        "Impossible d'apparier ORIGINAL avec v44_trades_oos"
    )

# -------------------------------------------------
# B1 REPLAY
# -------------------------------------------------

b=x[x["mode"]!="ORIGINAL"].copy()

b=b.merge(
    o[
        basecols+
        ["_rank","trade_id","entry_time",
         "entry_price"]
    ],
    on=basecols+["_rank"],
    how="left",
    validate="many_to_one"
)

matched=b["trade_id"].notna().sum()

print("B1 MATCHED",matched)
print("B1 UNMATCHED",len(b)-matched)

b=b[b["trade_id"].notna()].copy()

# -------------------------------------------------
# ORIGINAL NET
# -------------------------------------------------

orignet=xr[
    ["trade_id","net"]
].rename(
    columns={"net":"net_original_replay"}
)

b=b.merge(
    orignet,
    on="trade_id",
    how="left",
    validate="many_to_one"
)

if b["net_original_replay"].isna().any():
    raise SystemExit(
        "ORIGINAL replay manquant pour certains B1"
    )

# -------------------------------------------------
# ATTRIBUTION
# -------------------------------------------------

b["delta_net"]=
b["net"]-b["net_original_replay"]

rows=[]

for mode,q in b.groupby("mode"):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "n":len(q),

        "original_mean":
            q.net_original_replay.mean(),

        "b1_mean":
            q.net.mean(),

        "delta_mean":
            d.mean(),

        "delta_median":
            d.median(),

        "original_win":
            (q.net_original_replay>0).mean(),

        "b1_win":
            (q.net>0).mean(),

        "delta_win":
            (q.net>0).mean()
            -(q.net_original_replay>0).mean(),

        "delta_positive_pct":
            (d>0).mean(),

        "delta_negative_pct":
            (d<0).mean()
    })

A=pd.DataFrame(rows)

A.to_csv(
    O/"v416_attribution.csv",
    index=False
)

# -------------------------------------------------
# FOLD
# -------------------------------------------------

rows=[]

for (mode,fold),q in b.groupby(
    ["mode","fold"]
):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "fold":fold,
        "n":len(q),
        "original_mean":
            q.net_original_replay.mean(),
        "b1_mean":
            q.net.mean(),
        "delta_mean":
            d.mean(),
        "delta_median":
            d.median(),
        "delta_positive_pct":
            (d>0).mean()
    })

F=pd.DataFrame(rows)

F.to_csv(
    O/"v416_fold.csv",
    index=False
)

# -------------------------------------------------
# MARKET
# -------------------------------------------------

rows=[]

for (mode,sym,it),q in b.groupby(
    ["mode","symbol","interval"]
):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "symbol":sym,
        "interval":it,
        "n":len(q),
        "original_mean":
            q.net_original_replay.mean(),
        "b1_mean":
            q.net.mean(),
        "delta_mean":
            d.mean(),
        "delta_median":
            d.median(),
        "delta_positive_pct":
            (d>0).mean()
    })

M=pd.DataFrame(rows)

M.to_csv(
    O/"v416_market.csv",
    index=False
)

# -------------------------------------------------
# SIGNAL
# -------------------------------------------------

rows=[]

for (mode,sig),q in b.groupby(
    ["mode","signal"]
):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "signal":sig,
        "n":len(q),
        "original_mean":
            q.net_original_replay.mean(),
        "b1_mean":
            q.net.mean(),
        "delta_mean":
            d.mean(),
        "delta_median":
            d.median(),
        "delta_positive_pct":
            (d>0).mean()
    })

S=pd.DataFrame(rows)

S.to_csv(
    O/"v416_signal.csv",
    index=False
)

# -------------------------------------------------
# REGIME
# -------------------------------------------------

rows=[]

for (mode,reg),q in b.groupby(
    ["mode","regime"]
):

    d=q["delta_net"]

    rows.append({
        "mode":mode,
        "regime":reg,
        "n":len(q),
        "original_mean":
            q.net_original_replay.mean(),
        "b1_mean":
            q.net.mean(),
        "delta_mean":
            d.mean(),
        "delta_median":
            d.median(),
        "delta_positive_pct":
            (d>0).mean()
    })

R=pd.DataFrame(rows)

R.to_csv(
    O/"v416_regime.csv",
    index=False
)

# -------------------------------------------------
# DISTRIBUTION
# -------------------------------------------------

rows=[]

for mode,q in b.groupby("mode"):

    d=q["delta_net"]

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

# -------------------------------------------------
# AUDIT COMPLET DES MATCHES
# -------------------------------------------------

audit=b[
    [
        "trade_id","mode",
        "symbol","interval","fold",
        "signal","regime","profile","side",
        "entry_time","entry_price",
        "net_original_replay",
        "net","delta_net"
    ]
].copy()

audit.to_csv(
    O/"v416_trade_audit.csv",
    index=False
)

# -------------------------------------------------
# RAPPORT
# -------------------------------------------------

out=[
    "# SCALP LAB V4.16 — B1 ATTRIBUTION",
    "",
    f"Original OOS source : {len(o)}",
    f"Replay rows : {len(x)}",
    f"B1 matched : {len(b)}",
    "Holdout : exclu",
    "",
    "## ATTRIBUTION",
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
    R.to_string(index=False),
    "",
    "## METHOD",
    "- Source ORIGINAL = v44_trades_oos.csv.",
    "- Résultat replay ORIGINAL = v414_replay.csv.",
    "- B1 = résultats V4.14.",
    "- Apparier par dimensions du trade + rang d'apparition.",
    "- entry_time vient de v44_trades_oos.csv.",
    "- delta_net = B1 moins ORIGINAL replay.",
    "- delta positif = amélioration du même trade.",
    "- Aucun nouveau signal.",
    "- Aucun nouveau seuil.",
    "- Holdout exclu.",
    "- Cette version mesure l'effet B1 sur les trades conservés.",
    "- Les trades rejetés par les filtres GAP seront analysés au V4.17."
]

(O/"summary_v416.md").write_text(
    "\n".join(out),
    encoding="utf-8"
)

print()
print("===== ATTRIBUTION =====")
print(A.to_string(index=False))

print()
print("===== DELTA DISTRIBUTION =====")
print(D.to_string(index=False))

print()
print("===== OUTPUTS =====")
print("v416_attribution.csv")
print("v416_delta_distribution.csv")
print("v416_fold.csv")
print("v416_market.csv")
print("v416_signal.csv")
print("v416_regime.csv")
print("v416_trade_audit.csv")
print("summary_v416.md")

print()
print("V4.16 TERMINÉ")
