"""
SCALP LAB V4 — laboratoire de recherche scalping Binance USD-M.

Objectif :
- recherche compacte et reproductible
- TRAIN -> sélection
- TEST -> validation OOS
- FINAL HOLDOUT -> confirmation finale, jamais utilisé pour sélectionner
- benchmarks simples
- décomposition gross edge / fees / slippage
- stress coûts + Monte-Carlo
- aucune exécution réelle

Données :
Binance Futures USD-M
Entrée 5m / 15m
Contexte 1h
Signal clôturé -> entrée suivante
"""

from __future__ import annotations

import argparse, io, math, os, time, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://data.binance.vision/data/futures/um"
INTERVAL_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}

FEE_TAKER = 0.0005
FEE_MAKER = 0.0002
THROUGH = 0.00005

SLIP = {
    "BTCUSDT": 0.00010,
    "ETHUSDT": 0.00015,
    "SOLUSDT": 0.00030,
}
DEFAULT_SLIP = 0.00030

EXITS = (
    (1.5, 1.0, 12),
    (2.0, 1.0, 24),
    (3.0, 1.5, 36),
    (2.0, 2.0, 24),
)

PROFILES = ("taker", "maker_tp", "maker_both")

TRAIN_DAYS = 180
TEST_DAYS = 45
FINAL_HOLDOUT_DAYS = 45
STEP_DAYS = 45

MIN_TRAIN_TRADES = 50
MC_RUNS = 5000
MC_SEED = 20260928

DEFAULT_CAPITAL = 100.0

# V4 : moins de degrés de liberté que V3
SIGNALS = (
    ("vwap", {"n": 48, "k": 2.0}),
    ("vwap", {"n": 96, "k": 2.0}),
    ("vwap", {"n": 48, "k": 3.0}),
    ("donchian", {"n": 20, "vol": 0.0}),
    ("donchian", {"n": 20, "vol": 1.5}),
    ("donchian", {"n": 50, "vol": 1.5}),
    ("zscore", {"n": 30, "thr": 2.0}),
    ("zscore", {"n": 60, "thr": 2.5}),
    ("pullback", {"rsi": 35}),
    ("pullback", {"rsi": 40}),
    ("breakout", {"n": 20}),
)

# Contextes simples, sans multiplication des combinaisons
REGIMES = ("all", "trend", "range")


# ============================================================
# DATA
# ============================================================

def read_zip_csv(content: bytes):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        raw = z.read(name).decode("utf-8")
    return [
        r[:12] for r in (x.split(",") for x in raw.splitlines())
        if r and r[0].isdigit()
    ]


def fetch_vision(symbol: str, interval: str, start_ms: int, end_ms: int):
    rows, step = [], INTERVAL_MS[interval]
    start_dt = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    cur = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    while cur < end_dt:
        if cur.month == 12:
            nxt = cur.replace(
                year=cur.year + 1, month=1
            )
        else:
            nxt = cur.replace(month=cur.month + 1)

        a = max(cur.timestamp() * 1000, start_ms)
        b = min(nxt.timestamp() * 1000 - step, end_ms)

        if a <= b:
            url = (
                f"{BASE_URL}/monthly/klines/{symbol}/{interval}/"
                f"{symbol}-{interval}-{cur:%Y-%m}.zip"
            )
            try:
                r = requests.get(url, timeout=90)
                if r.ok:
                    rows.extend(read_zip_csv(r.content))
                else:
                    # current month may only exist in daily archive
                    day = datetime.fromtimestamp(a / 1000, timezone.utc).date()
                    last = datetime.fromtimestamp(b / 1000, timezone.utc).date()
                    while day <= last:
                        u = (
                            f"{BASE_URL}/daily/klines/{symbol}/{interval}/"
                            f"{symbol}-{interval}-{day}.zip"
                        )
                        try:
                            q = requests.get(u, timeout=90)
                            if q.ok:
                                rows.extend(read_zip_csv(q.content))
                        except requests.RequestException:
                            pass
                        day += pd.Timedelta(days=1)
            except requests.RequestException:
                pass

        cur = nxt

    return rows


def to_frame(rows):
    cols = ["time", "open", "high", "low", "close", "volume",
            "x", "q", "n", "tb", "tq", "i"]
    d = pd.DataFrame(rows, columns=cols)
    for c in cols[:6]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = (
        d.dropna(subset=cols[:6])
         .drop_duplicates("time")
         .sort_values("time")
         .reset_index(drop=True)
    )
    return d


# ============================================================
# FEATURES
# ============================================================

def make_features(d):
    c, h, l, v = (
        d["close"], d["high"], d["low"], d["volume"]
    )

    prev = c.shift()
    tr = pd.concat([
        h - l,
        (h - prev).abs(),
        (l - prev).abs()
    ], axis=1).max(axis=1)

    delta = c.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)

    avg_up = up.ewm(alpha=1 / 14, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)

    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    ema9 = c.ewm(span=9, adjust=False).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()

    mean20 = c.rolling(20).mean()
    sd20 = c.rolling(20).std()
    z = (c - mean20) / sd20.replace(0, np.nan)

    vmean = v.rolling(20).mean()
    typical = (h + l + c) / 3

    out = {
        "c": c.to_numpy(float),
        "h": h.to_numpy(float),
        "l": l.to_numpy(float),
        "v": v.to_numpy(float),
        "rsi": (100 - 100 / (1 + rs)).to_numpy(float),
        "atr": atr.to_numpy(float),
        "ema9": ema9.to_numpy(float),
        "ema20": ema20.to_numpy(float),
        "ema50": ema50.to_numpy(float),
        "ema200": ema200.to_numpy(float),
        "z20": z.to_numpy(float),
        "vol_ratio": (v / vmean.replace(0, np.nan)).to_numpy(float),
        "vwap48": (
            (typical * v).rolling(48).sum() /
            v.rolling(48).sum()
        ).to_numpy(float),
        "vwap96": (
            (typical * v).rolling(96).sum() /
            v.rolling(96).sum()
        ).to_numpy(float),
        "atr_pct": (atr / c).to_numpy(float),
        "ret": c.pct_change().to_numpy(float),
    }

    out["ema20_slope"] = ema20.pct_change(6).to_numpy(float)
    out["ema50_slope"] = ema50.pct_change(12).to_numpy(float)
    out["ema_sep"] = ((ema20 - ema50) / c).to_numpy(float)
    out["dist200"] = ((c - ema200) / ema200).to_numpy(float)

    return out


def align_1h(entry, h1):
    f = make_features(h1)
    x = pd.DataFrame({
        "time": h1["time"].to_numpy(),
        **{k: f[k] for k in (
            "c", "ema20", "ema50", "ema200",
            "atr", "rsi", "ema20_slope",
            "ema50_slope", "ema_sep", "dist200"
        )}
    })

    # disponibilité uniquement après clôture de la bougie 1h
    x["time"] += INTERVAL_MS["1h"]

    e = pd.DataFrame({"time": entry["time"].to_numpy()})
    return pd.merge_asof(
        e.sort_values("time"),
        x.sort_values("time"),
        on="time",
        direction="backward",
    )


def context_masks(entry, h1):
    a = align_1h(entry, h1)

    c = a["c"].to_numpy(float)
    e20 = a["ema20"].to_numpy(float)
    e50 = a["ema50"].to_numpy(float)
    e200 = a["ema200"].to_numpy(float)
    s20 = a["ema20_slope"].to_numpy(float)
    s50 = a["ema50_slope"].to_numpy(float)
    sep = a["ema_sep"].to_numpy(float)
    d200 = a["dist200"].to_numpy(float)

    valid = np.isfinite(
        np.column_stack([c, e20, e50, e200, s20, s50, sep, d200])
    ).all(axis=1)

    trend_up = (
        valid & (e20 > e50) & (c > e200) &
        (sep >= 0.0025) & (d200 <= 0.045)
    )
    trend_down = (
        valid & (e20 < e50) & (c < e200) &
        (sep <= -0.0025) & (d200 >= -0.045)
    )

    trend = trend_up | trend_down
    rng = valid & (np.abs(sep) < 0.0025) & (np.abs(d200) < 0.02)

    return {
        "all": valid,
        "trend": trend,
        "range": rng,
        "trend_up": trend_up,
        "trend_down": trend_down,
    }, a


# ============================================================
# SIGNALS
# ============================================================

@dataclass
class Candidate:
    name: str
    signal: np.ndarray
    regime: str


def sig(long, short):
    x = np.zeros(len(long), dtype=np.int8)
    x[long] = 1
    x[short] = -1
    return x


def build_signal(name, p, f):
    c, h, l = f["c"], f["h"], f["l"]

    if name == "vwap":
        vw = f[f"vwap{p['n']}"]
        dist = (c - vw) / f["atr"]
        return sig(dist < -p["k"], dist > p["k"])

    if name == "donchian":
        n = p["n"]
        hi = pd.Series(h).rolling(n).max().shift(1).to_numpy()
        lo = pd.Series(l).rolling(n).min().shift(1).to_numpy()
        vr = f["vol_ratio"]
        return sig(
            (c > hi) & (vr > p["vol"]),
            (c < lo) & (vr > p["vol"])
        )

    if name == "zscore":
        z = pd.Series(c).rolling(p["n"]).mean()
        sd = pd.Series(c).rolling(p["n"]).std()
        zz = ((pd.Series(c) - z) / sd.replace(0, np.nan)).to_numpy()
        return sig(zz < -p["thr"], zz > p["thr"])

    if name == "pullback":
        r = f["rsi"]
        up = (f["ema20"] > f["ema50"]) & (c > f["ema200"])
        dn = (f["ema20"] < f["ema50"]) & (c < f["ema200"])
        return sig(up & (r < p["rsi"]), dn & (r > 100 - p["rsi"]))

    if name == "breakout":
        n = p["n"]
        hi = pd.Series(h).rolling(n).max().shift(1).to_numpy()
        lo = pd.Series(l).rolling(n).min().shift(1).to_numpy()
        atrp = f["atr_pct"]
        base = pd.Series(atrp).rolling(50).mean().to_numpy()
        exp = atrp > base
        return sig((c > hi) & exp, (c < lo) & exp)

    raise ValueError(name)


def make_candidates(entry, h1):
    f = make_features(entry)
    masks, ctx = context_masks(entry, h1)
    result = []

    for name, p in SIGNALS:
        base = build_signal(name, p, f)

        for regime in REGIMES:
            m = masks[regime].copy()
            s = base.copy()
            s[~m] = 0

            # range : conserver les deux directions
            # trend : conserver les deux directions
            # all : conserver les deux directions
            if not np.any(s):
                continue

            label = name + "".join(
                f" {k}={v}" for k, v in p.items()
            )

            result.append(Candidate(label, s, regime))

    return f, result


# ============================================================
# SIMULATION
# ============================================================

def simulate(L, signal, tp_m, sl_m, hold, profile, slip, fee_scale=1.0,
             slip_scale=1.0):
    c, h, lo, atr = L["c"], L["h"], L["l"], L["atr"]
    fee = (FEE_MAKER if profile != "taker" else FEE_TAKER) * fee_scale
    slip *= slip_scale

    trades = []
    free = 0

    for j in np.flatnonzero(signal):
        if j < free or j + 1 >= len(c) or not np.isfinite(atr[j]):
            continue

        side = int(signal[j])
        a = atr[j]
        if a <= 0:
            continue

        if profile == "maker_both":
            if side == 1:
                if lo[j + 1] > c[j] * (1 - THROUGH):
                    continue
                entry = c[j]
            else:
                if h[j + 1] < c[j] * (1 + THROUGH):
                    continue
                entry = c[j]
            entry_fee = FEE_MAKER * fee_scale
        else:
            entry = c[j + 1] * (1 + side * slip)
            entry_fee = FEE_TAKER * fee_scale

        tp = entry + side * tp_m * a
        sl = entry - side * sl_m * a
        end = min(j + hold, len(c) - 1)

        exit_i = end
        exit_px = c[end]
        kind = "time"

        for k in range(j + 1, end + 1):
            hit_tp = h[k] >= tp if side == 1 else lo[k] <= tp
            hit_sl = lo[k] <= sl if side == 1 else h[k] >= sl

            if hit_sl:
                exit_i, exit_px, kind = k, sl * (1 - side * slip), "sl"
                break

            if hit_tp:
                if profile in ("maker_tp", "maker_both"):
                    exit_px, kind = tp, "tp"
                else:
                    exit_px, kind = tp * (1 - side * slip), "tp"
                exit_i = k
                break

        if kind == "time":
            exit_px *= 1 - side * slip

        exit_fee = (
            FEE_MAKER if kind == "tp" and profile != "taker"
            else FEE_TAKER
        ) * fee_scale

        gross = side * (exit_px - entry) / entry
        net = (1 + gross) * (1 - entry_fee) * (1 - exit_fee) - 1

        trades.append({
            "signal_i": j,
            "entry_i": j + 1,
            "exit_i": exit_i,
            "gross": gross,
            "net": net,
            "kind": kind,
            "side": side,
            "duration": exit_i - j,
        })

        free = exit_i + 1

    return trades


def inside(trades, start, end):
    return [
        t for t in trades
        if start <= t["signal_i"] < end
        and start <= t["entry_i"] < end
        and t["exit_i"] < end
    ]


# ============================================================
# STATISTICS
# ============================================================

def stats(trades):
    if not trades:
        return {
            "n": 0, "mean": np.nan, "gross": np.nan,
            "fees": np.nan, "slip": np.nan,
            "win": np.nan, "pf": np.nan,
            "median": np.nan, "p25": np.nan, "p75": np.nan,
            "dd": np.nan, "ret": np.nan,
        }

    net = np.array([t["net"] for t in trades], float)
    gross = np.array([t["gross"] for t in trades], float)

    eq = np.cumprod(1 + net)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1

    wins = net[net > 0]
    losses = net[net < 0]

    pf = np.sum(wins) / abs(np.sum(losses)) if len(losses) else np.inf

    # approximation analytique de l'impact coûts
    gross_mean = gross.mean()
    net_mean = net.mean()
    cost_mean = gross_mean - net_mean

    return {
        "n": len(net),
        "mean": net_mean,
        "gross": gross_mean,
        "fees": cost_mean,
        "slip": 0.0,
        "win": float(np.mean(net > 0)),
        "pf": pf,
        "median": np.median(net),
        "p25": np.percentile(net, 25),
        "p75": np.percentile(net, 75),
        "dd": dd.min(),
        "ret": eq[-1] - 1,
    }


def score(s):
    if s["n"] < MIN_TRAIN_TRADES:
        return -np.inf

    pf = 2 if np.isinf(s["pf"]) else np.clip(s["pf"] - 1, -1, 2)
    mean = np.clip(s["mean"] * 1000, -2, 2)
    dd = np.clip(abs(s["dd"]) * 10, 0, 2)
    return 0.50 * mean + 0.30 * pf + 0.20 * min(
        math.log1p(s["n"]) / 6, 1
    ) - 0.15 * dd


def monte_carlo(trades, capital, runs=MC_RUNS, seed=MC_SEED):
    if len(trades) < 20:
        return {"median": np.nan, "p05": np.nan, "p95": np.nan,
                "dd": np.nan}

    rng = np.random.default_rng(seed)
    r = np.array([t["net"] for t in trades], float)
    finals, dds = [], []

    for _ in range(runs):
        x = rng.choice(r, len(r), replace=True)
        eq = capital * np.cumprod(1 + x)
        peak = np.maximum.accumulate(eq)
        finals.append(eq[-1])
        dds.append(np.min(eq / peak - 1))

    return {
        "median": np.median(finals),
        "p05": np.percentile(finals, 5),
        "p95": np.percentile(finals, 95),
        "dd": np.median(dds),
    }


# ============================================================
# BENCHMARKS
# ============================================================

def benchmark_fixed(L, start, end, hold=12):
    """Entrée mécanique toutes les `hold` bougies."""
    signal = np.zeros(len(L["c"]), dtype=np.int8)
    signal[start:end:hold] = 1
    return simulate(
        L, signal, 2.0, 1.0, hold,
        "taker", DEFAULT_SLIP
    )


def benchmark_buy_hold(L, start, end):
    if end <= start + 1:
        return []

    entry = L["c"][start]
    exit_ = L["c"][end - 1]
    gross = exit_ / entry - 1
    fee = FEE_TAKER * 2
    net = (1 + gross) * (1 - fee) ** 2 - 1

    return [{
        "signal_i": start,
        "entry_i": start,
        "exit_i": end - 1,
        "gross": gross,
        "net": net,
        "kind": "benchmark",
        "side": 1,
        "duration": end - start,
    }]


# ============================================================
# WALK FORWARD
# ============================================================

def make_folds(n, interval):
    bars = int(86_400_000 / INTERVAL_MS[interval])
    train = TRAIN_DAYS * bars
    test = TEST_DAYS * bars

    # dernier bloc réservé au FINAL HOLDOUT
    holdout = FINAL_HOLDOUT_DAYS * bars
    usable = n - holdout

    folds = []
    s = 0

    while s + train + test <= usable:
        folds.append((s, s + train, s + train, s + train + test))
        s += STEP_DAYS * bars

    final_start = usable
    return folds, final_start


# ============================================================
# STRESS
# ============================================================

def stress(L, candidate, spec, start, end, symbol):
    scenarios = {
        "base": (1.0, 1.0),
        "fees+25%": (1.25, 1.0),
        "fees+50%": (1.50, 1.0),
        "fees+100%": (2.00, 1.0),
        "slip+50%": (1.0, 1.50),
        "slip+100%": (1.0, 2.00),
        "fees+50%_slip+100%": (1.50, 2.00),
    }

    out = []

    for name, (fs, ss) in scenarios.items():
        tr = simulate(
            L, candidate.signal,
            spec["tp"], spec["sl"], spec["hold"],
            spec["profile"],
            SLIP.get(symbol, DEFAULT_SLIP),
            fs, ss
        )
        tr = inside(tr, start, end)
        z = stats(tr)

        out.append({
            "scenario": name,
            "symbol": symbol,
            "mean": z["mean"],
            "pf": z["pf"],
            "win": z["win"],
            "dd": z["dd"],
            "n": z["n"],
            "return": z["ret"],
        })

    return out


# ============================================================
# REPORT
# ============================================================

def pct(x):
    return "nan" if not np.isfinite(x) else f"{x * 100:+.4f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--intervals", default="5m,15m")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    ap.add_argument("--mc-runs", type=int, default=MC_RUNS)
    args = ap.parse_args()

    t0 = time.time()
    outdir = Path("results")
    outdir.mkdir(exist_ok=True)

    for f in (
        "walk_forward_v4.csv",
        "stress_test_v4.csv",
        "summary_v4.md",
    ):
        p = outdir / f
        if p.exists():
            p.unlink()

    symbols = [x.strip() for x in args.symbols.split(",") if x.strip()]
    intervals = [x.strip() for x in args.intervals.split(",") if x.strip()]

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - args.days * 86_400_000

    rows, stresses = [], []
    log = []

    def say(s):
        print(s)
        log.append(s)

    say("# SCALP LAB V4")
    say("Binance USD-M | signal clôturé -> entrée suivante | contexte 1h")
    say(
        f"WF={TRAIN_DAYS}j/{TEST_DAYS}j/{STEP_DAYS}j | "
        f"FINAL HOLDOUT={FINAL_HOLDOUT_DAYS}j"
    )
    say(
        f"Coûts taker={FEE_TAKER:.2%} | maker={FEE_MAKER:.2%} | "
        f"candidats réduits={len(SIGNALS)} familles/configurations"
    )
    say("")

    for interval in intervals:
        for symbol in symbols:
            t_pair = time.time()

            entry = to_frame(
                fetch_vision(symbol, interval, start_ms, end_ms)
            )
            h1 = to_frame(
                fetch_vision(symbol, "1h", start_ms - 2 * 86_400_000, end_ms)
            )

            if len(entry) < 20_000 or len(h1) < 500:
                say(f"{symbol} {interval} | données insuffisantes")
                continue

            entry = entry[entry.time >= start_ms].reset_index(drop=True)

            folds, holdout_start = make_folds(len(entry), interval)
            ef, candidates = make_candidates(entry, h1)

            L = ef

            say(
                f"{symbol} {interval} | {len(entry)} candles | "
                f"{len(candidates)} candidats | "
                f"{len(folds)} folds | holdout={FINAL_HOLDOUT_DAYS}j"
            )

            for fi, (tr0, tr1, te0, te1) in enumerate(folds, 1):
                best = None

                for ci, cand in enumerate(candidates):
                    for tp, sl, hold in EXITS:
                        for profile in PROFILES:
                            all_trades = simulate(
                                L, cand.signal, tp, sl, hold,
                                profile,
                                SLIP.get(symbol, DEFAULT_SLIP)
                            )

                            train = inside(all_trades, tr0, tr1)
                            st = stats(train)
                            sc = score(st)

                            if best is None or sc > best["score"]:
                                best = {
                                    "candidate_i": ci,
                                    "candidate": cand,
                                    "tp": tp,
                                    "sl": sl,
                                    "hold": hold,
                                    "profile": profile,
                                    "score": sc,
                                    "train": st,
                                }

                if best is None:
                    continue

                test_trades = inside(
                    simulate(
                        L,
                        best["candidate"].signal,
                        best["tp"],
                        best["sl"],
                        best["hold"],
                        best["profile"],
                        SLIP.get(symbol, DEFAULT_SLIP),
                    ),
                    te0, te1
                )

                ts = stats(test_trades)
                mc = monte_carlo(
                    test_trades,
                    args.capital,
                    args.mc_runs,
                    MC_SEED + fi
                )

                bench = benchmark_fixed(L, te0, te1)
                bs = stats(bench)

                bh = benchmark_buy_hold(L, te0, te1)
                bhs = stats(bh)

                spec = {
                    "tp": best["tp"],
                    "sl": best["sl"],
                    "hold": best["hold"],
                    "profile": best["profile"],
                }

                stress_rows = stress(
                    L, best["candidate"], spec,
                    te0, te1, symbol
                )
                stresses.extend(
                    [{**x, "interval": interval, "fold": fi}
                     for x in stress_rows]
                )

                rows.append({
                    "symbol": symbol,
                    "interval": interval,
                    "fold": fi,
                    "candidate": best["candidate_i"],
                    "signal": best["candidate"].name,
                    "regime": best["candidate"].regime,
                    "profile": best["profile"],
                    "tp": best["tp"],
                    "sl": best["sl"],
                    "hold": best["hold"],
                    "train_n": best["train"]["n"],
                    "train_mean": best["train"]["mean"],
                    "train_pf": best["train"]["pf"],
                    "test_n": ts["n"],
                    "test_gross": ts["gross"],
                    "test_mean": ts["mean"],
                    "test_fees": ts["fees"],
                    "test_win": ts["win"],
                    "test_pf": ts["pf"],
                    "test_median": ts["median"],
                    "test_p25": ts["p25"],
                    "test_p75": ts["p75"],
                    "test_dd": ts["dd"],
                    "test_return": ts["ret"],
                    "mc_median": mc["median"],
                    "mc_p05": mc["p05"],
                    "mc_p95": mc["p95"],
                    "mc_dd": mc["dd"],
                    "bench_fixed_mean": bs["mean"],
                    "bench_fixed_pf": bs["pf"],
                    "bench_bh_return": bhs["ret"],
                })

                say(
                    f"  F{fi} {best['candidate'].name} / "
                    f"{best['candidate'].regime} / {best['profile']} | "
                    f"TEST {pct(ts['mean'])} | PF={ts['pf']:.2f} | "
                    f"DD={pct(ts['dd'])} | n={ts['n']}"
                )

            # ------------------------------------------------
            # FINAL HOLDOUT
            # ------------------------------------------------
            if holdout_start < len(entry):
                # IMPORTANT :
                # aucune nouvelle sélection ici.
                # On prend la stratégie majoritaire parmi les folds.
                pair_rows = [
                    x for x in rows
                    if x["symbol"] == symbol
                    and x["interval"] == interval
                ]

                if pair_rows:
                    key = lambda x: (
                        x["signal"],
                        x["regime"],
                        x["profile"],
                        x["tp"],
                        x["sl"],
                        x["hold"],
                    )

                    from collections import Counter

                    chosen = Counter(
                        key(x) for x in pair_rows
                    ).most_common(1)[0][0]

                    match = next(
                        x for x in pair_rows if key(x) == chosen
                    )

                    cand = candidates[match["candidate"]]

                    spec = {
                        "tp": match["tp"],
                        "sl": match["sl"],
                        "hold": match["hold"],
                        "profile": match["profile"],
                    }

                    hold_trades = inside(
                        simulate(
                            L,
                            cand.signal,
                            spec["tp"],
                            spec["sl"],
                            spec["hold"],
                            spec["profile"],
                            SLIP.get(symbol, DEFAULT_SLIP)
                        ),
                        holdout_start,
                        len(entry)
                    )

                    hs = stats(hold_trades)
                    hmc = monte_carlo(
                        hold_trades,
                        args.capital,
                        args.mc_runs,
                        MC_SEED + 999
                    )

                    rows.append({
                        "symbol": symbol,
                        "interval": interval,
                        "fold": "FINAL",
                        "candidate": match["candidate"],
                        "signal": match["signal"],
                        "regime": match["regime"],
                        "profile": match["profile"],
                        "tp": match["tp"],
                        "sl": match["sl"],
                        "hold": match["hold"],
                        "train_n": np.nan,
                        "train_mean": np.nan,
                        "train_pf": np.nan,
                        "test_n": hs["n"],
                        "test_gross": hs["gross"],
                        "test_mean": hs["mean"],
                        "test_fees": hs["fees"],
                        "test_win": hs["win"],
                        "test_pf": hs["pf"],
                        "test_median": hs["median"],
                        "test_p25": hs["p25"],
                        "test_p75": hs["p75"],
                        "test_dd": hs["dd"],
                        "test_return": hs["ret"],
                        "mc_median": hmc["median"],
                        "mc_p05": hmc["p05"],
                        "mc_p95": hmc["p95"],
                        "mc_dd": hmc["dd"],
                        "bench_fixed_mean": np.nan,
                        "bench_fixed_pf": np.nan,
                        "bench_bh_return": np.nan,
                    })

                    say(
                        f"  FINAL HOLDOUT | {match['signal']} | "
                        f"{match['profile']} | "
                        f"{pct(hs['mean'])} | PF={hs['pf']:.2f} | "
                        f"DD={pct(hs['dd'])} | n={hs['n']}"
                    )

            say(
                f"  -> {symbol} {interval} terminé "
                f"en {(time.time()-t_pair)/60:.1f} min"
            )

    wf = pd.DataFrame(rows)
    st = pd.DataFrame(stresses)

    wf.to_csv(outdir / "walk_forward_v4.csv", index=False)
    st.to_csv(outdir / "stress_test_v4.csv", index=False)

    # ========================================================
    # REPORT
    # ========================================================

    report = [
        "# SCALP LAB V4 — rapport de recherche",
        "",
        f"- Données : Binance USD-M",
        f"- TRAIN : {TRAIN_DAYS} jours",
        f"- TEST : {TEST_DAYS} jours",
        f"- STEP : {STEP_DAYS} jours",
        f"- FINAL HOLDOUT : {FINAL_HOLDOUT_DAYS} jours",
        f"- Coût taker : {FEE_TAKER:.2%}/côté",
        f"- Coût maker : {FEE_MAKER:.2%}/côté",
        "",
        "## Walk-forward OOS",
        "",
    ]

    valid = wf[wf["fold"] != "FINAL"] if not wf.empty else wf

    if not valid.empty:
        for interval in intervals:
            x = valid[valid.interval == interval]
            if x.empty:
                continue

            report += [
                f"### {interval}",
                "",
                "| mesure | valeur |",
                "|---|---:|",
                f"| folds | {len(x)} |",
                f"| test mean/trade | {pct(x.test_mean.mean())} |",
                f"| folds positifs | "
                f"{int((x.test_mean > 0).sum())}/{len(x)} |",
                f"| PF médian | {x.test_pf.median():.2f} |",
                f"| DD médian | {pct(x.test_dd.median())} |",
                f"| médiane trade | {pct(x.test_median.median())} |",
                "",
            ]

    report += [
        "## FINAL HOLDOUT",
        "",
        "| symbole | intervalle | mean/trade | PF | DD | n | return |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    finals = wf[wf["fold"] == "FINAL"] if not wf.empty else wf

    for _, r in finals.iterrows():
        report.append(
            f"| {r.symbol} | {r.interval} | "
            f"{pct(r.test_mean)} | {r.test_pf:.2f} | "
            f"{pct(r.test_dd)} | {int(r.test_n)} | "
            f"{pct(r.test_return)} |"
        )

    report += [
        "",
        "## Benchmarks",
        "",
    ]

    if not valid.empty:
        report += [
            "| intervalle | stratégie mean | benchmark mécanique |",
            "|---|---:|---:|",
        ]

        for interval in intervals:
            x = valid[valid.interval == interval]
            if x.empty:
                continue

            report.append(
                f"| {interval} | {pct(x.test_mean.mean())} | "
                f"{pct(x.bench_fixed_mean.mean())} |"
            )

    report += [
        "",
        "## Robustesse des coûts",
        "",
    ]

    if not st.empty:
        g = (
            st.groupby("scenario")
              .agg(mean=("mean", "mean"),
                   pf=("pf", "median"),
                   dd=("dd", "median"))
              .reset_index()
        )

        report += [
            "| scénario | mean/trade | PF médian | DD médian |",
            "|---|---:|---:|---:|",
        ]

        for _, r in g.iterrows():
            report.append(
                f"| {r.scenario} | {pct(r['mean'])} | "
                f"{r.pf:.2f} | {pct(r.dd)} |"
            )

    report += [
        "",
        "## Distribution des stratégies sélectionnées",
        "",
    ]

    if not valid.empty:
        for col in ("signal", "regime", "profile"):
            report.append(f"### {col}")
            report.append("")
            report.append(str(valid[col].value_counts().to_dict()))
            report.append("")

    report += [
        "## Limites",
        "",
        "- OHLCV uniquement.",
        "- Pas de carnet d'ordres.",
        "- Exécution maker approximée.",
        "- Pas de funding.",
        "- Pas de latence réseau réelle.",
        "- Ambiguïté intrabougie TP/SL résolue par priorité au SL.",
        "- Monte-Carlo basé sur les trades observés.",
        "- Le FINAL HOLDOUT n'est pas utilisé pour la sélection.",
        "",
        "## Interprétation",
        "",
        "V4 ne considère pas une stratégie comme validée sur la seule "
        "base d'un fold positif. La confirmation doit survivre à plusieurs "
        "folds OOS, aux coûts et au FINAL HOLDOUT.",
    ]

    (outdir / "summary_v4.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("")
    print("=" * 60)
    print("SCALP LAB V4 TERMINÉ")
    print("=" * 60)
    print(f"Durée : {(time.time()-t0)/60:.1f} min")
    print(f"Folds OOS : {len(valid)}")
    print("results/summary_v4.md")
    print("results/walk_forward_v4.csv")
    print("results/stress_test_v4.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
