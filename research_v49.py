from pathlib import Path
import pandas as pd
import numpy as np

O=Path("results")
d=pd.read_csv(O/"v48_trade_paths.csv")

for c in ["net","mfe","mae","duration_bars"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

for c in ["tp50_before_sl50","sl50_before_tp50"]:
    d[c]=d[c].astype(bool)

def A(cols):
    return d.groupby(cols,observed=True).agg(
        n=("net","size"),
        net=("net","mean"),
        win=("net",lambda x:(x>0).mean()),
        mfe=("mfe","mean"),
        mae=("mae","mean"),
        tp=("exit_reason",lambda x:(x=="TP").sum()),
        sl=("exit_reason",lambda x:(x=="SL").sum()),
        time=("exit_reason",lambda x:(x=="TIME").sum()),
        tp50=("tp50_before_sl50","sum"),
        sl50=("sl50_before_tp50","sum")
    ).reset_index()

def S(cols,name):
    x=A(cols)
    x.to_csv(O/name,index=False)
    return x

print("V4.9.1 | PATH x EDGE")
print("TRADES",len(d))

p=S(["path_class"],"v49_path_edge.csv")
e=S(["exit_reason","path_class"],"v49_exit_path_edge.csv")
s=S(["signal","path_class"],"v49_signal_path_edge.csv")
m=S(["symbol","interval","path_class"],"v49_market_path_edge.csv")
r=S(["regime","path_class"],"v49_regime_path_edge.csv")
sr=S(["signal","regime","path_class"],"v49_signal_regime_path.csv")
z=S(["side","path_class"],"v49_side_path_edge.csv")

g=pd.DataFrame([{
    "trades":len(d),
    "net":d.net.mean(),
    "win":(d.net>0).mean(),
    "mfe":d.mfe.mean(),
    "mae":d.mae.mean(),
    "tp50_first":d.tp50_before_sl50.sum(),
    "sl50_first":d.sl50_before_tp50.sum()
}])
g.to_csv(O/"v49_global.csv",index=False)

# compact summary
def top(x,n=8):
    x=x.sort_values("net",ascending=False).head(n)
    for _,q in x.iterrows():
        key=" | ".join(str(q[c]) for c in x.columns[:len(x.columns)-9])
        print(f"{key} | n={int(q.n)} net={q.net:.3%} win={q.win:.1%}")

lines=[
"# V4.9.1 — PATH × EDGE",
f"Trades OOS : {len(d)}",
f"Net/trade : {d.net.mean():.3%}",
f"Win rate : {d.net.gt(0).mean():.2%}",
f"TP50 first : {d.tp50_before_sl50.sum()} ({d.tp50_before_sl50.mean():.2%})",
f"SL50 first : {d.sl50_before_tp50.sum()} ({d.sl50_before_tp50.mean():.2%})",
"",
"## Path",
p.to_string(index=False),
"",
"## Signal × Path",
s.to_string(index=False),
"",
"## Market × Path",
m.to_string(index=False),
"",
"## Regime × Path",
r.to_string(index=False),
"",
"## Signal × Regime × Path",
sr.to_string(index=False)
]
(O/"summary_v49.md").write_text("\n".join(lines),encoding="utf-8")

print(f"NET {d.net.mean():.3%} | WIN {d.net.gt(0).mean():.2%}")
print(f"TP50_FIRST {d.tp50_before_sl50.sum()} | SL50_FIRST {d.sl50_before_tp50.sum()}")

print("\nTOP SIGNAL/PATH")
top(s)

print("\nTOP MARKET/PATH")
top(m)

print("\nTOP REGIME/PATH")
top(r)

print("\nV4.9.1 TERMINÉ")
