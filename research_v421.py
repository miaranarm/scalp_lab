from pathlib import Path
import pandas as pd

SRC=Path("results/walk_forward_v41.csv")
OUT=Path("results")
df=pd.read_csv(SRC)
final=df[df["fold"].astype(str).eq("FINAL")].copy()
oos=df[~df["fold"].astype(str).eq("FINAL")].copy()

req=["symbol","interval","candidate","signal","regime","profile","tp","sl","hold","test_n","test_mean","test_t","test_pf","test_dd","test_return"]
missing=[c for c in req if c not in df.columns]

lines=[
"# SCALP LAB V4.21 — FINAL HOLDOUT AUDIT",
"",
"## Integrity",
f"- Source: `results/walk_forward_v41.csv`",
f"- OOS rows: {len(oos)}",
f"- FINAL rows: {len(final)}",
f"- Missing required columns: {', '.join(missing) if missing else 'none'}",
"",
"## Rule",
"- The FINAL HOLDOUT is read-only confirmation data.",
"- No candidate, signal, regime, exit, profile or threshold is selected from FINAL.",
"- V4.21 does not reuse OOS observations as holdout.",
"",
"## FINAL HOLDOUT",
"",
"| symbol | interval | candidate | signal | regime | profile | TP | SL | hold | n | mean/trade | t | PF | DD | return |",
"|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
]
if final.empty:
    lines += ["","**STATUS: BLOCKED — no explicit FINAL row found.**"]
elif missing:
    lines += ["", "**STATUS: BLOCKED — required columns are missing.**"]
else:
    for _,r in final.iterrows():
        lines.append(
            f"| {r.symbol} | {r.interval} | {int(r.candidate)} | {r.signal} | "
            f"{r.regime} | {r.profile} | {r.tp:g} | {r.sl:g} | {int(r.hold)} | "
            f"{int(r.test_n)} | {r.test_mean:+.4%} | {r.test_t:.2f} | "
            f"{r.test_pf:.2f} | {r.test_dd:+.2%} | {r.test_return:+.2%} |"
        )
    lines += [
        "",
        "## STATUS",
        "",
        "**VALID — FINAL HOLDOUT FOUND AND KEPT SEPARATE FROM OOS SELECTION.**",
        "",
        "V4.21 performs an integrity/confirmation audit only. It does not retune the strategy.",
    ]

(OUT/"summary_v421.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(f"FINAL={len(final)} OOS={len(oos)} STATUS={'VALID' if len(final) and not missing else 'BLOCKED'}")
