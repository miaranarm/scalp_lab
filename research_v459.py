import os,pandas as pd,numpy as np

SRC="results/v458_clean_missed_tp.csv"
OUT="results"
THROUGH=0.00005  # 0.005%

d=pd.read_csv(SRC)

d["entry_price"]=pd.to_numeric(d.entry_price)
d["tp_price"]=pd.to_numeric(d.tp_price)
d["mfe"]=pd.to_numeric(d.mfe)

# Seuil TP exact + THROUGH
long=d.side.eq("LONG")

d["tp_touch_dist"]=np.where(
    long,
    d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price
)

d["through_price"]=np.where(
    long,
    d.tp_price*(1+THROUGH),
    d.tp_price*(1-THROUGH)
)

d["through_dist"]=np.where(
    long,
    d.through_price/d.entry_price-1,
    1-d.through_price/d.entry_price
)

d["mfe_pct"]=d.mfe*100
d["tp_touch_pct"]=d.tp_touch_dist*100
d["through_pct"]=d.through_dist*100

d["tp_touch"]=d.mfe>=d.tp_touch_dist
d["through_reached"]=d.mfe>=d.through_dist

d["classification"]=np.select(
    [
        d.through_reached,
        d.tp_touch
    ],
    [
        "THROUGH_REACHED",
        "TP_TOUCH_ONLY"
    ],
    default="TP_NOT_REACHED"
)

cols=[
"symbol","interval","fold","signal","regime","profile","side",
"entry_time","exit_time","duration_bars",
"entry_price","tp_price","through_price",
"tp_touch_pct","through_pct","mfe_pct",
"classification","exit_reason","net"
]

d[cols].to_csv(
    f"{OUT}/v459_through_audit.csv",index=False
)

print("V4.5.9 | THROUGH AUDIT")
print("INPUT",len(d))
print("THROUGH",f"{THROUGH*100:.3f}%")
print("")

for c in [
    "TP_TOUCH_ONLY",
    "THROUGH_REACHED",
    "TP_NOT_REACHED"
]:
    print(c,int((d.classification==c).sum()))

print("")
print("===== CASES =====")

for _,r in d.iterrows():
    print(
        f'{r.symbol} {r.interval} F{int(r.fold)} | '
        f'{r.side} | TP {r.tp_touch_pct:.4f}% | '
        f'THROUGH {r.through_pct:.4f}% | '
        f'MFE {r.mfe_pct:.4f}% | '
        f'{r.classification}'
    )

n_touch=int(d.tp_touch.sum())
n_through=int(d.through_reached.sum())
n_only=int(((d.tp_touch)&(~d.through_reached)).sum())

pd.DataFrame([{
    "input":len(d),
    "tp_touch":n_touch,
    "through_reached":n_through,
    "tp_touch_only":n_only
}]).to_csv(
    f"{OUT}/v459_summary.csv",index=False
)

with open(f"{OUT}/summary_v459.md","w") as f:
    f.write(f"""# SCALP LAB V4.5.9 — THROUGH AUDIT

- Input : {len(d)} cas
- Source : V4.5.8
- Holdout : exclu
- THROUGH : {THROUGH*100:.3f}%

## Résultat

- TP touch : {n_touch}
- THROUGH atteint : {n_through}
- TP touch uniquement : {n_only}

## Interprétation

TP touch = MFE >= TP théorique.

THROUGH atteint = MFE >= seuil TP avec
le franchissement maker THROUGH de V4.1.

Un cas TP_TOUCH_ONLY n'est donc pas considéré
comme un vrai TP maker manqué.

Aucun signal ni paramètre V4.1/V4.4 n'est modifié.
""")

print("")
print("V4.5.9 TERMINÉ")
