from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
SRC=O/"v414_replay.csv"

x=pd.read_csv(SRC)

need=["mode","symbol","interval","fold","signal","regime","profile",
      "side","net"]
miss=[c for c in need if c not in x.columns]
if miss: raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

x["mode"]=x["mode"].astype(str)
o=x[x["mode"]=="ORIGINAL"].copy()

if o.empty:
    raise SystemExit("ORIGINAL ABSENT")

print("V4.16 | B1 ATTRIBUTION / SURVIVORSHIP")
print("ORIGINAL",len(o))

modes=["B1_ALL","GAP0","GAP10","GAP25","GAP50"]

# -------------------------------------------------
# Même trade = identité par dimensions disponibles
# -------------------------------------------------

keys=["symbol","interval","fold","signal","regime",
      "profile","side"]

# Si plusieurs lignes existent dans un groupe,
# on conserve l'ordre original comme identifiant local.
o["tid"]=o.groupby(keys).cumcount()

x=x[x["mode"].isin(modes)].copy()
x["tid"]=x.groupby(keys+["mode"]).cumcount()

# -------------------------------------------------
# Recalage plus robuste par trade ordinal.
# Les populations B1 sont des sous-ensembles du même
# flux V4.14, mais peuvent avoir des trous.
# On reconstruit un identifiant avec les dimensions
# et entry_time si disponible.
# -------------------------------------------------

if "entry_time" in o.columns and "entry_time" in x.columns:
    keys2=keys+["entry_time"]
else:
    keys2=keys+["net"]

o2=o[keys2+["net"]].copy()
o2=o2.rename(columns={"net":"net_original"})

# Les lignes B1 gardent les mêmes dimensions de trade.
z=x.merge(o2,on=keys2,how="left")

z["kept"]=z["net_original"].notna()

# -------------------------------------------------
# ATTRIBUTION
# -------------------------------------------------

# Pour chaque mode :
# ALL = tous les trades rejoués B1
# FILTERED = trades dont le gap filtre exclut le trade
#
# Le CSV v414_replay ne contient pas explicitement les
# trades exclus par GAP. On peut donc mesurer les survivants
# directement, et comparer leur net B1 au net ORIGINAL.
#
# L'écart B1 - ORIGINAL = effet combiné :
# entrée différente + recalcul TP/SL + survivorship.

rows=[]

for mode,q in z.groupby("mode"):

    q=q[q["kept"]].copy()

    if q.empty: continue

    q["delta_net"]=q["net"]-q["net_original"]

    rows.append({
        "mode":mode,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":q.delta_net.mean(),
        "original_win":(q.net_original>0).mean(),
        "b1_win":(q.net>0).mean(),
        "delta_win":(q.net>0).mean()-
                    (q.net_original>0).mean(),
        "original_positive":(q.net_original>0).sum(),
        "b1_positive":(q.net>0).sum(),
        "delta_positive":
            (q.net>0).sum()-(q.net_original>0).sum()
    })

A=pd.DataFrame(rows)
A.to_csv(O/"v416_attribution.csv",index=False)

# -------------------------------------------------
# PAR FOLD
# -------------------------------------------------

rows=[]

for (mode,fold),q in z.groupby(["mode","fold"]):

    q=q[q["kept"]].copy()
    if q.empty: continue

    dn=q.net-q.net_original

    rows.append({
        "mode":mode,
        "fold":fold,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_win":
            (q.net>0).mean()-(q.net_original>0).mean(),
        "positive_delta":
            (dn>0).mean()
    })

F=pd.DataFrame(rows)
F.to_csv(O/"v416_fold.csv",index=False)

# -------------------------------------------------
# MARCHÉ / INTERVALLE
# -------------------------------------------------

rows=[]

for (mode,sym,it),q in z.groupby(
    ["mode","symbol","interval"]
):

    q=q[q["kept"]].copy()
    if q.empty: continue

    dn=q.net-q.net_original

    rows.append({
        "mode":mode,
        "symbol":sym,
        "interval":it,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_win":
            (q.net>0).mean()-(q.net_original>0).mean(),
        "positive_delta":
            (dn>0).mean()
    })

M=pd.DataFrame(rows)
M.to_csv(O/"v416_market.csv",index=False)

# -------------------------------------------------
# SIGNAL
# -------------------------------------------------

rows=[]

for (mode,sig),q in z.groupby(["mode","signal"]):

    q=q[q["kept"]].copy()
    if q.empty: continue

    dn=q.net-q.net_original

    rows.append({
        "mode":mode,
        "signal":sig,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_win":
            (q.net>0).mean()-(q.net_original>0).mean(),
        "positive_delta":
            (dn>0).mean()
    })

S=pd.DataFrame(rows)
S.to_csv(O/"v416_signal.csv",index=False)

# -------------------------------------------------
# REGIME
# -------------------------------------------------

rows=[]

for (mode,reg),q in z.groupby(["mode","regime"]):

    q=q[q["kept"]].copy()
    if q.empty: continue

    dn=q.net-q.net_original

    rows.append({
        "mode":mode,
        "regime":reg,
        "n":len(q),
        "original_mean":q.net_original.mean(),
        "b1_mean":q.net.mean(),
        "delta_mean":dn.mean(),
        "delta_win":
            (q.net>0).mean()-(q.net_original>0).mean(),
        "positive_delta":
            (dn>0).mean()
    })

R=pd.DataFrame(rows)
R.to_csv(O/"v416_regime.csv",index=False)

# -------------------------------------------------
# DISTRIBUTION DE L'EFFET B1
# -------------------------------------------------

rows=[]

for mode,q in z.groupby("mode"):

    q=q[q["kept"]].copy()
    if q.empty: continue

    dn=q.net-q.net_original

    rows.append({
        "mode":mode,
        "n":len(q),
        "delta_mean":dn.mean(),
        "delta_median":dn.median(),
        "delta_p10":dn.quantile(.10),
        "delta_p25":dn.quantile(.25),
        "delta_p75":dn.quantile(.75),
        "delta_p90":dn.quantile(.90),
        "delta_positive_pct":(dn>0).mean(),
        "delta_negative_pct":(dn<0).mean(),
        "delta_zero_pct":(dn==0).mean()
    })

D=pd.DataFrame(rows)
D.to_csv(O/"v416_delta_distribution.csv",index=False)

# -------------------------------------------------
# RAPPORT
# -------------------------------------------------

out=[
"# SCALP LAB V4.16 — B1 ATTRIBUTION / SURVIVORSHIP",
"",
f"ORIGINAL rows : {len(o)}",
f"B1 replay rows : {len(x)}",
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
"## INTERPRETATION",
"- original_mean = résultat du même trade selon ORIGINAL.",
"- b1_mean = résultat du même trade selon B1.",
"- delta_mean = B1 moins ORIGINAL sur les trades conservés.",
"- positive_delta = proportion de trades dont le net augmente avec B1.",
"- Les trades exclus par un filtre GAP ne sont pas inclus dans le delta individuel.",
"- Cette analyse distingue l'effet du nouveau prix d'entrée de l'effet de sélection.",
"- Aucun seuil n'est sélectionné.",
"- Aucun holdout n'est utilisé.",
"- Aucun signal nouveau n'est créé."
]

(O/"summary_v416.md").write_text(
    "\n".join(out),encoding="utf-8"
)

print()
print("===== ATTRIBUTION =====")
print(A.to_string(index=False))

print()
print("===== DELTA =====")
print(D.to_string(index=False))

print()
print("V4.16 TERMINÉ")
