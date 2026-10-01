from pathlib import Path
import pandas as pd
import numpy as np

R = Path("results")
WF = R / "walk_forward_v41.csv"

def pct(x):
    return "nan" if pd.isna(x) else f"{x*100:+.4f}%"

def fnum(df, col):
    if col not in df:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")

def analyse(df, keys):
    if df.empty:
        return pd.DataFrame()

    g = df.groupby(keys, dropna=False)

    x = g.agg(
        folds=("fold", "count"),
        mean=("test_mean", "mean"),
        median=("test_mean", "median"),
        std=("test_mean", "std"),
        min=("test_mean", "min"),
        max=("test_mean", "max"),
        pf=("test_pf", "median"),
        dd=("test_dd", "median"),
        trades=("test_n", "sum"),
        positive=("test_mean", lambda z: int((z > 0).sum())),
        random=("bench_random_mean", "mean"),
    ).reset_index()

    x["edge"] = x["mean"] - x["random"]
    x["positive_rate"] = x["positive"] / x["folds"]
    x["better_random"] = (
        df.groupby(keys, dropna=False)["edge_vs_random"]
        .apply(lambda z: int((z > 0).sum()))
        .values
    )

    x["better_random_rate"] = x["better_random"] / x["folds"]

    return x

def save(df, keys, filename):
    x = analyse(df, keys)
    x.to_csv(R / filename, index=False)
    return x

def main():
    print("=" * 72)
    print("SCALP LAB V4.3 — EDGE ISOLATION")
    print("=" * 72)

    if not WF.exists():
        raise SystemExit("ERREUR: results/walk_forward_v41.csv absent")

    df = pd.read_csv(WF)

    print(f"ROWS TOTAL : {len(df)}")

    # ----------------------------------------------------------
    # NUMERIC
    # ----------------------------------------------------------
    cols = [
        "test_mean",
        "test_median",
        "test_pf",
        "test_dd",
        "test_n",
        "bench_random_mean",
        "train_mean",
        "train_pf",
        "train_n",
    ]

    for c in cols:
        df[c] = fnum(df, c)

    df["edge_vs_random"] = (
        df["test_mean"] -
        df["bench_random_mean"]
    )

    # FINAL HOLDOUT NEVER USED FOR OOS ANALYSIS
    oos = df[df["fold"].astype(str) != "FINAL"].copy()
    hold = df[df["fold"].astype(str) == "FINAL"].copy()

    print(f"OOS : {len(oos)}")
    print(f"HOLDOUT : {len(hold)}")

    # ----------------------------------------------------------
    # 1. BASIC DIMENSIONS
    # ----------------------------------------------------------
    save(
        oos,
        ["symbol"],
        "v43_symbol.csv"
    )

    save(
        oos,
        ["interval"],
        "v43_interval.csv"
    )

    save(
        oos,
        ["signal"],
        "v43_signal.csv"
    )

    save(
        oos,
        ["regime"],
        "v43_regime.csv"
    )

    save(
        oos,
        ["profile"],
        "v43_profile.csv"
    )

    # ----------------------------------------------------------
    # 2. CROSS ANALYSIS
    # ----------------------------------------------------------
    save(
        oos,
        ["symbol", "interval"],
        "v43_symbol_interval.csv"
    )

    save(
        oos,
        ["signal", "regime"],
        "v43_signal_regime.csv"
    )

    save(
        oos,
        ["signal", "interval"],
        "v43_signal_interval.csv"
    )

    save(
        oos,
        ["signal", "symbol"],
        "v43_signal_symbol.csv"
    )

    save(
        oos,
        ["regime", "interval"],
        "v43_regime_interval.csv"
    )

    save(
        oos,
        ["signal", "regime", "interval"],
        "v43_signal_regime_interval.csv"
    )

    # ----------------------------------------------------------
    # 3. STABILITY
    # ----------------------------------------------------------
    rows = []

    group_cols = [
        "symbol",
        "interval",
        "signal",
        "regime"
    ]

    for key, g in oos.groupby(
        group_cols,
        dropna=False
    ):
        v = g["test_mean"].dropna()

        if len(v) == 0:
            continue

        edge = g["edge_vs_random"].dropna()

        rows.append({
            "symbol": key[0],
            "interval": key[1],
            "signal": key[2],
            "regime": key[3],
            "folds": len(v),
            "positive": int((v > 0).sum()),
            "positive_rate": float((v > 0).mean()),
            "mean": float(v.mean()),
            "median": float(v.median()),
            "std": float(v.std(ddof=0)),
            "min": float(v.min()),
            "max": float(v.max()),
            "edge_random": float(edge.mean())
                if len(edge) else np.nan,
            "better_random": int((edge > 0).sum())
                if len(edge) else 0,
        })

    stability = pd.DataFrame(rows)

    stability["stability_score"] = (
        stability["positive_rate"] * 0.35 +
        (
            stability["better_random"] /
            stability["folds"]
        ) * 0.35 +
        (
            stability["edge_random"].clip(-0.01, 0.01) /
            0.01
        ) * 0.30
    )

    stability = stability.sort_values(
        "stability_score",
        ascending=False
    )

    stability.to_csv(
        R / "v43_stability.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 4. TRAIN -> TEST DECAY
    # ----------------------------------------------------------
    if "train_mean" in oos:

        tt = oos.copy()

        tt["decay"] = (
            tt["test_mean"] -
            tt["train_mean"]
        )

        tt["train_positive"] = (
            tt["train_mean"] > 0
        )

        tt["test_positive"] = (
            tt["test_mean"] > 0
        )

        tt["edge_positive"] = (
            tt["edge_vs_random"] > 0
        )

        tt[
            [
                "symbol",
                "interval",
                "fold",
                "signal",
                "regime",
                "profile",
                "train_n",
                "train_mean",
                "train_pf",
                "test_n",
                "test_mean",
                "test_pf",
                "edge_vs_random",
                "decay",
                "train_positive",
                "test_positive",
                "edge_positive"
            ]
        ].to_csv(
            R / "v43_train_test.csv",
            index=False
        )

    # ----------------------------------------------------------
    # 5. TRADE COUNT
    # ----------------------------------------------------------
    bins = [
        -1,
        10,
        25,
        50,
        100,
        250,
        1000,
        999999999
    ]

    labels = [
        "0-10",
        "11-25",
        "26-50",
        "51-100",
        "101-250",
        "251-1000",
        "1000+"
    ]

    tc = oos.copy()

    tc["trade_bucket"] = pd.cut(
        tc["test_n"],
        bins=bins,
        labels=labels
    )

    trade = tc.groupby(
        "trade_bucket",
        observed=False
    ).agg(
        folds=("fold", "count"),
        mean=("test_mean", "mean"),
        median=("test_mean", "median"),
        pf=("test_pf", "median"),
        dd=("test_dd", "median"),
        edge=("edge_vs_random", "mean"),
        positive=("test_mean", lambda x: int((x > 0).sum()))
    ).reset_index()

    trade["positive_rate"] = (
        trade["positive"] /
        trade["folds"]
    )

    trade.to_csv(
        R / "v43_trade_count.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 6. TOP / BOTTOM COMBINATIONS
    # ----------------------------------------------------------
    combo = analyse(
        oos,
        [
            "symbol",
            "interval",
            "signal",
            "regime"
        ]
    )

    combo = combo.sort_values(
        ["edge", "positive_rate"],
        ascending=False
    )

    combo.to_csv(
        R / "v43_combinations.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 7. HOLDOUT COPY — DESCRIPTIVE ONLY
    # ----------------------------------------------------------
    if not hold.empty:
        hold["edge_vs_random"] = (
            hold["test_mean"] -
            hold["bench_random_mean"]
        )

        hold.to_csv(
            R / "v43_holdout.csv",
            index=False
        )

    # ----------------------------------------------------------
    # 8. GLOBAL
    # ----------------------------------------------------------
    global_rows = []

    for name, x in [
        ("ALL", oos),
        ("5m", oos[oos.interval == "5m"]),
        ("15m", oos[oos.interval == "15m"]),
        ("BTC", oos[oos.symbol == "BTCUSDT"]),
        ("ETH", oos[oos.symbol == "ETHUSDT"]),
        ("SOL", oos[oos.symbol == "SOLUSDT"]),
    ]:

        if x.empty:
            continue

        global_rows.append({
            "scope": name,
            "folds": len(x),
            "mean": x.test_mean.mean(),
            "median": x.test_mean.median(),
            "std": x.test_mean.std(ddof=0),
            "pf": x.test_pf.median(),
            "dd": x.test_dd.median(),
            "random": x.bench_random_mean.mean(),
            "edge": x.edge_vs_random.mean(),
            "positive": int(
                (x.test_mean > 0).sum()
            ),
            "positive_rate": float(
                (x.test_mean > 0).mean()
            ),
            "better_random": int(
                (x.edge_vs_random > 0).sum()
            ),
            "better_random_rate": float(
                (x.edge_vs_random > 0).mean()
            ),
            "trades": x.test_n.sum()
        })

    pd.DataFrame(global_rows).to_csv(
        R / "v43_global.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 9. REPORT
    # ----------------------------------------------------------
    report = [
        "# SCALP LAB V4.3 — EDGE ISOLATION",
        "",
        "V4.3 analyse uniquement les résultats V4.1.",
        "",
        "**Aucune nouvelle stratégie n'est optimisée.**",
        "",
        "Le FINAL HOLDOUT est conservé hors sélection.",
        "",
        "## Global OOS",
        "",
        f"- Folds : {len(oos)}",
        f"- Mean/trade : {pct(oos.test_mean.mean())}",
        f"- Médiane : {pct(oos.test_mean.median())}",
        f"- PF médian : {oos.test_pf.median():.2f}",
        f"- DD médian : {pct(oos.test_dd.median())}",
        f"- Random : {pct(oos.bench_random_mean.mean())}",
        f"- Edge : {pct(oos.edge_vs_random.mean())}",
        f"- Folds positifs : "
        f"{int((oos.test_mean > 0).sum())}/{len(oos)}",
        f"- Folds > random : "
        f"{int((oos.edge_vs_random > 0).sum())}/{len(oos)}",
        "",
    ]

    # ----------------------------------------------------------
    # BEST COMBINATIONS
    # ----------------------------------------------------------
    report += [
        "## Combinaisons OOS",
        "",
        "Les combinaisons ci-dessous sont descriptives.",
        "Elles ne constituent pas une sélection de trading.",
        "",
        "| symbole | TF | signal | régime | folds | mean | edge | +folds | PF |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]

    for _, r in combo.head(15).iterrows():
        report.append(
            f"| {r['symbol']} | {r['interval']} | "
            f"{r['signal']} | {r['regime']} | "
            f"{int(r['folds'])} | "
            f"{pct(r['mean'])} | "
            f"{pct(r['edge'])} | "
            f"{int(r['positive'])}/{int(r['folds'])} | "
            f"{r['pf']:.2f} |"
        )

    report += [
        "",
        "## Combinaisons les plus faibles",
        "",
        "| symbole | TF | signal | régime | folds | mean | edge | PF |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]

    for _, r in combo.tail(10).iterrows():
        report.append(
            f"| {r['symbol']} | {r['interval']} | "
            f"{r['signal']} | {r['regime']} | "
            f"{int(r['folds'])} | "
            f"{pct(r['mean'])} | "
            f"{pct(r['edge'])} | "
            f"{r['pf']:.2f} |"
        )

    # ----------------------------------------------------------
    # STABILITY
    # ----------------------------------------------------------
    report += [
        "",
        "## Stabilité",
        "",
        "Top combinaisons avec plusieurs observations :",
        "",
        "| symbole | TF | signal | régime | folds | + | edge | score |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]

    stab = stability[
        stability["folds"] >= 3
    ].head(15)

    for _, r in stab.iterrows():
        report.append(
            f"| {r['symbol']} | {r['interval']} | "
            f"{r['signal']} | {r['regime']} | "
            f"{int(r['folds'])} | "
            f"{int(r['positive'])}/{int(r['folds'])} | "
            f"{pct(r['edge_random'])} | "
            f"{r['stability_score']:.3f} |"
        )

    # ----------------------------------------------------------
    # HOLDOUT
    # ----------------------------------------------------------
    report += [
        "",
        "## FINAL HOLDOUT",
        "",
        "Le holdout reste strictement descriptif.",
        "",
    ]

    if not hold.empty:
        for _, r in hold.iterrows():
            report.append(
                f"- {r['symbol']} {r['interval']} : "
                f"{pct(r['test_mean'])}, "
                f"PF={r['test_pf']:.2f}, "
                f"n={int(r['test_n'])}"
            )

    # ----------------------------------------------------------
    # LIMITATION IMPORTANT
    # ----------------------------------------------------------
    report += [
        "",
        "## Limitation",
        "",
        "Le fichier walk_forward_v41.csv ne contient pas les trades "
        "individuels. V4.3 ne prétend donc pas analyser séparément "
        "LONG/SHORT ni la distribution trade par trade.",
        "",
        "Une analyse LONG/SHORT et trade-level nécessitera une nouvelle "
        "sortie de recherche dédiée, sans toucher au FINAL HOLDOUT.",
        "",
        "## Fichiers",
        "",
        "- v43_global.csv",
        "- v43_symbol.csv",
        "- v43_interval.csv",
        "- v43_signal.csv",
        "- v43_regime.csv",
        "- v43_profile.csv",
        "- v43_symbol_interval.csv",
        "- v43_signal_regime.csv",
        "- v43_signal_interval.csv",
        "- v43_signal_symbol.csv",
        "- v43_regime_interval.csv",
        "- v43_signal_regime_interval.csv",
        "- v43_stability.csv",
        "- v43_train_test.csv",
        "- v43_trade_count.csv",
        "- v43_combinations.csv",
        "- v43_holdout.csv",
    ]

    (R / "summary_v43.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("=" * 72)
    print("V4.3 TERMINÉE")
    print("=" * 72)
    print(f"OOS       : {len(oos)}")
    print(f"HOLDOUT   : {len(hold)}")
    print(f"MEAN      : {pct(oos.test_mean.mean())}")
    print(f"RANDOM    : {pct(oos.bench_random_mean.mean())}")
    print(f"EDGE      : {pct(oos.edge_vs_random.mean())}")
    print("=" * 72)

if __name__ == "__main__":
    main()
