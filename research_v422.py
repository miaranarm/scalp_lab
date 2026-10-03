from pathlib import Path
import re

O=Path("results")
s17=(O/"summary_v417.md").read_text()
s18=(O/"summary_v418.md").read_text()
s19=(O/"summary_v419.md").read_text()
s20=(O/"summary_v420.md").read_text()
s21=(O/"summary_v421.md").read_text()

def first_float(p,s):
    m=re.search(p,s,re.M)
    return float(m.group(1)) if m else None

b1=first_float(r"^B1_ALL\s+\d+\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)",s17)
gap0=first_float(r"^\s*GAP0\s+\d+\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)",s17)
v18=first_float(r"^\s*all\s+\d+\s+(-?[\d.]+)\s+[\d.]+\s+(-?[\d.]+)",s18)
v19=first_float(r"^donchian n=50 vol=1\.5\s+\d+\s+(-?[\d.]+)",s19)
ci=first_float(r"^323\.0\s+(-?[\d.]+).*?(-?[\d.]+)\s*$",s19)
v20=first_float(r"^\s*25\s+pullback rsi=35\s+\d+\s+(-?[\d.]+)",s20)

# Parse the V4.21 final table.
rows=[]
in_final=False
for line in s21.splitlines():
    if line.strip()=="## FINAL HOLDOUT":
        in_final=True
        continue
    if in_final and line.startswith("| BTCUSDT") or in_final and line.startswith("| ETHUSDT") or in_final and line.startswith("| SOLUSDT"):
        if "symbol" in line or "---" in line: continue
        c=[x.strip() for x in line.strip("|").split("|")]
        if len(c)>=15:
            try:
                rows.append({"symbol":c[0],"interval":c[1],"n":int(c[9]),
                             "mean":float(c[10].replace("%",""))/100,
                             "ret":float(c[14].replace("%",""))/100})
            except: pass

n=sum(r["n"] for r in rows)
wm=sum(r["n"]*r["mean"] for r in rows)/n if n else 0
pos=sum(r["ret"]>0 for r in rows)

lines=[
"# SCALP LAB V4.22 — FINAL SURVIVORSHIP SYNTHESIS",
"",
"## Scope",
"- V4.17 → V4.21 are synthesized only; no new tuning is performed.",
"- FINAL HOLDOUT remains confirmation-only.",
"- No parameter, signal, regime, exit or threshold is selected from FINAL.",
"",
"## Sequential evidence",
"",
"| Audit | Evidence | Result |",
"|---|---|---|",
f"| V4.17 | B1_ALL mean | {b1:.4%} |",
f"| V4.17 | GAP0 retained B1 mean | {gap0:.4%} |",
"| V4.17 | Filtering improved the sample, but retained edge stayed negative | FAIL |",
f"| V4.18 | 2,196 trades / aggregate net | {v18:.4%} |",
f"| V4.19 | Donchian 50 vol1.5 mean | {v19:.4%} |",
f"| V4.19 | 95% CI upper bound for that signal | {ci:.4%} |",
f"| V4.20 | strongest aggregate candidate | {v20:.4%} |",
"| V4.20 | No candidate positive OOS globally | FAIL |",
"| V4.21 | FINAL holdout integrity | VALID |",
"",
"## FINAL HOLDOUT",
"",
f"- Blocks: {len(rows)}",
f"- Trades represented: {n}",
f"- Positive blocks: {pos}/{len(rows)}",
f"- Weighted mean/trade: {wm:.4%}",
]
for r in rows:
    lines.append(f"- {r['symbol']} {r['interval']}: {r['n']} trades, mean {r['mean']:+.4%}, return {r['ret']:+.2%}")

lines += [
"",
"## Survival verdict",
"",
"**NO SURVIVOR CONFIRMED.**",
"",
"- V4.17 showed selection improvement without turning the retained sample positive.",
"- V4.18 showed the raw signal family remained net negative after costs.",
"- V4.19 found no signal with a clearly positive 95% confidence interval.",
"- V4.20 found no candidate with positive aggregate OOS net.",
"- V4.21 confirmed the selected OOS configurations do not generalize to the FINAL holdout.",
"",
"## Methodological decision",
"",
"**STOP PARAMETER TUNING FOR THIS SIGNAL FAMILY UNDER THE CURRENT MODEL.**",
"",
"Further research should change the hypothesis rather than continue micro-optimizing the same VWAP / Donchian / breakout / pullback family. A new research branch should introduce a materially different source of edge, then restart with untouched OOS and FINAL holdout.",
"",
"## STATUS",
"",
"**VALID — SURVIVORSHIP SYNTHESIS COMPLETE. NO CONFIRMED EDGE.**",
]
(O/"summary_v422.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("\n".join(lines))
