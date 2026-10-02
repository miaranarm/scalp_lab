import os,pandas as pd,numpy as np

SRC="results/v458_clean_missed_tp.csv"
OUT="results"
THROUGH=0.00005

d=pd.read_csv(SRC)

need=["symbol","interval","fold","signal","regime","profile",
      "side","entry_price","tp_price","mfe_pct","net"]
miss=[c for c in need if c not in d.columns]
if miss:
    raise SystemExit("COLONNES ABSENTES: "+",".join(miss))

for c in ["entry_price","tp_price","mfe_pct","net"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

long=d.side.astype(str).str.upper().eq("LONG")

# TP théorique
d["tp_dist"]=np.where(
    long,
    d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price
)

# TP + THROUGH
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

d["tp_touch"]=d.mfe_pct/100 >= d.tp_dist
d["through_reached"]=d.mfe_pct/100 >= d.through_dist

d["classification"]=np.select(
    [d.through_reached,d.tp_touch],
    ["THROUGH_REACHED","TP_TOUCH_ONLY"],
    default="TP_NOT_REACHED"
)

cols=[
"symbol","interval","fold","signal","regime","profile","side",
"entry_price","tp_price","through_price",
"tp_dist","through_dist","mfe_pct",
"classification","exit_reason","net"
]

d[cols].to_csv(
    f"{OUT}/v459_through_audit.csv",index=False
)

touch=int(d.tp_touch.sum())
through=int(d.through_reached.sum())
only=int((d.tp_touch & ~d.through_reached).sum())

print("V4.5.9 | THROUGH AUDIT")
print("INPUT",len(d))
print("TP TOUCH",touch)
print("THROUGH REACHED",through)
print("TP TOUCH ONLY",only)
print("")

for _,r in d.iterrows():
    print(
        f'{r.symbol} {r.interval} F{int(r.fold)} | '
        f'{r.side} | TP {r.tp_dist*100:.4f}% | '
        f'THROUGH {r.through_dist*100:.4f}% | '
        f'MFE {r.mfe_pct:.4f}% | '
        f'{r.classification}'
    )

pd.DataFrame([{
    "input":len(d),
    "tp_touch":touch,
    "through_reached":through,
    "tp_touch_only":only
}]).to_csv(
    f"{OUT}/v459_summary.csv",index=False
)

with open(f"{OUT}/summary_v459.md","w") as f:
    f.write(f"""# SCALP LAB V4.5.9 — THROUGH AUDIT

Input : {len(d)}
TP touch : {touch}
THROUGH reached : {through}
TP touch only : {only}

THROUGH V4.1 : {THROUGH*100:.3f}%

TP_TOUCH_ONLY = TP théorique atteint,
mais seuil THROUGH non atteint.

THROUGH_REACHED = seuil maker franchi.

Aucun recalcul V4.4.
Aucun changement de stratégie.
Holdout exclu.
""")

print("")
print("V4.5.9 TERMINÉ")
