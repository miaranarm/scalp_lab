"""
SCALP LAB V4.3
Research-only walk-forward engine.

V4.3 changes versus V4.2
-------------------------
1. Every fixed configuration is evaluated on every WF fold.
2. Robustness is calculated from the complete OOS matrix.
3. Training winner is stored separately in selected_v43.csv.
4. Simulations are cached once per configuration.
5. Random benchmark is disabled by default.
6. Explicit progress logging is emitted throughout the run.
7. No deployment / live trading.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import random
import zipfile
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIG
# ============================================================

BASE = "https://data.binance.vision/data/futures/um"

MS = {
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

FT = 0.0005
FM = 0.0002
TH = 0.00005

SLIP = {
    "BTCUSDT": 0.00010,
    "ETHUSDT": 0.00015,
    "SOLUSDT": 0.00030,
}

EXITS = (
    (1.5, 1.0, 12),
    (2.0, 1.0, 24),
    (3.0, 1.5, 36),
    (2.0, 2.0, 24),
)

PROFILES = (
    "taker",
    "maker_tp",
    "maker_both",
)

TRAIN = 180
TEST = 45
HOLD = 90
STEP = 45

MIN_TRAIN = 50
MIN_FOLDS = 5
MIN_TRADES = 50

MIN_POS = 0.50
MIN_RANDOM = 0.50
MIN_PF = 1.0
MIN_EDGE = 0.0

# V4.3 first diagnostic run:
# keep this at 0.
RANDOM_RUNS = 0

MC_RUNS = 0

SEED = 20260928
CAPITAL = 100.0

CTX = {
    "5m": "1h",
    "15m": "1h",
    "1h": "4h",
}

WARM = {
    "1h": 12,
    "4h": 40,
}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Candidate:
    name: str
    signal: dict
    regime: str


# ============================================================
# GENERAL HELPERS
# ============================================================

def finite(x):
    try:
        return np.isfinite(float(x))
    except Exception:
        return False


def safe_float(x, default=np.nan):
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def fmt_pct(x):
    if not finite(x):
        return "nan"
    return f"{float(x) * 100:.3f}%"


# ============================================================
# BINANCE VISION DATA
# ============================================================

def month_range(start, end):
    cur = pd.Timestamp(start).to_period("M")
    last = pd.Timestamp(end).to_period("M")

    while cur <= last:
        yield cur.year, cur.month
        cur += 1


def fetch_month(symbol, interval, year, month):
    """
    Binance Futures Vision monthly archive.
    """
    url = (
        f"{BASE}/monthly/klines/"
        f"{symbol}/{interval}/"
        f"{symbol}-{interval}-{year:04d}-{month:02d}.zip"
    )

    r = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "scalp-lab-v43"},
    )

    if r.status_code == 404:
        return None

    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = z.namelist()

        csv_name = next(
            (n for n in names if n.lower().endswith(".csv")),
            None,
        )

        if csv_name is None:
            return None

        with z.open(csv_name) as f:
            df = pd.read_csv(f, header=None)

    return df


def fetch(symbol, interval, days):
    """
    Download Binance Futures Vision monthly files.
    """
    end = pd.Timestamp.now(tz="UTC").floor("h")
    start = end - pd.Timedelta(days=days)

    print(
        f"[{symbol}] DATA {interval} "
        f"{start.date()} -> {end.date()}",
        flush=True,
    )

    frames = []

    for year, month in month_range(start, end):

        print(
            f"[{symbol}] download "
            f"{year:04d}-{month:02d}",
            flush=True,
        )

        try:
            x = fetch_month(
                symbol,
                interval,
                year,
                month,
            )

            if x is not None and not x.empty:
                frames.append(x)

        except Exception as e:
            print(
                f"[{symbol}] archive error "
                f"{year}-{month:02d}: {e}",
                flush=True,
            )

    if not frames:
        raise RuntimeError(
            f"No Binance Vision data for {symbol} {interval}"
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    # Binance kline schema
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]

    if len(df.columns) >= len(cols):
        df = df.iloc[:, :len(cols)]
        df.columns = cols

    df["time"] = pd.to_datetime(
        pd.to_numeric(df["open_time"], errors="coerce"),
        unit="ms",
        utc=True,
    )

    for c in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce",
        )

    df = df[
        [
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    df = df.dropna()

    df = df[
        (df["time"] >= start)
        & (df["time"] <= end)
    ]

    df = (
        df.sort_values("time")
        .drop_duplicates("time")
        .reset_index(drop=True)
    )

    print(
        f"[{symbol}] candles={len(df):,}",
        flush=True,
    )

    return df


# ============================================================
# FEATURES
# ============================================================

def atr(df, n=14):
    h = df["high"]
    l = df["low"]
    c = df["close"]

    pc = c.shift(1)

    tr = pd.concat(
        [
            h - l,
            (h - pc).abs(),
            (l - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(
        n,
        min_periods=n,
    ).mean()


def rsi(series, n=14):
    d = series.diff()

    up = d.clip(lower=0)
    dn = -d.clip(upper=0)

    au = up.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    ad = dn.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    rs = au / ad.replace(0, np.nan)

    return 100 - 100 / (1 + rs)


def rolling_vwap(df, n):
    pv = df["close"] * df["volume"]

    return (
        pv.rolling(n, min_periods=n).sum()
        / df["volume"].rolling(
            n,
            min_periods=n,
        ).sum()
    )


def zscore(series, n):
    mean = series.rolling(
        n,
        min_periods=n,
    ).mean()

    std = series.rolling(
        n,
        min_periods=n,
    ).std()

    return (series - mean) / std.replace(0, np.nan)


def donchian_high(df, n):
    return (
        df["high"]
        .rolling(n, min_periods=n)
        .max()
        .shift(1)
    )


def donchian_low(df, n):
    return (
        df["low"]
        .rolling(n, min_periods=n)
        .min()
        .shift(1)
    )


def features(df):
    x = df.copy()

    x["atr14"] = atr(x, 14)

    x["ema20"] = x["close"].ewm(
        span=20,
        adjust=False,
    ).mean()

    x["ema50"] = x["close"].ewm(
        span=50,
        adjust=False,
    ).mean()

    x["ema200"] = x["close"].ewm(
        span=200,
        adjust=False,
    ).mean()

    x["rsi14"] = rsi(
        x["close"],
        14,
    )

    for n in (48, 96):
        x[f"vwap{n}"] = rolling_vwap(
            x,
            n,
        )

    for n in (30, 60):
        x[f"z{n}"] = zscore(
            x["close"],
            n,
        )

    for n in (20, 50):
        x[f"dh{n}"] = donchian_high(
            x,
            n,
        )

        x[f"dl{n}"] = donchian_low(
            x,
            n,
        )

    return x


# ============================================================
# HIGHER TIMEFRAME CONTEXT
# ============================================================

def context(entry, higher, iv):
    """
    Align closed higher-timeframe candles with entry candles.
    """

    ctx = higher.copy()

    ctx["ema20"] = ctx["close"].ewm(
        span=20,
        adjust=False,
    ).mean()

    ctx["ema50"] = ctx["close"].ewm(
        span=50,
        adjust=False,
    ).mean()

    ctx["ema200"] = ctx["close"].ewm(
        span=200,
        adjust=False,
    ).mean()

    ctx["atr14"] = atr(
        ctx,
        14,
    )

    # Context candle is usable only after it has closed.
    ctx["time"] = (
        ctx["time"]
        + pd.to_timedelta(
            MS[iv],
            unit="ms",
        )
    )

    ctx = ctx[
        [
            "time",
            "close",
            "ema20",
            "ema50",
            "ema200",
            "atr14",
        ]
    ].sort_values("time")

    out = pd.merge_asof(
        entry.sort_values("time"),
        ctx,
        on="time",
        direction="backward",
        suffixes=("", "_ctx"),
    )

    out["trend"] = np.where(
        out["ema20_ctx"] > out["ema50_ctx"],
        1,
        np.where(
            out["ema20_ctx"] < out["ema50_ctx"],
            -1,
            0,
        ),
    )

    return out


# ============================================================
# SIGNALS
# ============================================================

def signal(df, spec):
    kind = spec["kind"]

    close = df["close"]
    atr14 = df["atr14"]

    s = pd.Series(
        0,
        index=df.index,
        dtype="int8",
    )

    if kind == "vwap":

        n = spec["n"]
        k = spec["k"]

        v = df[f"vwap{n}"]

        dist = (
            (close - v)
            / atr14.replace(0, np.nan)
        )

        s.loc[dist < -k] = 1
        s.loc[dist > k] = -1

    elif kind == "donchian":

        n = spec["n"]
        vol = spec["vol"]

        hi = df[f"dh{n}"]
        lo = df[f"dl{n}"]

        if vol == 0:
            long_cond = close > hi
            short_cond = close < lo

        else:
            atr_pct = (
                atr14
                / close
            )

            long_cond = (
                (close > hi)
                & (atr_pct >= vol / 10000)
            )

            short_cond = (
                (close < lo)
                & (atr_pct >= vol / 10000)
            )

        s.loc[long_cond] = 1
        s.loc[short_cond] = -1

    elif kind == "zscore":

        n = spec["n"]
        threshold = spec["thr"]

        z = df[f"z{n}"]

        s.loc[z < -threshold] = 1
        s.loc[z > threshold] = -1

    elif kind == "pullback":

        level = spec["rsi"]

        s.loc[
            (df["rsi14"] < level)
            & (close > df["ema20"])
        ] = 1

        s.loc[
            (df["rsi14"] > 100 - level)
            & (close < df["ema20"])
        ] = -1

    elif kind == "breakout":

        n = spec["n"]

        hi = df[f"dh{n}"]
        lo = df[f"dl{n}"]

        s.loc[close > hi] = 1
        s.loc[close < lo] = -1

    return s


def apply_regime(df, s, regime):
    out = s.copy()

    if regime == "all":
        return out

    trend = df["trend"]

    if regime == "trend":
        out.loc[
            ~(
                ((out == 1) & (trend == 1))
                |
                ((out == -1) & (trend == -1))
            )
        ] = 0

    elif regime == "range":
        out.loc[
            trend != 0
        ] = 0

    return out


# ============================================================
# CANDIDATES
# ============================================================

def candidates(entry, higher, iv):
    df = context(
        entry,
        higher,
        CTX.get(iv, "1h"),
    )

    df = features(df)

    specs = [
        (
            "vwap_n48_k2",
            {
                "kind": "vwap",
                "n": 48,
                "k": 2,
            },
        ),
        (
            "vwap_n96_k2",
            {
                "kind": "vwap",
                "n": 96,
                "k": 2,
            },
        ),
        (
            "vwap_n48_k3",
            {
                "kind": "vwap",
                "n": 48,
                "k": 3,
            },
        ),
        (
            "donchian_n20_v0",
            {
                "kind": "donchian",
                "n": 20,
                "vol": 0,
            },
        ),
        (
            "donchian_n20_v1.5",
            {
                "kind": "donchian",
                "n": 20,
                "vol": 1.5,
            },
        ),
        (
            "donchian_n50_v1.5",
            {
                "kind": "donchian",
                "n": 50,
                "vol": 1.5,
            },
        ),
        (
            "zscore_n30_t2",
            {
                "kind": "zscore",
                "n": 30,
                "thr": 2,
            },
        ),
        (
            "zscore_n60_t2.5",
            {
                "kind": "zscore",
                "n": 60,
                "thr": 2.5,
            },
        ),
        (
            "pullback_rsi35",
            {
                "kind": "pullback",
                "rsi": 35,
            },
        ),
        (
            "pullback_rsi40",
            {
                "kind": "pullback",
                "rsi": 40,
            },
        ),
        (
            "breakout_n20",
            {
                "kind": "breakout",
                "n": 20,
            },
        ),
    ]

    regimes = (
        "all",
        "trend",
        "range",
    )

    result = []

    for name, spec in specs:

        base_signal = signal(
            df,
            spec,
        )

        for regime in regimes:

            ss = apply_regime(
                df,
                base_signal,
                regime,
            )

            c = Candidate(
                name=name,
                signal=ss,
                regime=regime,
            )

            result.append(c)

    return df, result


# ============================================================
# SIMULATION
# ============================================================

def simulate(
    df,
    sig,
    tp,
    sl,
    hold,
    profile,
    slip,
):
    """
    Signal on closed candle.
    Entry next candle.

    Priority:
        SL before TP when both touched
        in same candle.

    No funding.
    No orderbook.
    No latency.
    """

    if df.empty:
        return []

    c = df["close"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)

    a = df["atr14"].to_numpy(dtype=float)
    s = sig.to_numpy(dtype=np.int8)

    times = df["time"].to_numpy()

    trades = []

    n = len(df)

    for i in range(n - 1):

        side = int(s[i])

        if side == 0:
            continue

        if not np.isfinite(c[i]):
            continue

        entry_idx = i + 1

        if entry_idx >= n:
            break

        entry = c[i]

        if not np.isfinite(entry):
            continue

        ef = FT

        # ----------------------------------------------------
        # Approximate maker fill
        # ----------------------------------------------------
        if profile in ("maker_tp", "maker_both"):

            if side == 1:

                if l[entry_idx] > c[i] * (1 - TH):
                    continue

            else:

                if h[entry_idx] < c[i] * (1 + TH):
                    continue

            entry = c[i]
            ef = FM

        else:

            entry = c[entry_idx]
            ef = FT

        if not np.isfinite(entry) or entry <= 0:
            continue

        atr_value = a[i]

        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        distance = atr_value

        if side == 1:

            tp_price = entry + tp * distance
            sl_price = entry - sl * distance

        else:

            tp_price = entry - tp * distance
            sl_price = entry + sl * distance

        exit_idx = min(
            entry_idx + hold,
            n - 1,
        )

        exit_price = c[exit_idx]
        exit_reason = "TIME"
        xf = FT

        for j in range(
            entry_idx,
            exit_idx + 1,
        ):

            if side == 1:

                hit_sl = l[j] <= sl_price
                hit_tp = h[j] >= tp_price

            else:

                hit_sl = h[j] >= sl_price
                hit_tp = l[j] <= tp_price

            if hit_sl and hit_tp:
                # Conservative priority.
                exit_price = sl_price
                exit_reason = "SL"
                break

            if hit_sl:
                exit_price = sl_price
                exit_reason = "SL"
                break

            if hit_tp:
                exit_price = tp_price
                exit_reason = "TP"

                if profile == "maker_tp":
                    xf = FM
                elif profile == "maker_both":
                    xf = FM

                break

        # ----------------------------------------------------
        # Gross return
        # ----------------------------------------------------
        if side == 1:
            gross = (
                exit_price / entry
            ) - 1
        else:
            gross = (
                entry / exit_price
            ) - 1

        # Approximate total costs:
        # entry fee + exit fee + slippage
        total_fee = ef + xf

        net = gross - total_fee - slip

        trades.append({
            "entry_time": pd.Timestamp(
                times[entry_idx]
            ),
            "exit_time": pd.Timestamp(
                times[
                    min(
                        j if 'j' in locals() else exit_idx,
                        n - 1,
                    )
                ]
            ),
            "side": side,
            "entry": entry,
            "exit": exit_price,
            "gross": gross,
            "net": net,
            "reason": exit_reason,
        })

    return trades


def inside(trades, start, end):
    if not trades:
        return []

    return [
        t for t in trades
        if (
            pd.Timestamp(start)
            <= pd.Timestamp(t["entry_time"])
            < pd.Timestamp(end)
        )
    ]


# ============================================================
# STATS
# ============================================================

def empty_stats():
    return {
        "n": 0,
        "mean": np.nan,
        "median": np.nan,
        "pf": np.nan,
        "edge": np.nan,
        "return": np.nan,
        "dd": np.nan,
        "wins": 0,
        "losses": 0,
    }


def stats(trades):
    if not trades:
        return empty_stats()

    x = pd.DataFrame(trades)

    if x.empty:
        return empty_stats()

    r = pd.to_numeric(
        x["net"],
        errors="coerce",
    ).dropna()

    if r.empty:
        return empty_stats()

    wins = r[r > 0]
    losses = r[r < 0]

    gross_profit = wins.sum()
    gross_loss = -losses.sum()

    if gross_loss > 0:
        pf = gross_profit / gross_loss
    else:
        pf = np.inf if gross_profit > 0 else np.nan

    equity = (1 + r).cumprod()

    peak = equity.cummax()

    dd = (
        equity / peak
        - 1
    ).min()

    # Simple mean edge per trade.
    edge = r.mean()

    return {
        "n": int(len(r)),
        "mean": float(r.mean()),
        "median": float(r.median()),
        "pf": float(pf),
        "edge": float(edge),
        "return": float(equity.iloc[-1] - 1),
        "dd": float(dd),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
    }


# ============================================================
# TRAIN SCORE
# ============================================================

def score(st):
    n = st["n"]

    if n < MIN_TRAIN:
        return -np.inf

    if not finite(st["mean"]):
        return -np.inf

    if not finite(st["pf"]):
        return -np.inf

    if not finite(st["dd"]):
        return -np.inf

    # Keep the original philosophy:
    # reward average return and PF,
    # penalize drawdown,
    # require sufficient sample size.
    #
    # This is only TRAIN selection.
    return (
        st["mean"] * 1000
        + math.log1p(max(st["pf"], 0))
        + st["dd"] * 2
    )


# ============================================================
# MONTE CARLO
# ============================================================

def mc(
    trades,
    runs=5000,
    seed=SEED,
):
    if runs <= 0:
        return {}

    if len(trades) < 20:
        return {}

    r = np.array(
        [
            float(t["net"])
            for t in trades
            if finite(t["net"])
        ],
        dtype=float,
    )

    if len(r) < 20:
        return {}

    rng = np.random.default_rng(seed)

    finals = []

    for _ in range(runs):

        sample = rng.choice(
            r,
            size=len(r),
            replace=True,
        )

        equity = np.cumprod(
            1 + sample
        )

        finals.append(
            equity[-1]
        )

    finals = np.asarray(
        finals,
        dtype=float,
    )

    return {
        "mean": float(np.mean(finals) - 1),
        "median": float(np.median(finals) - 1),
        "p05": float(np.percentile(finals, 5) - 1),
        "p95": float(np.percentile(finals, 95) - 1),
    }


def random_mc(
    L,
    sig,
    tp,
    sl,
    hold,
    profile,
    slip,
    start,
    end,
    runs,
    seed,
):
    """
    Random-side benchmark.

    It preserves the signal event timestamps but randomly
    assigns long/short directions.
    """

    if runs <= 0:
        return {}

    rng = np.random.default_rng(seed)

    sig0 = sig.copy()

    active = np.flatnonzero(
        sig0.to_numpy() != 0
    )

    if len(active) < 20:
        return {}

    results = []

    for _ in range(runs):

        rs = sig0.copy()

        signs = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=len(active),
        )

        arr = rs.to_numpy(
            copy=True
        )

        arr[active] = signs

        random_signal = pd.Series(
            arr,
            index=rs.index,
        )

        tr = simulate(
            L,
            random_signal,
            tp,
            sl,
            hold,
            profile,
            slip,
        )

        tr = inside(
            tr,
            start,
            end,
        )

        st = stats(tr)

        if st["n"] > 0:

            results.append({
                "mean": st["mean"],
                "pf": st["pf"],
                "edge": st["edge"],
            })

    if not results:
        return {}

    x = pd.DataFrame(results)

    return {
        "mean": float(x["mean"].mean()),
        "median": float(x["mean"].median()),
        "pf": float(x["pf"].median()),
        "edge": float(x["edge"].median()),
    }


# ============================================================
# FIXED / BUY & HOLD
# ============================================================

def fixed(trades):
    st = stats(trades)

    return st


def buyhold(df):
    if df.empty:
        return np.nan

    r = (
        df["close"].iloc[-1]
        / df["close"].iloc[0]
        - 1
    )

    return float(
        (1 + r)
        * (1 - FT) ** 2
        - 1
    )


# ============================================================
# WALK-FORWARD FOLDS
# ============================================================

def folds(
    start,
    end,
):
    """
    TRAIN / TEST rolling walk-forward.

    Durations are expressed in days.
    """

    start = pd.Timestamp(
        start,
        tz="UTC",
    )

    end = pd.Timestamp(
        end,
        tz="UTC",
    )

    out = []

    tr = pd.Timedelta(
        days=TRAIN
    )

    te = pd.Timedelta(
        days=TEST
    )

    step = pd.Timedelta(
        days=STEP
    )

    cursor = start + tr

    while cursor + te <= end:

        tr0 = cursor - tr
        tr1 = cursor

        te0 = cursor
        te1 = cursor + te

        out.append(
            (
                tr0,
                tr1,
                te0,
                te1,
            )
        )

        cursor += step

    return out


# ============================================================
# MEDIAN
# ============================================================

def finite_median(series):
    x = pd.to_numeric(
        series,
        errors="coerce",
    )

    x = x[np.isfinite(x)]

    if len(x) == 0:
        return np.nan

    return float(x.median())


# ============================================================
# V4.3 ROBUSTNESS
# ============================================================

def robustness(wf):
    """
    IMPORTANT:

    wf must contain every fixed configuration on every fold.

    active_folds therefore means:
    number of OOS folds in which this configuration
    actually generated at least one trade.

    It does NOT mean number of folds won.
    """

    if wf is None or wf.empty:
        return pd.DataFrame()

    x = wf.copy()

    x["train_eligible"] = (
        x["train_eligible"]
        .fillna(False)
        .astype(bool)
    )

    for col in [
        "test_n",
        "test_mean",
        "test_pf",
        "test_edge",
        "test_dd",
    ]:
        x[col] = pd.to_numeric(
            x[col],
            errors="coerce",
        )

    x["test_n"] = (
        x["test_n"]
        .fillna(0)
    )

    cols = [
        "symbol",
        "interval",
        "signal",
        "regime",
        "profile",
        "tp",
        "sl",
        "hold",
    ]

    rows = []

    for key, g0 in x.groupby(
        cols,
        dropna=False,
    ):

        g = g0[
            g0["train_eligible"]
        ].copy()

        if g.empty:
            continue

        active = g[
            g["test_n"] > 0
        ].copy()

        eligible_folds = len(g)
        active_folds = len(active)

        total_trades = int(
            active["test_n"].sum()
        )

        if active_folds:

            means = (
                active["test_mean"]
                .dropna()
            )

            pfs = (
                active["test_pf"]
                .dropna()
            )

            edges = (
                active["test_edge"]
                .dropna()
            )

            dds = (
                active["test_dd"]
                .dropna()
            )

            mean_oos = (
                float(means.mean())
                if len(means)
                else np.nan
            )

            median_oos = (
                float(means.median())
                if len(means)
                else np.nan
            )

            positive_ratio = (
                float(
                    (means > 0).mean()
                )
                if len(means)
                else np.nan
            )

            median_pf = (
                float(pfs.median())
                if len(pfs)
                else np.nan
            )

            median_dd = (
                float(dds.median())
                if len(dds)
                else np.nan
            )

            mean_edge = (
                float(edges.mean())
                if len(edges)
                else np.nan
            )

            median_edge = (
                float(edges.median())
                if len(edges)
                else np.nan
            )

            beat_random_ratio = (
                float(
                    (edges > 0).mean()
                )
                if len(edges)
                else np.nan
            )

        else:

            mean_oos = np.nan
            median_oos = np.nan
            positive_ratio = np.nan
            median_pf = np.nan
            median_dd = np.nan
            mean_edge = np.nan
            median_edge = np.nan
            beat_random_ratio = np.nan

        robust = (
            eligible_folds >= MIN_FOLDS
            and active_folds >= MIN_FOLDS
            and total_trades >= MIN_TRADES
            and finite(mean_oos)
            and finite(median_oos)
            and finite(positive_ratio)
            and finite(median_pf)
            and finite(median_dd)
            and finite(mean_edge)
            and finite(median_edge)
            and positive_ratio >= MIN_POS
            and beat_random_ratio >= MIN_RANDOM
            and median_pf >= MIN_PF
            and mean_edge >= MIN_EDGE
        )

        row = dict(
            zip(cols, key)
        )

        row.update({
            "eligible_folds":
                eligible_folds,

            "active_folds":
                active_folds,

            "zero_trade_folds":
                eligible_folds - active_folds,

            "total_trades":
                total_trades,

            "mean_oos":
                mean_oos,

            "median_oos":
                median_oos,

            "positive_fold_ratio":
                positive_ratio,

            "beat_random_ratio":
                beat_random_ratio,

            "median_pf":
                median_pf,

            "median_dd":
                median_dd,

            "mean_edge":
                mean_edge,

            "median_edge":
                median_edge,

            "robust":
                bool(robust),
        })

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)

    return out.sort_values(
        [
            "robust",
            "median_oos",
            "median_pf",
            "active_folds",
            "total_trades",
        ],
        ascending=[
            False,
            False,
            False,
            False,
            False,
        ],
    ).reset_index(drop=True)


# ============================================================
# GLOBAL ROBUSTNESS
# ============================================================

def global_robust(rob):
    if rob is None or rob.empty:
        return pd.DataFrame()

    x = rob[
        rob["robust"] == True
    ].copy()

    if x.empty:
        return pd.DataFrame()

    group_cols = [
        "interval",
        "signal",
        "regime",
        "profile",
        "tp",
        "sl",
        "hold",
    ]

    rows = []

    for key, g in x.groupby(
        group_cols,
        dropna=False,
    ):

        symbols = sorted(
            g["symbol"]
            .astype(str)
            .unique()
        )

        row = dict(
            zip(group_cols, key)
        )

        row.update({
            "symbols":
                ",".join(symbols),

            "symbol_count":
                len(symbols),

            "mean_oos":
                g["mean_oos"].mean(),

            "median_oos":
                g["median_oos"].median(),

            "median_pf":
                g["median_pf"].median(),

            "mean_edge":
                g["mean_edge"].mean(),

            "total_trades":
                int(g["total_trades"].sum()),

            "robust_symbols":
                len(symbols),
        })

        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        [
            "robust_symbols",
            "median_oos",
            "median_pf",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )


# ============================================================
# V4.3 WF ENGINE
# ============================================================

def evaluate_walk_forward_v43(
    L,
    cands,
    sym,
    iv,
    fs,
    random_runs=0,
):
    """
    Evaluate EVERY fixed configuration on EVERY fold.
    """

    slip = SLIP.get(
        sym,
        0.0003,
    )

    configs = []

    for ci, c in enumerate(cands):

        for tp, sl, hold in EXITS:

            for prof in PROFILES:

                configs.append({
                    "ci": ci,
                    "c": c,
                    "tp": tp,
                    "sl": sl,
                    "hold": hold,
                    "prof": prof,
                })

    print(
        f"[{sym}] CONFIGURATIONS = "
        f"{len(configs)} | "
        f"FOLDS = {len(fs)} | "
        f"RANDOM = {random_runs}",
        flush=True,
    )

    # --------------------------------------------------------
    # Precompute every simulation once.
    # --------------------------------------------------------

    cache = {}

    checkpoint = max(
        1,
        len(configs) // 4,
    )

    for no, cfg in enumerate(
        configs,
        1,
    ):

        key = (
            cfg["ci"],
            cfg["tp"],
            cfg["sl"],
            cfg["hold"],
            cfg["prof"],
        )

        cache[key] = simulate(
            L,
            cfg["c"].signal,
            cfg["tp"],
            cfg["sl"],
            cfg["hold"],
            cfg["prof"],
            slip,
        )

        if (
            no == 1
            or no % checkpoint == 0
            or no == len(configs)
        ):
            print(
                f"[{sym}] CACHE "
                f"{no}/{len(configs)}",
                flush=True,
            )

    all_rows = []
    selected_rows = []

    # --------------------------------------------------------
    # Every fold
    # --------------------------------------------------------

    for fi, (
        tr0,
        tr1,
        te0,
        te1,
    ) in enumerate(
        fs,
        1,
    ):

        print(
            f"[{sym}] FOLD "
            f"{fi}/{len(fs)} "
            f"TRAIN={tr0.date()}->{tr1.date()} "
            f"TEST={te0.date()}->{te1.date()}",
            flush=True,
        )

        best = None
        fold_rows = []

        for cfg_no, cfg in enumerate(
            configs,
            1,
        ):

            key = (
                cfg["ci"],
                cfg["tp"],
                cfg["sl"],
                cfg["hold"],
                cfg["prof"],
            )

            trades = cache[key]

            tr = inside(
                trades,
                tr0,
                tr1,
            )

            tt = inside(
                trades,
                te0,
                te1,
            )

            tr_st = stats(tr)
            te_st = stats(tt)

            train_score = score(
                tr_st
            )

            train_eligible = (
                tr_st["n"] >= MIN_TRAIN
                and finite(train_score)
            )

            random_mean = np.nan
            random_median = np.nan
            random_pf = np.nan
            random_edge = np.nan

            # Disabled in the first V4.3 run.
            if (
                random_runs > 0
                and train_eligible
                and te_st["n"] > 0
            ):

                try:

                    rr = random_mc(
                        L,
                        cfg["c"].signal,
                        cfg["tp"],
                        cfg["sl"],
                        cfg["hold"],
                        cfg["prof"],
                        slip,
                        te0,
                        te1,
                        random_runs,
                        SEED
                        + fi
                        + cfg_no,
                    )

                    if rr:

                        random_mean = rr.get(
                            "mean",
                            np.nan,
                        )

                        random_median = rr.get(
                            "median",
                            np.nan,
                        )

                        random_pf = rr.get(
                            "pf",
                            np.nan,
                        )

                        random_edge = rr.get(
                            "edge",
                            np.nan,
                        )

                except Exception as e:

                    print(
                        f"[{sym}] RANDOM ERROR "
                        f"fold={fi} "
                        f"cfg={cfg_no}: {e}",
                        flush=True,
                    )

            row = {
                "symbol": sym,
                "interval": iv,
                "fold": fi,

                "train_start": tr0,
                "train_end": tr1,

                "test_start": te0,
                "test_end": te1,

                "ci": cfg["ci"],

                "signal":
                    cfg["c"].name,

                "regime":
                    cfg["c"].regime,

                "profile":
                    cfg["prof"],

                "tp":
                    cfg["tp"],

                "sl":
                    cfg["sl"],

                "hold":
                    cfg["hold"],

                "train_eligible":
                    bool(train_eligible),

                "selected":
                    False,

                "train_n":
                    tr_st["n"],

                "train_mean":
                    tr_st["mean"],

                "train_pf":
                    tr_st["pf"],

                "train_edge":
                    tr_st["edge"],

                "train_return":
                    tr_st["return"],

                "train_dd":
                    tr_st["dd"],

                "test_n":
                    te_st["n"],

                "test_mean":
                    te_st["mean"],

                "test_pf":
                    te_st["pf"],

                "test_edge":
                    te_st["edge"],

                "test_return":
                    te_st["return"],

                "test_dd":
                    te_st["dd"],

                "random_mean":
                    random_mean,

                "random_median":
                    random_median,

                "random_pf":
                    random_pf,

                "random_edge":
                    random_edge,

                "train_score":
                    train_score,
            }

            fold_rows.append(row)

            if train_eligible:

                if (
                    best is None
                    or train_score
                    > best["score"]
                ):

                    best = {
                        "score":
                            train_score,

                        "row_index":
                            len(fold_rows) - 1,

                        "cfg":
                            cfg,
                    }

        # ----------------------------------------------------
        # Mark train winner.
        # ----------------------------------------------------

        if best is not None:

            selected = fold_rows[
                best["row_index"]
            ]

            selected["selected"] = True

            selected_rows.append(
                dict(selected)
            )

            print(
                f"[{sym}] FOLD "
                f"{fi}/{len(fs)} DONE | "
                f"WINNER={selected['signal']} | "
                f"{selected['regime']} | "
                f"{selected['profile']} | "
                f"TP={selected['tp']} "
                f"SL={selected['sl']} "
                f"H={selected['hold']} | "
                f"TRAIN_N={selected['train_n']} | "
                f"TEST_N={selected['test_n']}",
                flush=True,
            )

        else:

            print(
                f"[{sym}] FOLD "
                f"{fi}/{len(fs)} DONE | "
                f"NO ELIGIBLE CONFIG",
                flush=True,
            )

        all_rows.extend(
            fold_rows
        )

    print(
        f"[{sym}] WF COMPLETE | "
        f"ROWS={len(all_rows)} | "
        f"SELECTED={len(selected_rows)}",
        flush=True,
    )

    return (
        all_rows,
        selected_rows,
    )


# ============================================================
# HOLDOUT
# ============================================================

def run_holdout(
    L,
    cands,
    sym,
    iv,
    start,
    end,
    robust_df,
):
    if (
        robust_df is None
        or robust_df.empty
    ):
        return []

    r = robust_df[
        (robust_df["symbol"] == sym)
        & (robust_df["interval"] == iv)
        & (robust_df["robust"] == True)
    ].copy()

    if r.empty:
        return []

    # Take the first robust configuration for this asset.
    r = r.iloc[0]

    target = None

    for ci, c in enumerate(cands):

        if c.name != r["signal"]:
            continue

        if c.regime != r["regime"]:
            continue

        target = (
            ci,
            c,
        )
        break

    if target is None:
        return []

    ci, c = target

    trades = simulate(
        L,
        c.signal,
        float(r["tp"]),
        float(r["sl"]),
        int(r["hold"]),
        r["profile"],
        SLIP.get(sym, 0.0003),
    )

    h = inside(
        trades,
        start,
        end,
    )

    st = stats(h)

    return [{
        "symbol": sym,
        "interval": iv,
        "signal": c.name,
        "regime": c.regime,
        "profile": r["profile"],
        "tp": r["tp"],
        "sl": r["sl"],
        "hold": r["hold"],
        "holdout_start": start,
        "holdout_end": end,
        "holdout_n": st["n"],
        "holdout_mean": st["mean"],
        "holdout_pf": st["pf"],
        "holdout_edge": st["edge"],
        "holdout_return": st["return"],
        "holdout_dd": st["dd"],
    }]


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ],
    )

    parser.add_argument(
        "--intervals",
        nargs="+",
        default=["1h"],
    )

    parser.add_argument(
        "--days",
        type=int,
        default=730,
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100.0,
    )

    parser.add_argument(
        "--mc-runs",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--random-runs",
        type=int,
        default=RANDOM_RUNS,
    )

    args = parser.parse_args()

    global CAPITAL
    CAPITAL = args.capital

    random.seed(SEED)
    np.random.seed(SEED)

    Path("results").mkdir(
        parents=True,
        exist_ok=True,
    )

    all_wf_rows = []
    all_selected_rows = []
    all_rob_rows = []
    all_holdout_rows = []

    print(
        "==============================================",
        flush=True,
    )

    print(
        "SCALP LAB V4.3",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    print(
        f"Symbols : "
        f"{' '.join(args.symbols)}",
        flush=True,
    )

    print(
        f"Intervals: "
        f"{' '.join(args.intervals)}",
        flush=True,
    )

    print(
        f"History : {args.days} days",
        flush=True,
    )

    print(
        f"MC runs : {args.mc_runs}",
        flush=True,
    )

    print(
        f"Random  : {args.random_runs}",
        flush=True,
    )

    print(
        f"WF      : "
        f"{TRAIN} / {TEST} / {STEP} days",
        flush=True,
    )

    print(
        f"Holdout : {HOLD} days",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    for iv in args.intervals:

        if iv not in MS:
            raise ValueError(
                f"Unsupported interval: {iv}"
            )

        for sym in args.symbols:

            print(
                "",
                flush=True,
            )

            print(
                "==============================================",
                flush=True,
            )

            print(
                f"START {sym} {iv}",
                flush=True,
            )

            print(
                "==============================================",
                flush=True,
            )

            # ------------------------------------------------
            # Entry timeframe
            # ------------------------------------------------

            entry = fetch(
                sym,
                iv,
                args.days,
            )

            # ------------------------------------------------
            # Higher timeframe context
            # ------------------------------------------------

            ctx_iv = CTX.get(
                iv,
                "1h",
            )

            higher = fetch(
                sym,
                ctx_iv,
                args.days + WARM.get(
                    ctx_iv,
                    40,
                ),
            )

            L, cands = candidates(
                entry,
                higher,
                iv,
            )

            print(
                f"[{sym}] candidates="
                f"{len(cands)}",
                flush=True,
            )

            # ------------------------------------------------
            # WF dates
            # ------------------------------------------------

            start = L["time"].min()
            end = L["time"].max()

            fs = folds(
                start,
                end,
            )

            print(
                f"[{sym}] folds="
                f"{len(fs)}",
                flush=True,
            )

            if len(fs) == 0:

                print(
                    f"[{sym}] "
                    f"NO WALK-FORWARD FOLDS",
                    flush=True,
                )

                continue

            # ------------------------------------------------
            # V4.3 exhaustive WF
            # ------------------------------------------------

            wf_rows, selected_rows = (
                evaluate_walk_forward_v43(
                    L=L,
                    cands=cands,
                    sym=sym,
                    iv=iv,
                    fs=fs,
                    random_runs=args.random_runs,
                )
            )

            all_wf_rows.extend(
                wf_rows
            )

            all_selected_rows.extend(
                selected_rows
            )

            # ------------------------------------------------
            # Asset robustness
            # ------------------------------------------------

            wf_asset = pd.DataFrame(
                wf_rows
            )

            rob_asset = robustness(
                wf_asset
            )

            if not rob_asset.empty:
                all_rob_rows.extend(
                    rob_asset.to_dict(
                        "records"
                    )
                )

            robust_count = (
                int(
                    rob_asset["robust"].sum()
                )
                if not rob_asset.empty
                else 0
            )

            print(
                f"[{sym}] ROBUST "
                f"CONFIGS={robust_count}",
                flush=True,
            )

            # ------------------------------------------------
            # Holdout
            # ------------------------------------------------

            holdout_start = (
                end
                - pd.Timedelta(
                    days=HOLD
                )
            )

            hold_rows = run_holdout(
                L,
                cands,
                sym,
                iv,
                holdout_start,
                end,
                rob_asset,
            )

            all_holdout_rows.extend(
                hold_rows
            )

    # ========================================================
    # FINAL OUTPUTS
    # ========================================================

    wf = pd.DataFrame(
        all_wf_rows
    )

    selected = pd.DataFrame(
        all_selected_rows
    )

    rob = pd.DataFrame(
        all_rob_rows
    )

    holdout = pd.DataFrame(
        all_holdout_rows
    )

    wf.to_csv(
        "results/walk_forward_v43.csv",
        index=False,
    )

    selected.to_csv(
        "results/selected_v43.csv",
        index=False,
    )

    rob.to_csv(
        "results/robustness_v43.csv",
        index=False,
    )

    holdout.to_csv(
        "results/holdout_v43.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Global robustness
    # --------------------------------------------------------

    global_df = global_robust(
        rob
    )

    global_df.to_csv(
        "results/global_v43.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    robust_count = (
        int(
            rob["robust"].sum()
        )
        if not rob.empty
        else 0
    )

    summary = []

    summary.append(
        "# SCALP LAB V4.3 SUMMARY"
    )

    summary.append("")

    summary.append(
        f"- Symbols: "
        f"{', '.join(args.symbols)}"
    )

    summary.append(
        f"- Intervals: "
        f"{', '.join(args.intervals)}"
    )

    summary.append(
        f"- History: "
        f"{args.days} days"
    )

    summary.append(
        f"- MC runs: "
        f"{args.mc_runs}"
    )

    summary.append(
        f"- Random runs: "
        f"{args.random_runs}"
    )

    summary.append(
        f"- WF train/test/step: "
        f"{TRAIN}/{TEST}/{STEP} days"
    )

    summary.append(
        f"- Holdout: {HOLD} days"
    )

    summary.append("")

    summary.append(
        "## V4.3 methodology"
    )

    summary.append("")

    summary.append(
        "Every fixed configuration is evaluated "
        "on every walk-forward fold."
    )

    summary.append(
        "Robustness is calculated from the "
        "complete OOS matrix."
    )

    summary.append(
        "Training winners are stored separately "
        "in selected_v43.csv."
    )

    summary.append("")

    summary.append(
        f"- WF rows: {len(wf):,}"
    )

    summary.append(
        f"- Selected rows: {len(selected):,}"
    )

    summary.append(
        f"- Robust configurations: "
        f"{robust_count}"
    )

    summary.append("")

    if not rob.empty:

        summary.append(
            "## Robustness"
        )

        summary.append("")

        cols = [
            "symbol",
            "signal",
            "regime",
            "profile",
            "tp",
            "sl",
            "hold",
            "eligible_folds",
            "active_folds",
            "total_trades",
            "mean_oos",
            "median_oos",
            "positive_fold_ratio",
            "median_pf",
            "median_dd",
            "mean_edge",
            "robust",
        ]

        cols = [
            c for c in cols
            if c in rob.columns
        ]

        summary.append(
            rob[cols]
            .head(20)
            .to_markdown(
                index=False
            )
        )

    else:

        summary.append(
            "No robustness rows."
        )

    Path(
        "results/summary_v43.md"
    ).write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    # ========================================================
    # FINAL CONSOLE
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    print(
        "V4.3 COMPLETE",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    print(
        f"WF rows       : {len(wf):,}",
        flush=True,
    )

    print(
        f"Selected rows : {len(selected):,}",
        flush=True,
    )

    print(
        f"Robust configs: {robust_count}",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )


if __name__ == "__main__":
    main()
