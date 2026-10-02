from pathlib import Path
import pandas as pd,numpy as np

O=Path("results")
SRC=O/"v414_replay.csv"

x=pd.read_csv(SRC)

need=["mode","fold","symbol","interval","signal","regime","profile","net"]
miss=[c for c in need if c not in x.columns]
if miss:
    raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

x=x[x["mode"]!="ORIGINAL"].copy()

print("V4.15 | B1 OOS STABILITY")
print("ROWS",len(x))

def st(q):
    if len(q)==0:
        return {"n":0,"mean":np.nan,"win":np.nan,"pf":np.nan}

    p=q.loc[q.net>0,"net"].sum()
    n=-q.loc[q.net<0,"net"].sum()

    return {
        "n":len(q),
        "mean":q.net.mean(),
        "win":(q.net>0).mean(),
        "pf":p/n if n else np.nan
    }

o=pd.read_csv(SRC)

if "mode" not in o.columns:
    raise SystemExit("COLONNE mode ABSENTE")

o=o[o["mode"]=="ORIGINAL"].copy()

# =========================
# FOLD
# =========================

rows=[]

for fold,q in x.groupby("fold"):

    for mode,z in q.groupby("mode"):

        a=st(z)

        oo=o[o["fold"]==fold]
        b=st(oo)

        a.update({
            "fold":fold,
            "mode":mode,
            "delta_mean":a["mean"]-b["mean"],
            "delta_win":a["win"]-b["win"],
            "delta_pf":a["pf"]-b["pf"]
        })

        rows.append(a)

F=pd.DataFrame(rows)

F.to_csv(O/"v415_fold.csv",index=False)

# =========================
# MARKET / INTERVAL
# =========================

rows=[]

for (mode,sym,it),q in x.groupby(
    ["mode","symbol","interval"]
):

    a=st(q)

    oo=o[
        (o["symbol"]==sym)&
        (o["interval"]==it)
    ]

    b=st(oo)

    a.update({
        "mode":mode,
        "symbol":sym,
        "interval":it,
        "delta_mean":a["mean"]-b["mean"],
        "delta_win":a["win"]-b["win"],
        "delta_pf":a["pf"]-b["pf"]
    })

    rows.append(a)

M=pd.DataFrame(rows)

M.to_csv(O/"v415_market.csv",index=False)

# =========================
# SIGNAL
# =========================

rows=[]

for (mode,sig),q in x.groupby(
    ["mode","signal"]
):

    a=st(q)

    oo=o[o["signal"]==sig]
    b=st(oo)

    a.update({
        "mode":mode,
        "signal":sig,
        "delta_mean":a["mean"]-b["mean"],
        "delta_win":a["win"]-b["win"],
        "delta_pf":a["pf"]-b["pf"]
    })

    rows.append(a)

S=pd.DataFrame(rows)

S.to_csv(O/"v415_signal.csv",index=False)

# =========================
# REGIME
# =========================

rows=[]

for (mode,reg),q in x.groupby(
    ["mode","regime"]
):

    a=st(q)

    oo=o[o["regime"]==reg]
    b=st(oo)

    a.update({
        "mode":mode,
        "regime":reg,
        "delta_mean":a["mean"]-b["mean"],
        "delta_win":a["win"]-b["win"],
        "delta_pf":a["pf"]-b["pf"]
    })

    rows.append(a)

R=pd.DataFrame(rows)

R.to_csv(O/"v415_regime.csv",index=False)

# =========================
# STABILITY
# =========================

stab=[]

for mode,q in F.groupby("mode"):

    stab.append({
        "mode":mode,
        "folds":len(q),
        "delta_mean_avg":q["delta_mean"].mean(),
        "delta_mean_median":q["delta_mean"].median(),
        "delta_mean_positive_folds":
            (q["delta_mean"]>0).sum(),
        "delta_pf_positive_folds":
            (q["delta_pf"]>0).sum(),
        "absolute_positive_folds":
            (q["mean"]>0).sum(),
        "mean_positive_pct":
            (q["mean"]>0).mean()
    })

T=pd.DataFrame(stab)

T.to_csv(O/"v415_stability.csv",index=False)

# =========================
# SUMMARY
# =========================

out=[
    "# SCALP LAB V4.15 — B1 OOS STABILITY",
    "",
    f"Replay rows : {len(x)}",
    f"ORIGINAL rows : {len(o)}",
    "Holdout : exclu",
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
    "## METHOD",
    "- ORIGINAL = référence V4.4.",
    "- B1 filters = V4.14 replay.",
    "- Aucun nouveau signal.",
    "- Aucun accès au holdout.",
    "- Même population temporelle que le replay V4.14.",
    "- Delta = B1 moins ORIGINAL.",
    "- Positive fold count = mesure descriptive.",
    "- La stabilité temporelle est vérifiée fold par fold."
]

(O/"summary_v415.md").write_text(
    "\n".join(out),
    encoding="utf-8"
)

print()
print("===== STABILITY =====")
print(T.to_string(index=False))

print()
print("===== OUTPUTS =====")
print("v415_fold.csv")
print("v415_market.csv")
print("v415_signal.csv")
print("v415_regime.csv")
print("v415_stability.csv")
print("summary_v415.md")

print()
print("V4.15 TERMINÉ")
