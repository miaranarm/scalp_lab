from pathlib import Path
import pandas as pd
import numpy as np

O=Path("results")
d=pd.read_csv(O/"v48_trade_paths.csv")

for c in ["entry_price","tp_price","sl_price","net","mfe","mae"]:
    d[c]=pd.to_numeric(d[c],errors="coerce")

d.entry_time=pd.to_datetime(d.entry_time,utc=True)
d.exit_time=pd.to_datetime(d.exit_time,utc=True)

def pct(x):
    return x*100

# V4.10 utilise les chemins déjà calculés par V4.8.
# On récupère les premiers niveaux favorables/adverses.
levels=["tp50","sl50","tp75","sl75","tp100","sl100"]

for c in levels:
    cbar=c+"_bar"
    if cbar not in d:
        d[cbar]=np.nan

def first_bar(r,side):
    vals=[]
    for c in ["tp50_bar","tp75_bar","tp100_bar"]:
        v=r.get(c,np.nan)
        if pd.notna(v): vals.append(("F",int(v)))
    for c in ["sl50_bar","sl75_bar","sl100_bar"]:
        v=r.get(c,np.nan)
        if pd.notna(v): vals.append(("A",int(v)))
    if not vals:
        return None
    return min(vals,key=lambda x:x[1])

# Analyse compacte des premières bougies.
# Les colonnes bars_to_* sont des index de bougie depuis l'entrée.
def timing(r,n):
    fav=[r.get("tp50_bar",np.nan),r.get("tp75_bar",np.nan),
         r.get("tp100_bar",np.nan)]
    adv=[r.get("sl50_bar",np.nan),r.get("sl75_bar",np.nan),
         r.get("sl100_bar",np.nan)]

    fav=[x for x in fav if pd.notna(x) and x<=n]
    adv=[x for x in adv if pd.notna(x) and x<=n]

    f=min(fav) if fav else np.nan
    a=min(adv) if adv else np.nan

    return pd.Series({
        "fav":int(pd.notna(f)),
        "adv":int(pd.notna(a)),
        "fav_first":int(pd.notna(f) and (pd.isna(a) or f<a)),
        "adv_first":int(pd.notna(a) and (pd.isna(f) or a<f)),
        "both":int(pd.notna(f) and pd.notna(a) and f==a)
    })

for n in range(1,7):
    x=d.apply(lambda r:timing(r,n),axis=1)
    for c in x:
        d[f"b{n}_{c}"]=x[c].values

# Première direction réellement détectable.
def first_path(r):
    f=r.tp50_bar if pd.notna(r.tp50_bar) else np.inf
    a=r.sl50_bar if pd.notna(r.sl50_bar) else np.inf
    if f==np.inf and a==np.inf: return "NONE"
    if f<a: return "FAVORABLE"
    if a<f: return "ADVERSE"
    return "SAME_BAR"

d["first_path"]=d.apply(first_path,axis=1)

# Agrégations
def A(cols):
    return d.groupby(cols,observed=True).agg(
        n=("net","size"),
        net=("net","mean"),
        win=("net",lambda x:(x>0).mean()),
        mfe=("mfe","mean"),
        mae=("mae","mean")
    ).reset_index()

# Première direction
fp=A(["first_path"])
fp.to_csv(O/"v410_first_path.csv",index=False)

# Timing par horizon
rows=[]
for n in range(1,7):
    rows.append({
        "bars":n,
        "fav":d[f"b{n}_fav"].sum(),
        "fav_pct":d[f"b{n}_fav"].mean(),
        "adv":d[f"b{n}_adv"].sum(),
        "adv_pct":d[f"b{n}_adv"].mean(),
        "fav_first":d[f"b{n}_fav_first"].sum(),
        "adv_first":d[f"b{n}_adv_first"].sum(),
        "both":d[f"b{n}_both"].sum()
    })

h=pd.DataFrame(rows)
h.to_csv(O/"v410_timing.csv",index=False)

# Timing croisé par signal
rows=[]
for sig,g in d.groupby("signal",observed=True):
    for n in range(1,7):
        rows.append({
            "signal":sig,
            "bars":n,
            "n":len(g),
            "fav_first":g[f"b{n}_fav_first"].sum(),
            "adv_first":g[f"b{n}_adv_first"].sum(),
            "fav_pct":g[f"b{n}_fav"].mean(),
            "adv_pct":g[f"b{n}_adv"].mean()
        })

sp=pd.DataFrame(rows)
sp.to_csv(O/"v410_signal_timing.csv",index=False)

# Marché
rows=[]
for (sym,it),g in d.groupby(["symbol","interval"],observed=True):
    for n in range(1,7):
        rows.append({
            "symbol":sym,
            "interval":it,
            "bars":n,
            "n":len(g),
            "fav_first":g[f"b{n}_fav_first"].sum(),
            "adv_first":g[f"b{n}_adv_first"].sum(),
            "fav_pct":g[f"b{n}_fav"].mean(),
            "adv_pct":g[f"b{n}_adv"].mean()
        })

mp=pd.DataFrame(rows)
mp.to_csv(O/"v410_market_timing.csv",index=False)

# Résumé
lines=[
"# SCALP LAB V4.10 — ENTRY TIMING FORENSICS",
"",
f"Trades OOS : {len(d)}",
"Holdout : exclu",
"",
"## Première direction",
fp.to_string(index=False),
"",
"## Timing global",
h.to_string(index=False),
"",
"## Signal × timing",
sp.to_string(index=False),
"",
"## Marché × timing",
mp.to_string(index=False),
"",
"## Méthode",
"- Analyse OOS uniquement.",
"- Aucun signal ni paramètre modifié.",
"- Horizon : 1 à 6 bougies après l'entrée.",
"- TP50/SL50 servent uniquement à identifier la première direction.",
"- Une même bougie peut toucher les deux niveaux : ordre intrabougie inconnu."
]

(O/"summary_v410.md").write_text("\n".join(lines),encoding="utf-8")

print("V4.10 | ENTRY TIMING")
print("TRADES",len(d))
print("\nFIRST PATH")
print(fp.to_string(index=False))

print("\nTIMING")
print(h.to_string(index=False))

print("\nSIGNAL")
for n in range(1,7):
    x=sp[sp.bars==n]
    print(
        f"B{n} | FAV_FIRST {int(x.fav_first.sum())} | "
        f"ADV_FIRST {int(x.adv_first.sum())}"
    )

print("\nMARKET")
for _,r in mp[mp.bars==1].iterrows():
    print(
        f"{r.symbol} {r.interval} | "
        f"FAV {r.fav_pct:.1%} | ADV {r.adv_pct:.1%}"
    )

print("\nV4.10 TERMINÉ")
