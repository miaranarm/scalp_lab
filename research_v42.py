from pathlib import Path
import pandas as pd
import numpy as np

IN = Path("results")
OUT = IN

WF = IN / "walk_forward_v41.csv"
ST = IN / "stress_test_v41.csv"

def pct(x):
    return f"{x*100:.4f}%"

def num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)

def group_report(df, cols):
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(cols, dropna=False)
    return g.agg(
        folds=("fold","count"),
        mean_trade=("test_mean","mean"),
        median_trade=("test_mean","median"),
        pf_median=("test_pf","median"),
        dd_median=("test_dd","median"),
        trades=("test_n","sum"),
        positive=("test_mean", lambda x: int((x > 0).sum())),
        random_mean=("bench_random_mean","mean"),
    ).reset_index()

def add_edge(df):
    if df.empty:
        return df
    df = df.copy()
    df["edge_vs_random"] = df["test_mean"] - df["bench_random_mean"]
    df["better_random"] = df["edge_vs_random"] > 0
    return df

def save_group(df, cols, name):
    x = group_report(df, cols)
    if x.empty:
        return
    x["edge_vs_random"] = x["mean_trade"] - x["random_mean"]
    x.to_csv(OUT / name, index=False)

def main():
    print("="*70)
    print("SCALP LAB V4.2 — DIAGNOSTIC")
    print("="*70)

    if not WF.exists():
        raise SystemExit("ERREUR: results/walk_forward_v41.csv absent")

    wf = pd.read_csv(WF)

    print(f"ROWS {len(wf)}")

    # ----------------------------------------------------------
    # NORMALISATION
    # ----------------------------------------------------------
    for c in ["test_mean","test_pf","test_dd","test_n",
              "bench_random_mean","train_mean","train_pf","train_n"]:
        wf[c] = num(wf, c)

    wf = add_edge(wf)

    if "fold" in wf:
        oos = wf[wf["fold"].astype(str) != "FINAL"].copy()
        hold = wf[wf["fold"].astype(str) == "FINAL"].copy()
    else:
        oos = wf.copy()
        hold = pd.DataFrame()

    print(f"OOS {len(oos)}")
    print(f"HOLDOUT {len(hold)}")

    # ----------------------------------------------------------
    # 1. ANALYSE PAR DIMENSION
    # ----------------------------------------------------------
    save_group(
        oos, ["symbol"],
        "v42_by_symbol.csv"
    )

    save_group(
        oos, ["interval"],
        "v42_by_interval.csv"
    )

    save_group(
        oos, ["signal"],
        "v42_by_signal.csv"
    )

    save_group(
        oos, ["regime"],
        "v42_by_regime.csv"
    )

    save_group(
        oos, ["profile"],
        "v42_by_profile.csv"
    )

    save_group(
        oos, ["tp","sl","hold"],
        "v42_by_exit.csv"
    )

    save_group(
        oos, ["symbol","interval"],
        "v42_by_symbol_interval.csv"
    )

    save_group(
        oos, ["signal","regime"],
        "v42_by_signal_regime.csv"
    )

    save_group(
        oos, ["signal","interval"],
        "v42_by_signal_interval.csv"
    )

    # ----------------------------------------------------------
    # 2. STABILITE INTER-FOLDS
    # ----------------------------------------------------------
    stability = []

    for key, g in oos.groupby(
        ["symbol","interval","signal","regime","profile"],
        dropna=False
    ):
        vals = pd.to_numeric(g["test_mean"], errors="coerce").dropna()

        if len(vals) == 0:
            continue

        stability.append({
            "symbol": key[0],
            "interval": key[1],
            "signal": key[2],
            "regime": key[3],
            "profile": key[4],
            "folds": len(vals),
            "positive_folds": int((vals > 0).sum()),
            "positive_rate": float((vals > 0).mean()),
            "mean_trade": float(vals.mean()),
            "median_trade": float(vals.median()),
            "std_trade": float(vals.std(ddof=0)),
            "min_fold": float(vals.min()),
            "max_fold": float(vals.max()),
            "edge_random": float(
                g["edge_vs_random"].mean()
            ),
        })

    pd.DataFrame(stability).to_csv(
        OUT / "v42_stability.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 3. TRAIN -> TEST
    # ----------------------------------------------------------
    if "train_mean" in oos.columns:
        tt = oos.copy()

        tt["train_test_decay"] = (
            tt["test_mean"] - tt["train_mean"]
        )

        tt["train_positive"] = tt["train_mean"] > 0
        tt["test_positive"] = tt["test_mean"] > 0

        tt[
            [
                "symbol","interval","fold","signal","regime",
                "profile","tp","sl","hold",
                "train_n","train_mean","train_pf",
                "test_n","test_mean","test_pf",
                "train_test_decay","edge_vs_random"
            ]
        ].to_csv(
            OUT / "v42_train_test.csv",
            index=False
        )

    # ----------------------------------------------------------
    # 4. TRADE COUNT
    # ----------------------------------------------------------
    bins = [-1, 10, 25, 50, 100, 250, 1000, 999999]

    labels = [
        "0-10","11-25","26-50",
        "51-100","101-250","251-1000","1000+"
    ]

    x = oos.copy()
    x["trade_bucket"] = pd.cut(
        x["test_n"],
        bins=bins,
        labels=labels
    )

    tc = x.groupby(
        "trade_bucket",
        observed=False
    ).agg(
        folds=("fold","count"),
        mean_trade=("test_mean","mean"),
        pf_median=("test_pf","median"),
        dd_median=("test_dd","median"),
        edge_random=("edge_vs_random","mean"),
        positive=("test_mean", lambda z: int((z > 0).sum()))
    ).reset_index()

    tc.to_csv(
        OUT / "v42_trade_count.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 5. FINAL HOLDOUT — INFORMATION ONLY
    # ----------------------------------------------------------
    if not hold.empty:
        hold["edge_vs_random"] = (
            hold["test_mean"] -
            hold["bench_random_mean"]
        )

        hold.to_csv(
            OUT / "v42_holdout.csv",
            index=False
        )

    # ----------------------------------------------------------
    # 6. GLOBAL
    # ----------------------------------------------------------
    global_rows = []

    for label, df in [
        ("ALL_OOS", oos),
        ("5m", oos[oos["interval"] == "5m"]),
        ("15m", oos[oos["interval"] == "15m"]),
    ]:
        if df.empty:
            continue

        global_rows.append({
            "scope": label,
            "folds": len(df),
            "mean_trade": df["test_mean"].mean(),
            "median_trade": df["test_mean"].median(),
            "pf_median": df["test_pf"].median(),
            "dd_median": df["test_dd"].median(),
            "random_mean": df["bench_random_mean"].mean(),
            "edge_random": df["edge_vs_random"].mean(),
            "positive_folds": int(
                (df["test_mean"] > 0).sum()
            ),
            "better_random": int(
                (df["edge_vs_random"] > 0).sum()
            ),
            "total_trades": df["test_n"].sum(),
        })

    pd.DataFrame(global_rows).to_csv(
        OUT / "v42_global.csv",
        index=False
    )

    # ----------------------------------------------------------
    # 7. RAPPORT
    # ----------------------------------------------------------
    report = [
        "# SCALP LAB V4.2 — Diagnostic V4.1",
        "",
        "V4.2 analyse les résultats V4.1 sans modifier",
        "la sélection originale ni réutiliser le FINAL HOLDOUT.",
        "",
        "## OOS global",
        "",
    ]

    if not oos.empty:
        report += [
            f"- Folds OOS : {len(oos)}",
            f"- Mean/trade : {pct(oos.test_mean.mean())}",
            f"- Médiane trade : {pct(oos.test_mean.median())}",
            f"- PF médian : {oos.test_pf.median():.2f}",
            f"- DD médian : {pct(oos.test_dd.median())}",
            f"- Random : {pct(oos.bench_random_mean.mean())}",
            f"- Edge vs random : {pct(oos.edge_vs_random.mean())}",
            f"- Folds positifs : "
            f"{int((oos.test_mean > 0).sum())}/{len(oos)}",
            f"- Folds > random : "
            f"{int((oos.edge_vs_random > 0).sum())}/{len(oos)}",
            "",
        ]

    # ----------------------------------------------------------
    # TOP SIGNALS
    # ----------------------------------------------------------
    sig = group_report(oos, ["signal"])

    if not sig.empty:
        sig["edge_vs_random"] = (
            sig["mean_trade"] - sig["random_mean"]
        )

        sig = sig.sort_values(
            ["edge_vs_random","positive"],
            ascending=False
        )

        report += [
            "## Signal",
            "",
            "| signal | folds | mean | edge/random | +folds | PF |",
            "|---|---:|---:|---:|---:|---:|",
        ]

        for _, r in sig.head(20).iterrows():
            report.append(
                f"| {r['signal']} | {int(r['folds'])} | "
                f"{pct(r['mean_trade'])} | "
                f"{pct(r['edge_vs_random'])} | "
                f"{int(r['positive'])}/{int(r['folds'])} | "
                f"{r['pf_median']:.2f} |"
            )

        report.append("")

    # ----------------------------------------------------------
    # REGIMES
    # ----------------------------------------------------------
    reg = group_report(oos, ["regime"])

    if not reg.empty:
        reg["edge_vs_random"] = (
            reg["mean_trade"] - reg["random_mean"]
        )

        report += [
            "## Régimes",
            "",
            "| régime | folds | mean | edge/random | PF |",
            "|---|---:|---:|---:|---:|",
        ]

        for _, r in reg.iterrows():
            report.append(
                f"| {r['regime']} | {int(r['folds'])} | "
                f"{pct(r['mean_trade'])} | "
                f"{pct(r['edge_vs_random'])} | "
                f"{r['pf_median']:.2f} |"
            )

        report.append("")

    # ----------------------------------------------------------
    # INTERVALLES
    # ----------------------------------------------------------
    it = group_report(oos, ["interval"])

    if not it.empty:
        it["edge_vs_random"] = (
            it["mean_trade"] - it["random_mean"]
        )

        report += [
            "## Intervalles",
            "",
            "| intervalle | folds | mean | edge/random | PF |",
            "|---|---:|---:|---:|---:|",
        ]

        for _, r in it.iterrows():
            report.append(
                f"| {r['interval']} | {int(r['folds'])} | "
                f"{pct(r['mean_trade'])} | "
                f"{pct(r['edge_vs_random'])} | "
                f"{r['pf_median']:.2f} |"
            )

        report.append("")

    # ----------------------------------------------------------
    # HOLDOUT
    # ----------------------------------------------------------
    report += [
        "## FINAL HOLDOUT",
        "",
        "Le holdout est descriptif uniquement.",
        "Il n'intervient jamais dans la sélection V4.2.",
        "",
    ]

    if not hold.empty:
        for _, r in hold.iterrows():
            report.append(
                f"- {r['symbol']} {r['interval']} : "
                f"mean={pct(r['test_mean'])}, "
                f"PF={r['test_pf']:.2f}, "
                f"n={int(r['test_n'])}"
            )
    else:
        report.append("- absent")

    report += [
        "",
        "## Fichiers",
        "",
        "- v42_global.csv",
        "- v42_by_symbol.csv",
        "- v42_by_interval.csv",
        "- v42_by_signal.csv",
        "- v42_by_regime.csv",
        "- v42_by_profile.csv",
        "- v42_by_exit.csv",
        "- v42_by_symbol_interval.csv",
        "- v42_by_signal_regime.csv",
        "- v42_by_signal_interval.csv",
        "- v42_stability.csv",
        "- v42_train_test.csv",
        "- v42_trade_count.csv",
        "- v42_holdout.csv",
    ]

    (OUT / "summary_v42.md").write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    print("="*70)
    print("V4.2 TERMINÉE")
    print("="*70)
    print("RESULTS:")
    for p in sorted(OUT.glob("v42_*")):
        print(" ", p.name)
    print(" ", "summary_v42.md")


if __name__ == "__main__":
    main()
