import os,pandas as pd,numpy as np

S="results/v44_trades_oos.csv"; O="results"
os.makedirs(O,exist_ok=True)
d=pd.read_csv(S)
print(f"V4.5.7 | INPUT {len(d)}")

s=d.side.astype(str).str.strip().str.upper()
d["side_name"]=s.replace({"1":"LONG","+1":"LONG","-1":"SHORT",
                          "LONG":"LONG","SHORT":"SHORT"})
d["exit"]=d.exit_reason.astype(str).str.strip().str.lower()

for c in ["entry_price","tp_price","sl_price","mfe","mae",
          "tp_mult","sl_mult","duration_bars"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

d["tp_dist"]=np.where(d.side_name.eq("LONG"),
    d.tp_price/d.entry_price-1,
    1-d.tp_price/d.entry_price)

d["sl_dist"]=np.where(d.side_name.eq("LONG"),
    1-d.sl_price/d.entry_price,
    d.sl_price/d.entry_price-1)

d["tp_reached"]=d.mfe>=d.tp_dist
d["sl_reached"]=d.mae.abs()>=d.sl_dist
d["tp_exit"]=d.exit.eq("tp")
d["sl_exit"]=d.exit.eq("sl")
d["time_exit"]=d.exit.eq("time")

d["missed_tp"]=d.tp_reached&~d.tp_exit
d["clean_missed_tp"]=d.tp_reached&~d.sl_reached&~d.tp_exit
d["tp_sl_both_reached"]=d.tp_reached&d.sl_reached

tp=int(d.tp_exit.sum())
sl=int(d.sl_exit.sum())
tm=int(d.time_exit.sum())

if (tp,sl,tm)!=(791,1213,192):
    raise SystemExit(f"EXIT CHECK FAILED {tp}/{sl}/{tm}")

def cls(r):
    if not r.missed_tp:return "NOT_MISSED"
    if r.clean_missed_tp:return "CLEAN_MISSED_TP"
    if r.tp_sl_both_reached and r.sl_exit:return "TP_SL_AMBIGUOUS_SL_EXIT"
    if r.tp_sl_both_reached and r.time_exit:return "TP_SL_AMBIGUOUS_TIME_EXIT"
    if r.tp_sl_both_reached:return "TP_SL_BOTH_REACHED"
    if r.time_exit:return "TP_REACHED_TIME_EXIT"
    return "OTHER_MISSED_TP"

d["forensic_class"]=d.apply(cls,axis=1)
m=d[d.missed_tp].copy()

cols=["symbol","interval","fold","signal","regime","profile",
      "tp_mult","sl_mult","side_name","entry_time","exit_time",
      "entry_price","tp_price","sl_price","exit_price",
      "tp_dist","sl_dist","mfe","mae","duration_bars",
      "exit","forensic_class"]

m[cols].to_csv(f"{O}/v457_missed_tp_forensics.csv",index=False)
d[d.tp_reached][cols].to_csv(f"{O}/v457_all_tp_reached.csv",index=False)

pd.DataFrame([{
    "trades":len(d),"tp":tp,"sl":sl,"time":tm,
    "tp_reached":int(d.tp_reached.sum()),
    "missed_tp":len(m),
    "clean":int(d.clean_missed_tp.sum()),
    "both":int(d.tp_sl_both_reached.sum())
}]).to_csv(f"{O}/v457_global.csv",index=False)

(m.groupby("forensic_class")
 .agg(n=("symbol","size"),mean_net=("net","mean"),
      mean_mfe=("mfe","mean"),mean_mae=("mae","mean"))
 .reset_index()
 .to_csv(f"{O}/v457_classification.csv",index=False))

(m.groupby(["symbol","interval"])
 .agg(n=("symbol","size"),clean=("clean_missed_tp","sum"),
      both=("tp_sl_both_reached","sum"),mean_net=("net","mean"))
 .reset_index()
 .to_csv(f"{O}/v457_symbol_interval.csv",index=False))

(m.groupby(["symbol","interval","signal","regime","profile"])
 .agg(n=("symbol","size"),clean=("clean_missed_tp","sum"),
      both=("tp_sl_both_reached","sum"),mean_net=("net","mean"))
 .reset_index()
 .to_csv(f"{O}/v457_strategy.csv",index=False))

r=int(d.tp_reached.sum())
clean=int(d.clean_missed_tp.sum())
both=int(d.tp_sl_both_reached.sum())

summary=f"""# SCALP LAB V4.5.7

Input OOS : {len(d)}
Holdout : exclu

EXIT : TP {tp} | SL {sl} | TIME {tm}
EXIT CHECK : PASS

TP REACHED : {r} ({100*r/len(d):.2f}%)
MISSED TP : {len(m)} ({100*len(m)/len(d):.2f}%)
CLEAN MISSED TP : {clean}
TP+SL BOTH : {both}

CLEAN = MFE >= TP, MAE < SL, sortie != TP.
BOTH = MFE >= TP et MAE >= SL.
OHLC/MFE/MAE ne permet pas de reconstruire
l'ordre intrabougie exact.
V4.1 conserve la priorité SL.

V4.4 inchangée.
Aucune optimisation.
Aucun trading réel.
"""

open(f"{O}/summary_v457.md","w",encoding="utf-8").write(summary)

print(f"EXIT PASS | TP {tp} | SL {sl} | TIME {tm}")
print(f"TP REACHED {r} | MISSED {len(m)} | CLEAN {clean} | BOTH {both}")

print("V4.5.7 TERMINÉ")
