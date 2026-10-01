"""
SCALP LAB V4.4 — TRADE-LEVEL FORENSICS
Rejoue les stratégies sélectionnées par V4.1 et exporte chaque trade OOS.
FINAL HOLDOUT exclu.
"""

from __future__ import annotations
import argparse, time
from pathlib import Path
import numpy as np
import pandas as pd
import research_v41 as v41

OUT=Path("results")
TRADES=OUT/"v44_trades_oos.csv"

def replay(L, signal, tp_m, sl_m, hold, profile, slip):
    c,h,lo,atr=L["c"],L["h"],L["l"],L["atr"]
    t=L["time"]
    fee=(v41.FEE_MAKER if profile!="taker" else v41.FEE_TAKER)
    maker_tp=profile in ("maker_tp","maker_both")
    out=[]; free=0

    for j in np.flatnonzero(signal):
        if j<free or j+1>=len(c) or not np.isfinite(atr[j]):
            continue
        side=int(signal[j]); a=atr[j]
        if a<=0: continue

        if profile=="maker_both":
            if side==1:
                if lo[j+1]>c[j]*(1-v41.THROUGH): continue
            else:
                if h[j+1]<c[j]*(1+v41.THROUGH): continue
            entry=c[j]
            entry_fee=v41.FEE_MAKER
        else:
            entry=c[j+1]*(1+side*slip)
            entry_fee=v41.FEE_TAKER

        tp=entry+side*tp_m*a
        sl=entry-side*sl_m*a
        tp_touch=tp*(1+side*v41.THROUGH) if maker_tp else tp
        end=min(j+hold,len(c)-1)

        exit_i=end; exit_px=c[end]; kind="time"

        for k in range(j+1,end+1):
            hit_tp=h[k]>=tp_touch if side==1 else lo[k]<=tp_touch
            hit_sl=lo[k]<=sl if side==1 else h[k]>=sl

            if hit_sl:
                exit_i=k
                exit_px=sl*(1-side*slip)
                kind="sl"
                break

            if hit_tp:
                exit_i=k
                exit_px=tp if maker_tp else tp*(1-side*slip)
                kind="tp"
                break

        if kind=="time":
            exit_px*=1-side*slip

        exit_fee=(
            v41.FEE_MAKER if kind=="tp" and profile!="taker"
            else v41.FEE_TAKER
        )

        gross=side*(exit_px-entry)/entry
        net=(1+gross)*(1-entry_fee)*(1-exit_fee)-1

        hi=h[j+1:exit_i+1]
        lw=lo[j+1:exit_i+1]

        if side==1:
            mfe=(np.max(hi)-entry)/entry
            mae=(np.min(lw)-entry)/entry
        else:
            mfe=(entry-np.min(lw))/entry
            mae=(entry-np.max(hi))/entry

        out.append({
            "signal_i":j,
            "entry_i":j+1,
            "exit_i":exit_i,
            "signal_time":int(t[j]),
            "entry_time":int(t[j+1]),
            "exit_time":int(t[exit_i]),
            "side":"LONG" if side==1 else "SHORT",
            "entry_price":entry,
            "exit_price":exit_px,
            "tp_price":tp,
            "sl_price":sl,
            "gross":gross,
            "net":net,
            "entry_fee":entry_fee,
            "exit_fee":exit_fee,
            "exit_reason":kind.upper(),
            "duration_bars":exit_i-j,
            "mfe":mfe,
            "mae":mae,
        })
        free=exit_i+1

    return out


def load_pair(symbol,interval,days):
    now=int(time.time()*1000)
    start=now-days*86_400_000
    ctx=v41.CONTEXT_ENTRY_TO_CTX.get(interval,"1h")
    warm=v41.CONTEXT_WARMUP_DAYS.get(ctx,12)

    entry=v41.to_frame(v41.fetch_vision(symbol,interval,start,now))
    h1=v41.to_frame(v41.fetch_vision(
        symbol,ctx,start-warm*86_400_000,now
    ))
    entry=entry[entry.time>=start].reset_index(drop=True)
    ef,cands=v41.make_candidates(entry,h1,ctx)

    L=dict(ef)
    L["time"]=entry["time"].to_numpy(float)

    folds,holdout=v41.make_folds(len(entry),interval)
    return entry,L,cands,folds,holdout


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--intervals",default="5m,15m")
    ap.add_argument("--days",type=int,default=730)
    args=ap.parse_args()

    wf=pd.read_csv(OUT/"walk_forward_v41.csv")
    wf=wf[wf["fold"].astype(str)!="FINAL"].copy()

    rows=[]

    for interval in [x.strip() for x in args.intervals.split(",")]:
        for symbol in [x.strip() for x in args.symbols.split(",")]:
            q=wf[(wf.symbol==symbol)&(wf.interval==interval)]
            if q.empty:
                continue

            print(f"V44 | {symbol} {interval}")

            entry,L,cands,folds,holdout=load_pair(
                symbol,interval,args.days
            )

            for _,r in q.iterrows():
                fi=int(r.fold)
                if fi<1 or fi>len(folds):
                    print(f"  F{fi} ignoré")
                    continue

                tr0,tr1,te0,te1=folds[fi-1]

                ci=int(r.candidate)
                if ci<0 or ci>=len(cands):
                    print(f"  F{fi} candidate invalide")
                    continue

                cand=cands[ci]

                trades=replay(
                    L,cand.signal,
                    float(r.tp),float(r.sl),int(r.hold),
                    str(r.profile),
                    v41.SLIP.get(symbol,v41.DEFAULT_SLIP)
                )

                trades=v41.inside(trades,te0,te1)

                for z in trades:
                    z.update({
                        "symbol":symbol,
                        "interval":interval,
                        "fold":fi,
                        "candidate":ci,
                        "signal":r.signal,
                        "regime":r.regime,
                        "profile":r.profile,
                        "tp_mult":r.tp,
                        "sl_mult":r.sl,
                        "hold":r.hold,
                        "train_n":r.train_n,
                        "train_mean":r.train_mean,
                        "train_pf":r.train_pf,
                        "fold_test_mean":r.test_mean,
                        "fold_random_mean":r.bench_random_mean,
                        "fold_edge_random":r.edge_vs_random,
                    })
                    rows.append(z)

                print(
                    f"  F{fi} | {r.signal} | {r.regime} | "
                    f"{r.profile} | trades={len(trades)}"
                )

    if not rows:
        raise SystemExit("Aucun trade OOS.")

    df=pd.DataFrame(rows)

    for c in ("signal_time","entry_time","exit_time"):
        df[c]=pd.to_datetime(df[c],unit="ms",utc=True)

    cols=[
        "symbol","interval","fold","candidate","signal","regime","profile",
        "tp_mult","sl_mult","hold",
        "signal_time","entry_time","exit_time","side",
        "entry_price","exit_price","tp_price","sl_price",
        "gross","net","entry_fee","exit_fee",
        "exit_reason","duration_bars","mfe","mae",
        "train_n","train_mean","train_pf",
        "fold_test_mean","fold_random_mean","fold_edge_random"
    ]
    df=df[cols]
    df.to_csv(TRADES,index=False)

    def agg(cols,name):
        x=df.groupby(cols).agg(
            trades=("net","size"),
            mean_net=("net","mean"),
            mean_gross=("gross","mean"),
            median_net=("net","median"),
            win=("net",lambda x:(x>0).mean()),
            mfe=("mfe","mean"),
            mae=("mae","mean"),
            duration=("duration_bars","mean")
        ).reset_index()
        x.to_csv(OUT/name,index=False)

    agg(["symbol","interval"],"v44_symbol_interval.csv")
    agg(["side"],"v44_long_short.csv")
    agg(["exit_reason"],"v44_exit_analysis.csv")
    agg(["signal"],"v44_signal.csv")
    agg(["regime"],"v44_regime.csv")
    agg(["profile"],"v44_profile.csv")
    agg(["signal","side"],"v44_signal_side.csv")
    agg(["signal","exit_reason"],"v44_signal_exit.csv")
    agg(["fold"],"v44_fold.csv")
    agg(["duration_bars"],"v44_duration.csv")

    summary=[]
    summary += [
        "# SCALP LAB V4.4 — TRADE FORENSICS",
        "",
        f"- Trades OOS : {len(df)}",
        f"- LONG : {(df.side=='LONG').sum()}",
        f"- SHORT : {(df.side=='SHORT').sum()}",
        f"- TP : {(df.exit_reason=='TP').sum()}",
        f"- SL : {(df.exit_reason=='SL').sum()}",
        f"- TIME : {(df.exit_reason=='TIME').sum()}",
        "",
        "## Global",
        "",
        f"- mean net/trade : {df.net.mean():+.4%}",
        f"- median net : {df.net.median():+.4%}",
        f"- win rate : {(df.net>0).mean():.2%}",
        f"- mean gross : {df.gross.mean():+.4%}",
        f"- mean MFE : {df.mfe.mean():+.4%}",
        f"- mean MAE : {df.mae.mean():+.4%}",
        f"- mean duration : {df.duration_bars.mean():.2f} bars",
        "",
        "## Par côté",
        "",
    ]

    for side,g in df.groupby("side"):
        summary.append(
            f"- **{side}** : n={len(g)}, "
            f"mean={g.net.mean():+.4%}, "
            f"win={(g.net>0).mean():.2%}, "
            f"MFE={g.mfe.mean():+.4%}, "
            f"MAE={g.mae.mean():+.4%}"
        )

    summary += [
        "",
        "## Sorties",
        "",
    ]

    for reason,g in df.groupby("exit_reason"):
        summary.append(
            f"- **{reason}** : n={len(g)}, "
            f"mean={g.net.mean():+.4%}, "
            f"win={(g.net>0).mean():.2%}"
        )

    summary += [
        "",
        "## Important",
        "",
        "- Analyse strictement OOS.",
        "- FINAL HOLDOUT volontairement exclu.",
        "- Les prix et coûts sont rejoués avec les règles exactes de V4.1.",
        "- TP/SL conserve la priorité SL de V4.1 en cas de conflit intrabougie.",
        "- Aucun signal, indicateur ou paramètre supplémentaire n'est introduit.",
        ""
    ]

    (OUT/"summary_v44.md").write_text(
        "\n".join(summary),encoding="utf-8"
    )

    print("")
    print("="*55)
    print("V44 | TERMINÉ")
    print(f"TRADES {len(df)}")
    print("FINAL HOLDOUT EXCLU")
    print("results/v44_trades_oos.csv")
    print("results/summary_v44.md")
    print("="*55)


if __name__=="__main__":
    main()
