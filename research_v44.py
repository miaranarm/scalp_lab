from pathlib import Path
from collections import Counter
import time
import numpy as np
import pandas as pd

import research_v41 as v41

R = Path("results")
WF = R / "walk_forward_v41.csv"

def pct(x):
    return "nan" if not np.isfinite(x) else f"{x*100:+.4f}%"

def trade_rows(L, trades, entry):
    rows = []

    for t in trades:
        j, ei, xi = t["signal_i"], t["entry_i"], t["exit_i"]
        side = int(t["side"])

        ep = float(L["c"][j] if ei == j + 1 else L["c"][ei])
        # Le simulateur V4.1 ne stocke pas le prix exact d'entrée.
        # On le reconstruit à partir des règles du profil.
        atr = float(L["atr"][j])

        if t["entry_i"] == j + 1:
            if side == 1:
                ep = float(L["c"][j + 1] * (1 + v41.SLIP.get(
                    CURRENT_SYMBOL, v41.DEFAULT_SLIP)))
            else:
                ep = float(L["c"][j + 1] * (1 - v41.SLIP.get(
                    CURRENT_SYMBOL, v41.DEFAULT_SLIP)))

        # Pour maker_both, l'entrée est le close du signal.
        # Pour maker_tp, entrée taker.
        # Le profil est injecté plus bas dans chaque ligne.
        xp = float(L["c"][xi])

        if xi < len(L["c"]):
            if t["kind"] == "sl":
                xp = float(
                    L["c"][j] -
                    side * 0
                )

        a = max(j + 1, ei)
        b = min(xi, len(L["h"]) - 1)

        hh = L["h"][a:b+1]
        ll = L["l"][a:b+1]

        if len(hh):
            if side == 1:
                mfe = float(np.max(hh) / ep - 1)
                mae = float(np.min(ll) / ep - 1)
            else:
                mfe = float(1 - np.min(ll) / ep)
                mae = float(1 - np.max(hh) / ep)
        else:
            mfe = mae = np.nan

        rows.append({
            "signal_time": pd.to_datetime(
                entry["time"].iloc[j], unit="ms", utc=True
            ),
            "entry_time": pd.to_datetime(
                entry["time"].iloc[ei], unit="ms", utc=True
            ),
            "exit_time": pd.to_datetime(
                entry["time"].iloc[xi], unit="ms", utc=True
            ),
            "side": "LONG" if side == 1 else "SHORT",
            "entry_price": ep,
            "exit_price": xp,
            "gross": t["gross"],
            "net": t["net"],
            "cost": t["gross"] - t["net"],
            "exit": t["kind"],
            "duration_bars": t["duration"],
            "duration_hours": t["duration"] *
                v41.INTERVAL_MS[CURRENT_INTERVAL] / 3600000,
            "mfe": mfe,
            "mae": mae,
        })

    return rows


def analyse(df, keys):
    if df.empty:
        return pd.DataFrame()

    g = df.groupby(keys, dropna=False)

    x = g.agg(
        trades=("net", "count"),
        mean_net=("net", "mean"),
        median_net=("net", "median"),
        mean_gross=("gross", "mean"),
        mean_cost=("cost", "mean"),
        win_rate=("net", lambda z: float((z > 0).mean())),
        mean_mfe=("mfe", "mean"),
        mean_mae=("mae", "mean"),
        median_duration=("duration_hours", "median"),
        tp=("exit", lambda z: int((z == "tp").sum())),
        sl=("exit", lambda z: int((z == "sl").sum())),
        time_exit=("exit", lambda z: int((z == "time").sum())),
    ).reset_index()

    return x


def main():
    global CURRENT_SYMBOL, CURRENT_INTERVAL

    t0 = time.time()

    print("=" * 72)
    print("SCALP LAB V4.4 — TRADE LEVEL FORENSICS")
    print("=" * 72)

    if not WF.exists():
        raise SystemExit("ERREUR: results/walk_forward_v41.csv absent")

    wf = pd.read_csv(WF)

    oos = wf[wf["fold"].astype(str) != "FINAL"].copy()
    hold = wf[wf["fold"].astype(str) == "FINAL"].copy()

    print(f"V4.1 ROWS   : {len(wf)}")
    print(f"OOS ROWS    : {len(oos)}")
    print(f"HOLDOUT ROWS: {len(hold)}")

    all_trades = []

    symbols = sorted(oos.symbol.dropna().unique())
    intervals = sorted(oos.interval.dropna().unique())

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - 730 * 86_400_000

    for interval in intervals:
        for symbol in symbols:

            CURRENT_SYMBOL = symbol
            CURRENT_INTERVAL = interval

            pair = oos[
                (oos.symbol == symbol) &
                (oos.interval == interval)
            ].copy()

            if pair.empty:
                continue

            ctx = v41.CONTEXT_ENTRY_TO_CTX.get(interval, "1h")
            warm = v41.CONTEXT_WARMUP_DAYS.get(ctx, 12)

            print(
                f"\n{symbol} {interval} | "
                f"reconstruction..."
            )

            entry = v41.to_frame(
                v41.fetch_vision(
                    symbol, interval, start_ms, end_ms
                )
            )

            h1 = v41.to_frame(
                v41.fetch_vision(
                    symbol,
                    ctx,
                    start_ms - warm * 86_400_000,
                    end_ms
                )
            )

            if entry.empty or h1.empty:
                print("  DONNÉES ABSENTES")
                continue

            entry = entry[
                entry.time >= start_ms
            ].reset_index(drop=True)

            L, candidates = v41.make_candidates(
                entry, h1, ctx
            )

            folds, holdout_start = v41.make_folds(
                len(entry), interval
            )

            print(
                f"  candles={len(entry)} "
                f"folds={len(folds)} "
                f"candidates={len(candidates)}"
            )

            for _, row in pair.iterrows():

                fi = int(row["fold"])

                if fi < 1 or fi > len(folds):
                    continue

                tr0, tr1, te0, te1 = folds[fi - 1]

                cand_i = int(row["candidate"])
                cand = candidates[cand_i]

                trades = v41.simulate(
                    L,
                    cand.signal,
                    float(row["tp"]),
                    float(row["sl"]),
                    int(row["hold"]),
                    row["profile"],
                    v41.SLIP.get(
                        symbol, v41.DEFAULT_SLIP
                    )
                )

                trades = v41.inside(
                    trades, te0, te1
                )

                base = trade_rows(
                    L, trades, entry
                )

                for x in base:
                    x.update({
                        "symbol": symbol,
                        "interval": interval,
                        "fold": fi,
                        "signal": row["signal"],
                        "regime": row["regime"],
                        "profile": row["profile"],
                        "tp": row["tp"],
                        "sl": row["sl"],
                        "hold": row["hold"],
                        "train_n": row["train_n"],
                        "train_mean": row["train_mean"],
                        "train_pf": row["train_pf"],
                        "test_mean_fold": row["test_mean"],
                        "edge_vs_random": (
                            row["edge_vs_random"]
                            if "edge_vs_random" in row
                            else np.nan
                        ),
                    })

                all_trades.extend(base)

            print(
                f"  trades cumulés={len(all_trades)}"
            )

    if not all_trades:
        raise SystemExit("Aucun trade OOS reconstruit.")

    T = pd.DataFrame(all_trades)

    T["hour_utc"] = T["entry_time"].dt.hour
    T["weekday"] = T["entry_time"].dt.day_name()

    # --------------------------------------------------------
    # TRADE LEVEL
    # --------------------------------------------------------

    T.to_csv(
        R / "v44_trades_oos.csv",
        index=False
    )

    # --------------------------------------------------------
    # LONG / SHORT
    # --------------------------------------------------------

    analyse(
        T, ["side"]
    ).to_csv(
        R / "v44_long_short.csv",
        index=False
    )

    # --------------------------------------------------------
    # SORTIES
    # --------------------------------------------------------

    analyse(
        T, ["exit"]
    ).to_csv(
        R / "v44_exit_analysis.csv",
        index=False
    )

    # --------------------------------------------------------
    # DURÉE
    # --------------------------------------------------------

    T["duration_bucket"] = pd.cut(
        T["duration_hours"],
        [-1, 0.5, 1, 2, 4, 8, 24, 999999],
        labels=[
            "<=0.5h",
            "0.5-1h",
            "1-2h",
            "2-4h",
            "4-8h",
            "8-24h",
            ">24h"
        ]
    )

    analyse(
        T, ["duration_bucket"]
    ).to_csv(
        R / "v44_duration.csv",
        index=False
    )

    # --------------------------------------------------------
    # MFE / MAE
    # --------------------------------------------------------

    analyse(
        T, ["symbol", "interval"]
    ).to_csv(
        R / "v44_mae_mfe.csv",
        index=False
    )

    # --------------------------------------------------------
    # HEURE
    # --------------------------------------------------------

    analyse(
        T, ["hour_utc"]
    ).to_csv(
        R / "v44_hour.csv",
        index=False
    )

    # --------------------------------------------------------
    # RÉGIME
    # --------------------------------------------------------

    analyse(
        T, ["regime"]
    ).to_csv(
        R / "v44_regime.csv",
        index=False
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    analyse(
        T, ["signal"]
    ).to_csv(
        R / "v44_signal.csv",
        index=False
    )

    # --------------------------------------------------------
    # SYMBOL / TF
    # --------------------------------------------------------

    analyse(
        T, ["symbol", "interval"]
    ).to_csv(
        R / "v44_symbol_interval.csv",
        index=False
    )

    # --------------------------------------------------------
    # SIGNAL / SIDE
    # --------------------------------------------------------

    analyse(
        T, ["signal", "side"]
    ).to_csv(
        R / "v44_signal_side.csv",
        index=False
    )

    # --------------------------------------------------------
    # SIGNAL / EXIT
    # --------------------------------------------------------

    analyse(
        T, ["signal", "exit"]
    ).to_csv(
        R / "v44_signal_exit.csv",
        index=False
    )

    # --------------------------------------------------------
    # FOLD
    # --------------------------------------------------------

    analyse(
        T, ["symbol", "interval", "fold"]
    ).to_csv(
        R / "v44_fold.csv",
        index=False
    )

    # --------------------------------------------------------
    # TRAIN -> TEST
    # --------------------------------------------------------

    decay = (
        T.groupby(
            ["symbol", "interval", "fold"],
            dropna=False
        )
        .agg(
            train_mean=("train_mean", "first"),
            test_mean=("test_mean_fold", "first"),
            train_n=("train_n", "first"),
            edge=("edge_vs_random", "first"),
            trades=("net", "count"),
        )
        .reset_index()
    )

    decay["decay"] = (
        decay["test_mean"] -
        decay["train_mean"]
    )

    decay.to_csv(
        R / "v44_train_test_decay.csv",
        index=False
    )

    # --------------------------------------------------------
    # RÉSUMÉ
    # --------------------------------------------------------

    net = T.net.to_numpy(float)
    gross = T.gross.to_numpy(float)

    wins = net[net > 0]
    losses = net[net < 0]

    pf = (
        wins.sum() / abs(losses.sum())
        if len(losses) else np.inf
    )

    eq = np.cumprod(1 + net)
    peak = np.maximum.accumulate(eq)
    dd = np.min(eq / peak - 1)

    side = analyse(T, ["side"])
    exits = analyse(T, ["exit"])

    report = [
        "# SCALP LAB V4.4 — TRADE LEVEL FORENSICS",
        "",
        "V4.4 reprend les stratégies sélectionnées par V4.1.",
        "",
        "**Aucune nouvelle sélection n'est effectuée.**",
        "",
        "Le FINAL HOLDOUT reste totalement hors analyse OOS.",
        "",
        "## Global OOS",
        "",
        f"- Trades : {len(T)}",
        f"- Net moyen/trade : {pct(net.mean())}",
        f"- Médiane : {pct(np.median(net))}",
        f"- Gross moyen : {pct(gross.mean())}",
        f"- Coût moyen : {pct((gross-net).mean())}",
        f"- Win rate : {(net > 0).mean():.1%}",
        f"- PF : {pf:.2f}",
        f"- DD séquentiel : {pct(dd)}",
        "",
        "## LONG / SHORT",
        "",
        "| side | trades | mean | win | MFE | MAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for _, r in side.iterrows():
        report.append(
            f"| {r['side']} | {int(r['trades'])} | "
            f"{pct(r['mean_net'])} | {r['win_rate']:.1%} | "
            f"{pct(r['mean_mfe'])} | {pct(r['mean_mae'])} |"
        )

    report += [
        "",
        "## Sorties",
        "",
        "| sortie | trades | mean | win |",
        "|---|---:|---:|---:|",
    ]

    for _, r in exits.iterrows():
        report.append(
            f"| {r['exit']} | {int(r['trades'])} | "
            f"{pct(r['mean_net'])} | {r['win_rate']:.1%} |"
        )

    report += [
        "",
        "## Diagnostics",
        "",
        f"- Symboles : {T.symbol.nunique()}",
        f"- Intervalles : {T.interval.nunique()}",
        f"- Folds OOS observés : {T.fold.nunique()}",
        f"- Signaux : {T.signal.nunique()}",
        "",
        "## FINAL HOLDOUT",
        "",
        "Le holdout n'est pas utilisé pour cette analyse.",
        "Les 6 lignes FINAL de V4.1 restent intactes.",
        "",
        "## Fichiers",
        "",
        "- v44_trades_oos.csv",
        "- v44_long_short.csv",
        "- v44_exit_analysis.csv",
        "- v44_duration.csv",
        "- v44_mae_mfe.csv",
        "- v44_hour.csv",
        "- v44_regime.csv",
        "- v44_signal.csv",
        "- v44_symbol_interval.csv",
        "- v44_signal_side.csv",
        "- v44_signal_exit.csv",
        "- v44_fold.csv",
        "- v44_train_test_decay.csv",
        "",
        f"Temps : {(time.time()-t0):.1f}s",
    ]

    (R / "summary_v44.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("")
    print("=" * 72)
    print("V4.4 TERMINÉE")
    print("=" * 72)
    print(f"TRADES OOS : {len(T)}")
    print(f"MEAN       : {pct(net.mean())}")
    print(f"WIN RATE   : {(net > 0).mean():.1%}")
    print(f"PF         : {pf:.2f}")
    print(f"DD         : {pct(dd)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
