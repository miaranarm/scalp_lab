import os,pandas as pd,numpy as np

SRC="results/v44_trades_oos.csv"; OUT="results"
os.makedirs(OUT,exist_ok=True)

d=pd.read_csv(SRC)
s=d.side.astype(str).str.strip().str.upper()
d["side"]=s.replace({"1":"LONG","+1":"LONG","-1":"SHORT"})
d["exit_reason"]=d.exit_reason.astype(str).str.strip().str.lower()

for c in ["entry_price","tp_price","sl_price","exit_price","mfe","mae","duration_bars"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

d["tp_dist"]=np.where(
    d.side.eq("LONG"),d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price
)
d["sl_dist"]=np.where(
    d.side.eq("LONG"),1-d.sl_price/d.entry_price,
    d.sl_price/d.entry_price-1
)

d["tp_reached"]=d.mfe>=d.tp_dist
d["sl_reached"]=d.mae.abs()>=d.sl_dist
d["missed"]=d.tp_reached & ~d.exit_reason.eq("tp")
d["clean"]=d.missed & ~d.sl_reached

x=d[d.clean].copy()

if len(x)!=6:
    raise SystemExit(f"EXPECTED 6 CLEAN MISSED TP, GOT {len(x)}")

x["mfe_pct"]=x.mfe*100
x["mae_pct"]=x.mae*100
x["tp_pct"]=x.tp_dist*100
x["sl_pct"]=x.sl_dist*100
x["mfe_over_tp"]=x.mfe/x.tp_dist
x["mae_over_sl"]=x.mae.abs()/x.sl_dist

cols=[
"symbol","interval","fold","signal","regime","profile",
"side","entry_time","exit_time","duration_bars",
"entry_price","tp_price","sl_price","exit_price",
"tp_pct","sl_pct","mfe_pct","mae_pct",
"mfe_over_tp","mae_over_sl","exit_reason","net"
]

x[cols].to_csv(f"{OUT}/v458_clean_missed_tp.csv",index=False)

# compact summary
print("V4.5.8 | CLEAN MISSED TP AUDIT")
print("COUNT",len(x))
print("NET MEAN",f'{x.net.mean()*100:.4f}%')
print("MFE MEAN",f'{x.mfe_pct.mean():.4f}%')
print("TP MEAN",f'{x.tp_pct.mean():.4f}%')
print("")

for _,r in x.iterrows():
    print(
        f'{r.symbol} {r.interval} F{int(r.fold)} | '
        f'{r.side} | TP {r.tp_pct:.3f}% | '
        f'MFE {r.mfe_pct:.3f}% | '
        f'MAE {r.mae_pct:.3f}% | '
        f'{r.exit_reason.upper()} | NET {r.net*100:.3f}%'
    )

pd.DataFrame([{
    "clean_missed_tp":len(x),
    "net_mean":x.net.mean(),
    "mfe_mean":x.mfe.mean(),
    "tp_mean":x.tp_dist.mean(),
    "sl_mean":x.sl_dist.mean()
}]).to_csv(f"{OUT}/v458_summary.csv",index=False)

with open(f"{OUT}/summary_v458.md","w") as f:
    f.write(
f"""# V4.5.8 — CLEAN MISSED TP AUDIT

- Trades audités : {len(x)}
- Source : V4.4 OOS
- Holdout : exclu

## Résultat

- Net moyen : {x.net.mean()*100:.4f}%
- MFE moyen : {x.mfe.mean()*100:.4f}%
- TP moyen : {x.tp_dist.mean()*100:.4f}%
- SL moyen : {x.sl_dist.mean()*100:.4f}%

## Définition

TP atteint selon MFE,
SL non atteint selon MAE,
sortie finale différente de TP.

Cette analyse ne modifie aucun signal,
paramètre ou résultat V4.4.
"""
    )

print("V4.5.8 TERMINÉ")
