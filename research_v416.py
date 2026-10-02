from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
SRC=O/"v414_replay.csv"

x=pd.read_csv(SRC)

need=[
    "mode","symbol","interval","fold","signal",
    "regime","profile","side","net"
]
miss=[c for c in need if c not in x.columns]
if miss:
    raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

print("V4.16 | B1 ATTRIBUTION / SURVIVORSHIP")

# -------------------------------------------------
# ORIGINAL
# -------------------------------------------------

o=x[x["mode"]=="ORIGINAL"].copy()

if o.empty:
    raise SystemExit("ORIGINAL ABSENT")

print("ORIGINAL",len(o))

# -------------------------------------------------
# IDENTIFIANT DE TRADE
# -------------------------------------------------
#
# v414_replay reprend les mêmes trades V4.14.
# entry_time est l'identifiant le plus fiable.
# On utilise les dimensions du trade + entry_time.
#
# -------------------------------------------------

idcols=[
    "symbol","interval","fold","signal",
    "regime","profile","side"
]

if "entry_time" in x.columns:
    idcols += ["entry_time"]
else:
    raise SystemExit(
        "entry_time ABSENT: impossible de faire "
        "l'attribution trade par trade."
    )

# Nettoyage éventuel des dates
x["entry_time"]=pd.to_datetime(
    x["entry_time"],errors="coerce",utc=True
)

if x["entry_time"].isna().any():
    raise SystemExit("entry_time contient des valeurs invalides")

# Vérification des doublons ORIGINAL
dup=o.duplicated(idcols).sum()

print("ORIGINAL DUPLICATES",dup)

if dup:
    raise SystemExit(
        "IDENTIFIANT ORIGINAL NON UNIQUE: "
        f"{dup} doublons"
    )

# -------------------------------------------------
# Table ORIGINAL
# -------------------------------------------------

orig=o[idcols+["net"]].copy()
orig=orig.rename(columns={"net":"net_original"})

# -------------------------------------------------
# B1
# -------------------------------------------------

modes=["B1_ALL","GAP0","GAP10","GAP25","GAP50"]

b=x[x["mode"].isin(modes)].copy()

# -------------------------------------------------
# MERGE
# -------------------------------------------------

z=b.merge(
    orig,
    on=idcols,
    how="left",
    validate="many_to_one"
)

z["matched"]=z["net_original"].notna()

print("B1 ROWS",len(b))
print("MATCHED",int(z["matched"].sum()))
print("UNMATCHED",int((~z["matched"]).sum()))

if (~z["matched"]).any():
    print("WARNING: trades B1 non retrouvés")

z=z[z["matched"]].copy()

# -------------------------------------------------
# ATTRIBUTION TRADE PAR TRADE
# -------------------------------------------------

z["delta_net"]=z["net"]-z["net_original"]

rows=[]

for mode,q in z.groupby("mode"):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "n":len(q),

        "original_mean":
            q["net_original"].mean(),

        "b1_mean":
            q["net"].mean(),

        "delta_mean":
            dn.mean(),

        "delta_median":
            dn.median(),

        "original_win":
            (q["net_original"]>0).mean(),

        "b1_win":
            (q["net"]>0).mean(),

        "delta_win":
            (q["net"]>0).mean()
            -(q["net_original"]>0).mean(),

        "delta_positive_pct":
            (dn>0).mean(),

        "delta_negative_pct":
            (dn<0).mean()
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

for (mode,fold),q in z.groupby(
    ["mode","fold"]
):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "fold":fold,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_median":dn.median(),
        "delta_win":
            (q.net>0).mean()
            -(q.net_original>0).mean(),
        "delta_positive_pct":
            (dn>0).mean()
    })

F=pd.DataFrame(rows)

F.to_csv(
    O/"v416_fold.csv",
    index=False
)

# -------------------------------------------------
# MARKET / INTERVAL
# -------------------------------------------------

rows=[]

for (mode,sym,it),q in z.groupby(
    ["mode","symbol","interval"]
):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "symbol":sym,
        "interval":it,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_median":dn.median(),
        "delta_win":
            (q.net>0).mean()
            -(q.net_original>0).mean(),
        "delta_positive_pct":
            (dn>0).mean()
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

for (mode,sig),q in z.groupby(
    ["mode","signal"]
):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "signal":sig,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_median":dn.median(),
        "delta_win":
            (q.net>0).mean()
            -(q.net_original>0).mean(),
        "delta_positive_pct":
            (dn>0).mean()
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

for (mode,reg),q in z.groupby(
    ["mode","regime"]
):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "regime":reg,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_median":dn.median(),
        "delta_win":
            (q.net>0).mean()
            -(q.net_original>0).mean(),
        "delta_positive_pct":
            (dn>0).mean()
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

for mode,q in z.groupby("mode"):

    dn=q["delta_net"]

    rows.append({
        "mode":mode,
        "n":len(q),
        "mean":dn.mean(),
        "median":dn.median(),
        "p10":dn.quantile(.10),
        "p25":dn.quantile(.25),
        "p75":dn.quantile(.75),
        "p90":dn.quantile(.90),
        "positive_pct":(dn>0).mean(),
        "negative_pct":(dn<0).mean()
    })

D=pd.DataFrame(rows)

D.to_csv(
    O/"v416_delta_distribution.csv",
    index=False
)

# -------------------------------------------------
# RAPPORT
# -------------------------------------------------

out=[
    "# SCALP LAB V4.16 — B1 ATTRIBUTION",
    "",
    f"ORIGINAL : {len(o)}",
    f"B1 rows : {len(b)}",
    f"Matched : {len(z)}",
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
    "- ORIGINAL = résultat V4.14 de référence.",
    "- B1 = résultat V4.14 avec entrée B1.",
    "- Les trades sont appariés par symbol, interval, fold, signal,",
    "  regime, profile, side et entry_time.",
    "- delta_net = net B1 moins net ORIGINAL.",
    "- delta positif = amélioration du même trade.",
    "- Aucun nouveau signal.",
    "- Aucun nouveau seuil.",
    "- Holdout exclu.",
    "- Cette version mesure l'effet d'entrée sur les trades conservés.",
    "- Elle ne prétend pas encore mesurer la performance des trades rejetés."
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
print("summary_v416.md")

print()
print("V4.16 TERMINÉ")
