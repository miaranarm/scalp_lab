import pandas as pd
from pathlib import Path
P=Path("results");d=pd.read_csv(P/"v44_trades_oos.csv")
d["fees"]=d.entry_fee+d.exit_fee
def A(c,n):
 x=d.groupby(c).agg(n=("net","size"),gross=("gross","mean"),fees=("fees","mean"),net=("net","mean"),win=("net",lambda s:(s>0).mean()),gross_win=("gross",lambda s:(s>0).mean()),mfe=("mfe","mean"),mae=("mae","mean")).reset_index()
 x.to_csv(P/f"v418_{n}.csv",index=False);return x
T=[("signal","signal"),(["symbol","interval"],"market"),("fold","fold"),("regime","regime"),("profile","profile"),("exit_reason","exit")]
X=[]
for c,n in T:X.append((n,A(c,n)))
d[["symbol","interval","fold","signal","regime","side","gross","fees","net","exit_reason"]].to_csv(P/"v418_trade_audit.csv",index=False)
o=["# V4.18 — EDGE ANATOMY","","Trades: "+str(len(d)),"","Net = gross - fees. Aucun filtre ni optimisation."]
for n,x in X:o+=["",f"## {n.upper()}",x.to_string(index=False)]
(P/"summary_v418.md").write_text("\n".join(o),encoding="utf8")
print("\n".join(o));print("V4.18 TERMINÉ")