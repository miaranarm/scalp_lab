"""
SCALP LAB V4.2 — laboratoire de recherche scalping Binance USD-M.

V4.2 = V4.1 + couche de robustesse statistique.

Conserve :
- Binance Futures USD-M
- data.binance.vision
- OHLCV
- signal clôturé -> entrée suivante
- mêmes signaux
- mêmes régimes
- mêmes exits
- mêmes profils
- même simulation
- même benchmark random-side
- même Monte-Carlo

Ajoute :
- FINAL HOLDOUT 90 jours
- agrégation OOS par configuration
- stabilité inter-folds
- pénalisation des petits échantillons
- filtre de robustesse
- analyse multi-actifs
- configurations n=0 invalides
- Monte-Carlo réellement désactivable avec --mc-runs 0
"""

from __future__ import annotations

import argparse
import io
import math
import time
import zipfile
from collections import Counter
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

INTERVAL_MS = {
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

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

PROFILES = (
    "taker",
    "maker_tp",
    "maker_both",
)

TRAIN_DAYS = 180
TEST_DAYS = 45
FINAL_HOLDOUT_DAYS = 90
STEP_DAYS = 45

MIN_TRAIN_TRADES = 50

# ------------------------------------------------------------
# ROBUSTESSE V4.2
# ------------------------------------------------------------

# Nombre minimum de folds OOS avec au moins un trade.
MIN_ACTIVE_FOLDS = 5

# Nombre minimum de trades OOS cumulés.
MIN_TOTAL_TRADES = 50

# Au moins 50% des folds OOS doivent être positifs.
MIN_POSITIVE_FOLD_RATIO = 0.50

# Au moins 50% des folds OOS doivent battre le random-side.
MIN_BEAT_RANDOM_RATIO = 0.50

# PF médian minimum.
MIN_MEDIAN_PF = 1.00

# Edge médian contre random-side minimum.
MIN_MEDIAN_EDGE_RANDOM = 0.0

RANDOM_SIDE_RUNS = 100

MC_RUNS = 5000
MC_SEED = 20260928

DEFAULT_CAPITAL = 100.0

CONTEXT_ENTRY_TO_CTX = {
    "5m": "1h",
    "15m": "1h",
    "1h": "4h",
}

CONTEXT_WARMUP_DAYS = {
    "1h": 12,
    "4h": 40,
}

CONTEXT_MIN_LEN = {
    "1h": 500,
    "4h": 200,
}

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

REGIMES = (
    "all",
    "trend",
    "range",
)


# ============================================================
# DATA
# ============================================================

def read_zip_csv(content: bytes):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        raw = z.read(name).decode("utf-8")

    return [
        r[:12]
        for r in (
            x.split(",")
            for x in raw.splitlines()
        )
        if r and r[0].isdigit()
    ]


def fetch_vision(
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
):
    rows = []
    step = INTERVAL_MS[interval]

    start_dt = datetime.fromtimestamp(
        start_ms / 1000,
        timezone.utc,
    )

    end_dt = datetime.fromtimestamp(
        end_ms / 1000,
        timezone.utc,
    )

    cur = start_dt.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    while cur < end_dt:

        if cur.month == 12:
            nxt = cur.replace(
                year=cur.year + 1,
                month=1,
            )
        else:
            nxt = cur.replace(
                month=cur.month + 1
            )

        a = max(
            cur.timestamp() * 1000,
            start_ms,
        )

        b = min(
            nxt.timestamp() * 1000 - step,
            end_ms,
        )

        if a <= b:

            url = (
                f"{BASE_URL}/monthly/klines/"
                f"{symbol}/{interval}/"
                f"{symbol}-{interval}-{cur:%Y-%m}.zip"
            )

            try:
                r = requests.get(
                    url,
                    timeout=90,
                )

                if r.ok:
                    rows.extend(
                        read_zip_csv(r.content)
                    )

                else:
                    day = datetime.fromtimestamp(
                        a / 1000,
                        timezone.utc,
                    ).date()

                    last = datetime.fromtimestamp(
                        b / 1000,
                        timezone.utc,
                    ).date()

                    while day <= last:

                        u = (
                            f"{BASE_URL}/daily/klines/"
                            f"{symbol}/{interval}/"
                            f"{symbol}-{interval}-{day}.zip"
                        )

                        try:
                            q = requests.get(
                                u,
                                timeout=90,
                            )

                            if q.ok:
                                rows.extend(
                                    read_zip_csv(
                                        q.content
                                    )
                                )

                        except requests.RequestException:
                            pass

                        day += pd.Timedelta(
                            days=1
                        )

            except requests.RequestException:
                pass

        cur = nxt

    return rows


def to_frame(rows):

    cols = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "x",
        "q",
        "n",
        "tb",
        "tq",
        "i",
    ]

    d = pd.DataFrame(
        rows,
        columns=cols,
    )

    for c in cols[:6]:
        d[c] = pd.to_numeric(
            d[c],
            errors="coerce",
        )

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

    c = d["close"]
    h = d["high"]
    l = d["low"]
    v = d["volume"]

    prev = c.shift()

    tr = pd.concat(
        [
            h - l,
            (h - prev).abs(),
            (l - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)

    delta = c.diff()

    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)

    avg_up = up.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    avg_down = down.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    rs = avg_up / avg_down.replace(
        0,
        np.nan,
    )

    atr = tr.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    ema9 = c.ewm(
        span=9,
        adjust=False,
    ).mean()

    ema20 = c.ewm(
        span=20,
        adjust=False,
    ).mean()

    ema50 = c.ewm(
        span=50,
        adjust=False,
    ).mean()

    ema200 = c.ewm(
        span=200,
        adjust=False,
    ).mean()

    mean20 = c.rolling(20).mean()
    sd20 = c.rolling(20).std()

    z = (
        (c - mean20)
        / sd20.replace(0, np.nan)
    )

    vmean = v.rolling(20).mean()

    typical = (
        h + l + c
    ) / 3

    out = {
        "c": c.to_numpy(float),
        "h": h.to_numpy(float),
        "l": l.to_numpy(float),
        "v": v.to_numpy(float),

        "rsi": (
            100 - 100 / (1 + rs)
        ).to_numpy(float),

        "atr": atr.to_numpy(float),

        "ema9": ema9.to_numpy(float),
        "ema20": ema20.to_numpy(float),
        "ema50": ema50.to_numpy(float),
        "ema200": ema200.to_numpy(float),

        "z20": z.to_numpy(float),

        "vol_ratio": (
            v / vmean.replace(0, np.nan)
        ).to_numpy(float),

        "vwap48": (
            (typical * v).rolling(48).sum()
            /
            v.rolling(48).sum()
        ).to_numpy(float),

        "vwap96": (
            (typical * v).rolling(96).sum()
            /
            v.rolling(96).sum()
        ).to_numpy(float),

        "atr_pct": (
            atr / c
        ).to_numpy(float),

        "ret": c.pct_change().to_numpy(float),
    }

    out["ema20_slope"] = (
        ema20.pct_change(6)
        .to_numpy(float)
    )

    out["ema50_slope"] = (
        ema50.pct_change(12)
        .to_numpy(float)
    )

    out["ema_sep"] = (
        (ema20 - ema50) / c
    ).to_numpy(float)

    out["dist200"] = (
        (c - ema200) / ema200
    ).to_numpy(float)

    return out


def align_1h(
    entry,
    h1,
    ctx_iv,
):

    f = make_features(h1)

    x = pd.DataFrame(
        {
            "time": h1["time"].to_numpy(),

            **{
                k: f[k]
                for k in (
                    "c",
                    "ema20",
                    "ema50",
                    "ema200",
                    "atr",
                    "rsi",
                    "ema20_slope",
                    "ema50_slope",
                    "ema_sep",
                    "dist200",
                )
            },
        }
    )

    x["time"] += INTERVAL_MS[ctx_iv]

    e = pd.DataFrame(
        {
            "time": entry["time"].to_numpy()
        }
    )

    return pd.merge_asof(
        e.sort_values("time"),
        x.sort_values("time"),
        on="time",
        direction="backward",
    )


def context_masks(
    entry,
    h1,
    ctx_iv,
):

    a = align_1h(
        entry,
        h1,
        ctx_iv,
    )

    c = a["c"].to_numpy(float)
    e20 = a["ema20"].to_numpy(float)
    e50 = a["ema50"].to_numpy(float)
    e200 = a["ema200"].to_numpy(float)
    s20 = a["ema20_slope"].to_numpy(float)
    s50 = a["ema50_slope"].to_numpy(float)
    sep = a["ema_sep"].to_numpy(float)
    d200 = a["dist200"].to_numpy(float)

    valid = np.isfinite(
        np.column_stack(
            [
                c,
                e20,
                e50,
                e200,
                s20,
                s50,
                sep,
                d200,
            ]
        )
    ).all(axis=1)

    trend_up = (
        valid
        & (e20 > e50)
        & (c > e200)
        & (sep >= 0.0025)
        & (d200 <= 0.045)
    )

    trend_down = (
        valid
        & (e20 < e50)
        & (c < e200)
        & (sep <= -0.0025)
        & (d200 >= -0.045)
    )

    trend = trend_up | trend_down

    rng = (
        valid
        & (np.abs(sep) < 0.0025)
        & (np.abs(d200) < 0.02)
    )

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

    x = np.zeros(
        len(long),
        dtype=np.int8,
    )

    x[long] = 1
    x[short] = -1

    return x


def build_signal(
    name,
    p,
    f,
):

    c = f["c"]
    h = f["h"]
    l = f["l"]

    if name == "vwap":

        vw = f[
            f"vwap{p['n']}"
        ]

        dist = (
            c - vw
        ) / f["atr"]

        return sig(
            dist < -p["k"],
            dist > p["k"],
        )

    if name == "donchian":

        n = p["n"]

        hi = (
            pd.Series(h)
            .rolling(n)
            .max()
            .shift(1)
            .to_numpy()
        )

        lo = (
            pd.Series(l)
            .rolling(n)
            .min()
            .shift(1)
            .to_numpy()
        )

        vr = f["vol_ratio"]

        return sig(
            (c > hi)
            & (vr > p["vol"]),
            (c < lo)
            & (vr > p["vol"]),
        )

    if name == "zscore":

        z = pd.Series(c).rolling(
            p["n"]
        ).mean()

        sd = pd.Series(c).rolling(
            p["n"]
        ).std()

        zz = (
            (
                pd.Series(c) - z
            )
            / sd.replace(0, np.nan)
        ).to_numpy()

        return sig(
            zz < -p["thr"],
            zz > p["thr"],
        )

    if name == "pullback":

        r = f["rsi"]

        up = (
            (f["ema20"] > f["ema50"])
            & (c > f["ema200"])
        )

        dn = (
            (f["ema20"] < f["ema50"])
            & (c < f["ema200"])
        )

        return sig(
            up & (r < p["rsi"]),
            dn & (r > 100 - p["rsi"]),
        )

    if name == "breakout":

        n = p["n"]

        hi = (
            pd.Series(h)
            .rolling(n)
            .max()
            .shift(1)
            .to_numpy()
        )

        lo = (
            pd.Series(l)
            .rolling(n)
            .min()
            .shift(1)
            .to_numpy()
        )

        atrp = f["atr_pct"]

        base = (
            pd.Series(atrp)
            .rolling(50)
            .mean()
            .to_numpy()
        )

        exp = atrp > base

        return sig(
            (c > hi) & exp,
            (c < lo) & exp,
        )

    raise ValueError(name)


def make_candidates(
    entry,
    h1,
    ctx_iv,
):

    f = make_features(entry)

    masks, ctx = context_masks(
        entry,
        h1,
        ctx_iv,
    )

    result = []

    for name, p in SIGNALS:

        base = build_signal(
            name,
            p,
            f,
        )

        for regime in REGIMES:

            m = masks[regime].copy()

            s = base.copy()
            s[~m] = 0

            if not np.any(s):
                continue

            label = (
                name
                + "".join(
                    f" {k}={v}"
                    for k, v in p.items()
                )
            )

            result.append(
                Candidate(
                    label,
                    s,
                    regime,
                )
            )

    return f, result


# ============================================================
# SIMULATION
# ============================================================

def simulate(
    L,
    signal,
    tp_m,
    sl_m,
    hold,
    profile,
    slip,
    fee_scale=1.0,
    slip_scale=1.0,
):

    c = L["c"]
    h = L["h"]
    lo = L["l"]
    atr = L["atr"]

    slip *= slip_scale

    maker_tp_fill = (
        profile
        in ("maker_tp", "maker_both")
    )

    trades = []
    free = 0

    for j in np.flatnonzero(signal):

        if (
            j < free
            or j + 1 >= len(c)
            or not np.isfinite(atr[j])
        ):
            continue

        side = int(signal[j])
        a = atr[j]

        if a <= 0:
            continue

        if profile == "maker_both":

            if side == 1:

                if (
                    lo[j + 1]
                    > c[j] * (1 - THROUGH)
                ):
                    continue

                entry = c[j]

            else:

                if (
                    h[j + 1]
                    < c[j] * (1 + THROUGH)
                ):
                    continue

                entry = c[j]

            entry_fee = (
                FEE_MAKER
                * fee_scale
            )

        else:

            entry = (
                c[j + 1]
                * (1 + side * slip)
            )

            entry_fee = (
                FEE_TAKER
                * fee_scale
            )

        tp = (
            entry
            + side * tp_m * a
        )

        sl = (
            entry
            - side * sl_m * a
        )

        tp_touch = (
            tp * (1 + side * THROUGH)
            if maker_tp_fill
            else tp
        )

        end = min(
            j + hold,
            len(c) - 1,
        )

        exit_i = end
        exit_px = c[end]
        kind = "time"

        for k in range(
            j + 1,
            end + 1,
        ):

            hit_tp = (
                h[k] >= tp_touch
                if side == 1
                else lo[k] <= tp_touch
            )

            hit_sl = (
                lo[k] <= sl
                if side == 1
                else h[k] >= sl
            )

            if hit_sl:

                exit_i = k

                exit_px = (
                    sl
                    * (1 - side * slip)
                )

                kind = "sl"
                break

            if hit_tp:

                if maker_tp_fill:

                    exit_px = tp
                    kind = "tp"

                else:

                    exit_px = (
                        tp
                        * (1 - side * slip)
                    )

                    kind = "tp"

                exit_i = k
                break

        if kind == "time":

            exit_px *= (
                1 - side * slip
            )

        exit_fee = (
            FEE_MAKER
            if (
                kind == "tp"
                and profile != "taker"
            )
            else FEE_TAKER
        ) * fee_scale

        gross = (
            side
            * (exit_px - entry)
            / entry
        )

        net = (
            (1 + gross)
            * (1 - entry_fee)
            * (1 - exit_fee)
            - 1
        )

        trades.append(
            {
                "signal_i": j,
                "entry_i": j + 1,
                "exit_i": exit_i,
                "gross": gross,
                "net": net,
                "kind": kind,
                "side": side,
                "duration": exit_i - j,
            }
        )

        free = exit_i + 1

    return trades


def inside(
    trades,
    start,
    end,
):

    return [
        t
        for t in trades
        if (
            start <= t["signal_i"] < end
            and start <= t["entry_i"] < end
            and t["exit_i"] < end
        )
    ]


# ============================================================
# STATISTICS
# ============================================================

def empty_stats():

    return {
        "n": 0,
        "mean": np.nan,
        "se": np.nan,
        "t": np.nan,
        "gross": np.nan,
        "fees": np.nan,
        "slip": np.nan,
        "win": np.nan,
        "pf": np.nan,
        "median": np.nan,
        "p25": np.nan,
        "p75": np.nan,
        "dd": np.nan,
        "ret": np.nan,
    }


def stats(trades):

    if not trades:
        return empty_stats()

    net = np.array(
        [t["net"] for t in trades],
        float,
    )

    gross = np.array(
        [t["gross"] for t in trades],
        float,
    )

    net = net[
        np.isfinite(net)
    ]

    gross = gross[
        np.isfinite(gross)
    ]

    if len(net) == 0:
        return empty_stats()

    eq = np.cumprod(
        1 + net
    )

    peak = np.maximum.accumulate(
        eq
    )

    dd = (
        eq / peak
        - 1
    )

    wins = net[net > 0]
    losses = net[net < 0]

    if len(losses):
        pf = (
            np.sum(wins)
            / abs(np.sum(losses))
        )
    else:
        pf = np.inf

    gross_mean = (
        float(gross.mean())
        if len(gross)
        else np.nan
    )

    net_mean = float(
        net.mean()
    )

    cost_mean = (
        gross_mean - net_mean
        if np.isfinite(gross_mean)
        else np.nan
    )

    se = (
        net.std(ddof=1)
        / math.sqrt(len(net))
        if len(net) > 1
        else np.nan
    )

    if (
        np.isfinite(se)
        and se > 0
    ):
        t_stat = (
            net_mean / se
        )
    else:
        t_stat = np.nan

    return {
        "n": int(len(net)),
        "mean": net_mean,
        "se": se,
        "t": t_stat,
        "gross": gross_mean,
        "fees": cost_mean,
        "slip": 0.0,
        "win": float(
            np.mean(net > 0)
        ),
        "pf": pf,
        "median": float(
            np.median(net)
        ),
        "p25": float(
            np.percentile(net, 25)
        ),
        "p75": float(
            np.percentile(net, 75)
        ),
        "dd": float(
            dd.min()
        ),
        "ret": float(
            eq[-1] - 1
        ),
    }


def score(s):

    if (
        s["n"] < MIN_TRAIN_TRADES
    ):
        return -np.inf

    if not np.isfinite(
        s["mean"]
    ):
        return -np.inf

    pf = (
        2
        if np.isinf(s["pf"])
        else np.clip(
            s["pf"] - 1,
            -1,
            2,
        )
    )

    mean = np.clip(
        s["mean"] * 1000,
        -2,
        2,
    )

    dd = np.clip(
        abs(s["dd"]) * 10,
        0,
        2,
    )

    t_component = 0.0

    if np.isfinite(
        s["t"]
    ):
        t_component = np.clip(
            s["t"],
            -3,
            3,
        ) / 3

    n_component = min(
        math.log1p(
            s["n"]
        ) / math.log1p(150),
        1,
    )

    return (
        0.35 * t_component
        + 0.30 * pf
        + 0.20 * (
            mean / 2
        )
        + 0.15 * n_component
        - 0.15 * dd
    )


# ============================================================
# MONTE CARLO
# ============================================================

def monte_carlo(
    trades,
    capital,
    runs=MC_RUNS,
    seed=MC_SEED,
):

    # --------------------------------------------------------
    # V4.2 FIX :
    # --mc-runs 0 signifie réellement "pas de MC".
    # --------------------------------------------------------

    if (
        runs is None
        or runs <= 0
        or len(trades) < 20
    ):

        return {
            "enabled": False,
            "median": np.nan,
            "p05": np.nan,
            "p95": np.nan,
            "dd": np.nan,
        }

    r = np.array(
        [
            t["net"]
            for t in trades
        ],
        float,
    )

    r = r[
        np.isfinite(r)
    ]

    if len(r) < 20:

        return {
            "enabled": False,
            "median": np.nan,
            "p05": np.nan,
            "p95": np.nan,
            "dd": np.nan,
        }

    rng = np.random.default_rng(
        seed
    )

    finals = []
    dds = []

    for _ in range(
        int(runs)
    ):

        x = rng.choice(
            r,
            len(r),
            replace=True,
        )

        eq = (
            capital
            * np.cumprod(
                1 + x
            )
        )

        if len(eq) == 0:
            continue

        peak = np.maximum.accumulate(
            eq
        )

        finals.append(
            float(eq[-1])
        )

        dds.append(
            float(
                np.min(
                    eq / peak - 1
                )
            )
        )

    # --------------------------------------------------------
    # Protection supplémentaire.
    # --------------------------------------------------------

    if not finals:

        return {
            "enabled": False,
            "median": np.nan,
            "p05": np.nan,
            "p95": np.nan,
            "dd": np.nan,
        }

    finals = np.asarray(
        finals,
        dtype=float,
    )

    dds = np.asarray(
        dds,
        dtype=float,
    )

    return {
        "enabled": True,
        "median": float(
            np.median(finals)
        ),
        "p05": float(
            np.percentile(
                finals,
                5,
            )
        ),
        "p95": float(
            np.percentile(
                finals,
                95,
            )
        ),
        "dd": float(
            np.median(dds)
        ),
    }


# ============================================================
# BENCHMARKS
# ============================================================

def benchmark_fixed(
    L,
    start,
    end,
    hold=12,
):

    signal = np.zeros(
        len(L["c"]),
        dtype=np.int8,
    )

    signal[
        start:end:hold
    ] = 1

    return simulate(
        L,
        signal,
        2.0,
        1.0,
        hold,
        "taker",
        DEFAULT_SLIP,
    )


def benchmark_random_side(
    L,
    candidate_signal,
    tp_m,
    sl_m,
    hold,
    profile,
    slip,
    start,
    end,
    seed,
):

    rng = np.random.default_rng(
        seed
    )

    idx = np.flatnonzero(
        candidate_signal
    )

    if len(idx) == 0:
        return []

    rand_signal = np.zeros(
        len(candidate_signal),
        dtype=np.int8,
    )

    rand_signal[idx] = rng.choice(
        [-1, 1],
        size=len(idx),
    )

    trades = simulate(
        L,
        rand_signal,
        tp_m,
        sl_m,
        hold,
        profile,
        slip,
    )

    return inside(
        trades,
        start,
        end,
    )


def benchmark_random_side_mc(
    L,
    candidate_signal,
    tp_m,
    sl_m,
    hold,
    profile,
    slip,
    start,
    end,
    seed,
    runs=RANDOM_SIDE_RUNS,
):

    if runs <= 0:

        return {
            "mean": np.nan,
            "se": np.nan,
            "n": 0,
            "p05": np.nan,
            "p95": np.nan,
        }

    means = []
    ns = []

    for i in range(
        int(runs)
    ):

        trades = benchmark_random_side(
            L,
            candidate_signal,
            tp_m,
            sl_m,
            hold,
            profile,
            slip,
            start,
            end,
            seed=seed + i,
        )

        z = stats(trades)

        if np.isfinite(
            z["mean"]
        ):

            means.append(
                z["mean"]
            )

            ns.append(
                z["n"]
            )

    if not means:

        return {
            "mean": np.nan,
            "se": np.nan,
            "n": 0,
            "p05": np.nan,
            "p95": np.nan,
        }

    a = np.asarray(
        means,
        dtype=float,
    )

    return {
        "mean": float(
            np.mean(a)
        ),
        "se": float(
            np.std(
                a,
                ddof=1,
            )
            / math.sqrt(len(a))
        )
        if len(a) > 1
        else np.nan,
        "n": int(
            round(np.mean(ns))
        ),
        "p05": float(
            np.percentile(
                a,
                5,
            )
        ),
        "p95": float(
            np.percentile(
                a,
                95,
            )
        ),
    }


def benchmark_buy_hold(
    L,
    start,
    end,
):

    if end <= start + 1:
        return []

    entry = L["c"][start]
    exit_ = L["c"][end - 1]

    if (
        not np.isfinite(entry)
        or not np.isfinite(exit_)
        or entry <= 0
    ):
        return []

    gross = (
        exit_ / entry - 1
    )

    fee = FEE_TAKER * 2

    net = (
        (1 + gross)
        * (1 - fee) ** 2
        - 1
    )

    return [
        {
            "signal_i": start,
            "entry_i": start,
            "exit_i": end - 1,
            "gross": gross,
            "net": net,
            "kind": "benchmark",
            "side": 1,
            "duration": end - start,
        }
    ]


# ============================================================
# WALK FORWARD
# ============================================================

def make_folds(
    n,
    interval,
):

    bars = int(
        86_400_000
        / INTERVAL_MS[interval]
    )

    train = (
        TRAIN_DAYS * bars
    )

    test = (
        TEST_DAYS * bars
    )

    holdout = (
        FINAL_HOLDOUT_DAYS * bars
    )

    usable = n - holdout

    folds = []
    s = 0

    while (
        s + train + test
        <= usable
    ):

        folds.append(
            (
                s,
                s + train,
                s + train,
                s + train + test,
            )
        )

        s += (
            STEP_DAYS * bars
        )

    final_start = usable

    return folds, final_start


# ============================================================
# STRESS
# ============================================================

def stress(
    L,
    candidate,
    spec,
    start,
    end,
    symbol,
):

    scenarios = {
        "base": (1.0, 1.0),
        "fees+25%": (1.25, 1.0),
        "fees+50%": (1.50, 1.0),
        "fees+100%": (2.00, 1.0),
        "slip+50%": (1.0, 1.50),
        "slip+100%": (1.0, 2.00),
        "fees+50%_slip+100%": (
            1.50,
            2.00,
        ),
    }

    out = []

    for name, (
        fs,
        ss,
    ) in scenarios.items():

        tr = simulate(
            L,
            candidate.signal,
            spec["tp"],
            spec["sl"],
            spec["hold"],
            spec["profile"],
            SLIP.get(
                symbol,
                DEFAULT_SLIP,
            ),
            fs,
            ss,
        )

        tr = inside(
            tr,
            start,
            end,
        )

        z = stats(tr)

        out.append(
            {
                "scenario": name,
                "symbol": symbol,
                "mean": z["mean"],
                "pf": z["pf"],
                "win": z["win"],
                "dd": z["dd"],
                "n": z["n"],
                "return": z["ret"],
            }
        )

    return out


# ============================================================
# ROBUSTESSE
# ============================================================

def config_key(row):

    return (
        row["signal"],
        row["regime"],
        row["profile"],
        float(row["tp"]),
        float(row["sl"]),
        int(row["hold"]),
    )


def finite_median(series):

    x = pd.to_numeric(
        series,
        errors="coerce",
    )

    x = x[
        np.isfinite(x)
    ]

    if len(x) == 0:
        return np.nan

    return float(
        np.median(x)
    )


def aggregate_robustness(
    wf: pd.DataFrame,
):

    if wf.empty:
        return pd.DataFrame()

    oos = wf[
        wf["fold"] != "FINAL"
    ].copy()

    if oos.empty:
        return pd.DataFrame()

    rows = []

    group_cols = [
        "symbol",
        "interval",
        "signal",
        "regime",
        "profile",
        "tp",
        "sl",
        "hold",
    ]

    for key, g in oos.groupby(
        group_cols,
        dropna=False,
    ):

        # ----------------------------------------------------
        # IMPORTANT :
        # un fold est actif dès qu'il contient au moins
        # un trade OOS.
        #
        # Le seuil de 50 trades s'applique au cumul.
        # ----------------------------------------------------

        test_n = pd.to_numeric(
            g["test_n"],
            errors="coerce",
        ).fillna(0)

        active = g[
            test_n > 0
        ].copy()

        if active.empty:
            continue

        n_folds = len(active)

        total_trades = int(
            pd.to_numeric(
                active["test_n"],
                errors="coerce",
            ).fillna(0).sum()
        )

        test_means = pd.to_numeric(
            active["test_mean"],
            errors="coerce",
        )

        test_means = test_means[
            np.isfinite(test_means)
        ]

        if len(test_means) == 0:
            continue

        mean_oos = float(
            test_means.mean()
        )

        median_oos = float(
            test_means.median()
        )

        std_oos = (
            float(
                test_means.std(
                    ddof=1
                )
            )
            if len(test_means) > 1
            else np.nan
        )

        if (
            np.isfinite(std_oos)
            and std_oos > 0
        ):
            t_oos = (
                mean_oos
                /
                (
                    std_oos
                    / math.sqrt(
                        len(test_means)
                    )
                )
            )
        else:
            t_oos = np.nan

        positive_ratio = float(
            np.mean(
                test_means > 0
            )
        )

        edge = pd.to_numeric(
            active["edge_vs_random"],
            errors="coerce",
        )

        edge = edge[
            np.isfinite(edge)
        ]

        if len(edge):

            median_edge = float(
                np.median(edge)
            )

            mean_edge = float(
                np.mean(edge)
            )

            beat_random_ratio = float(
                np.mean(edge > 0)
            )

        else:

            median_edge = np.nan
            mean_edge = np.nan
            beat_random_ratio = 0.0

        median_pf = finite_median(
            active["test_pf"]
        )

        median_dd = finite_median(
            active["test_dd"]
        )

        # ----------------------------------------------------
        # SCORE ROBUSTE
        # ----------------------------------------------------

        stability = (
            positive_ratio
            + beat_random_ratio
        ) / 2

        if np.isfinite(
            median_pf
        ):

            pf_component = np.clip(
                median_pf - 1.0,
                -1.0,
                2.0,
            )

            pf_component = (
                pf_component + 1.0
            ) / 3.0

        else:

            pf_component = 0.0

        if np.isfinite(
            median_edge
        ):

            edge_component = np.clip(
                median_edge,
                -0.01,
                0.01,
            )

            edge_component = (
                edge_component + 0.01
            ) / 0.02

        else:

            edge_component = 0.0

        sample_component = min(
            1.0,
            total_trades / 200,
        )

        fold_component = min(
            1.0,
            n_folds / 10,
        )

        if (
            np.isfinite(std_oos)
            and std_oos > 0
        ):

            consistency = max(
                0.0,
                1.0
                - min(
                    std_oos / 0.01,
                    1.0,
                ),
            )

        else:

            consistency = 0.0

        robustness_score = (
            0.25 * stability
            + 0.18 * pf_component
            + 0.18 * edge_component
            + 0.12 * sample_component
            + 0.12 * fold_component
            + 0.15 * consistency
        )

        robust = (
            n_folds
            >= MIN_ACTIVE_FOLDS
            and total_trades
            >= MIN_TOTAL_TRADES
            and positive_ratio
            >= MIN_POSITIVE_FOLD_RATIO
            and beat_random_ratio
            >= MIN_BEAT_RANDOM_RATIO
            and np.isfinite(
                median_pf
            )
            and median_pf
            >= MIN_MEDIAN_PF
            and np.isfinite(
                median_edge
            )
            and median_edge
            >= MIN_MEDIAN_EDGE_RANDOM
        )

        rows.append(
            {
                "symbol": key[0],
                "interval": key[1],
                "signal": key[2],
                "regime": key[3],
                "profile": key[4],
                "tp": key[5],
                "sl": key[6],
                "hold": key[7],

                "active_folds": n_folds,
                "total_trades": total_trades,

                "mean_oos": mean_oos,
                "median_oos": median_oos,
                "std_oos": std_oos,
                "t_oos": t_oos,

                "positive_fold_ratio":
                    positive_ratio,

                "beat_random_ratio":
                    beat_random_ratio,

                "median_pf":
                    median_pf,

                "median_dd":
                    median_dd,

                "mean_edge_random":
                    mean_edge,

                "median_edge_random":
                    median_edge,

                "robustness_score":
                    robustness_score,

                "robust":
                    bool(robust),
            }
        )

    return pd.DataFrame(
        rows
    )


def global_robustness(
    robustness: pd.DataFrame,
):

    if robustness.empty:
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

    for key, g in robustness.groupby(
        group_cols,
        dropna=False,
    ):

        rows.append(
            {
                "interval": key[0],
                "signal": key[1],
                "regime": key[2],
                "profile": key[3],
                "tp": key[4],
                "sl": key[5],
                "hold": key[6],

                "symbols": int(
                    g["symbol"].nunique()
                ),

                "robust_symbols": int(
                    g["robust"].sum()
                ),

                "total_trades": int(
                    g["total_trades"].sum()
                ),

                "mean_oos": float(
                    g["mean_oos"].mean()
                ),

                "median_oos":
                    finite_median(
                        g["median_oos"]
                    ),

                "positive_fold_ratio":
                    float(
                        g[
                            "positive_fold_ratio"
                        ].mean()
                    ),

                "beat_random_ratio":
                    float(
                        g[
                            "beat_random_ratio"
                        ].mean()
                    ),

                "median_pf":
                    finite_median(
                        g["median_pf"]
                    ),

                "median_edge_random":
                    finite_median(
                        g[
                            "median_edge_random"
                        ]
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    result["global_robust"] = (
        (result["symbols"] >= 3)
        &
        (result["robust_symbols"] >= 2)
        &
        (result["total_trades"] >= 150)
        &
        (
            result["positive_fold_ratio"]
            >= 0.50
        )
        &
        (
            result["beat_random_ratio"]
            >= 0.50
        )
        &
        (
            result["median_pf"]
            >= 1.00
        )
        &
        (
            result["median_edge_random"]
            >= 0
        )
    )

    result = result.sort_values(
        [
            "global_robust",
            "median_edge_random",
            "median_pf",
            "total_trades",
        ],
        ascending=False,
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# FORMAT
# ============================================================

def pct(x):

    if x is None:
        return "nan"

    try:
        x = float(x)
    except (
        TypeError,
        ValueError,
    ):
        return "nan"

    if not np.isfinite(x):
        return "nan"

    return f"{x * 100:+.4f}%"


def fmt_num(x, digits=2):

    try:
        x = float(x)
    except (
        TypeError,
        ValueError,
    ):
        return "nan"

    if not np.isfinite(x):
        return "nan"

    return f"{x:.{digits}f}"


# ============================================================
# MAIN
# ============================================================

def main():

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--symbols",
        default="BTCUSDT,ETHUSDT,SOLUSDT",
    )

    ap.add_argument(
        "--intervals",
        default="5m,15m",
    )

    ap.add_argument(
        "--days",
        type=int,
        default=730,
    )

    ap.add_argument(
        "--capital",
        type=float,
        default=DEFAULT_CAPITAL,
    )

    ap.add_argument(
        "--mc-runs",
        type=int,
        default=MC_RUNS,
    )

    args = ap.parse_args()

    t0 = time.time()

    outdir = Path(
        "results"
    )

    outdir.mkdir(
        exist_ok=True
    )

    for f in (
        "walk_forward_v42.csv",
        "robustness_v42.csv",
        "global_v42.csv",
        "stress_test_v42.csv",
        "holdout_v42.csv",
        "summary_v42.md",
    ):

        p = outdir / f

        if p.exists():
            p.unlink()

    symbols = [
        x.strip()
        for x in args.symbols.split(",")
        if x.strip()
    ]

    intervals = [
        x.strip()
        for x in args.intervals.split(",")
        if x.strip()
    ]

    end_ms = int(
        time.time() * 1000
    )

    start_ms = (
        end_ms
        - args.days * 86_400_000
    )

    rows = []
    stresses = []
    holdouts = []
    log = []

    def say(s):

        print(s)
        log.append(s)

    say("# SCALP LAB V4.2")

    say(
        "Binance USD-M | "
        "signal clôturé -> entrée suivante | "
        "contexte 1h"
    )

    say(
        f"WF={TRAIN_DAYS}j/"
        f"{TEST_DAYS}j/"
        f"{STEP_DAYS}j | "
        f"FINAL HOLDOUT="
        f"{FINAL_HOLDOUT_DAYS}j"
    )

    say(
        f"Coûts taker={FEE_TAKER:.2%} | "
        f"maker={FEE_MAKER:.2%} | "
        f"candidats={len(SIGNALS)}"
    )

    say(
        "ROBUSTNESS | "
        f"folds>={MIN_ACTIVE_FOLDS} | "
        f"trades>={MIN_TOTAL_TRADES} | "
        f"positive>={MIN_POSITIVE_FOLD_RATIO:.0%} | "
        f">random>={MIN_BEAT_RANDOM_RATIO:.0%} | "
        f"PF>={MIN_MEDIAN_PF:.2f}"
    )

    say(
        f"MONTE-CARLO | "
        f"runs={args.mc_runs}"
    )

    say("")

    for interval in intervals:

        for symbol in symbols:

            t_pair = time.time()

            ctx_iv = (
                CONTEXT_ENTRY_TO_CTX.get(
                    interval,
                    "1h",
                )
            )

            warmup_days = (
                CONTEXT_WARMUP_DAYS.get(
                    ctx_iv,
                    12,
                )
            )

            min_ctx_len = (
                CONTEXT_MIN_LEN.get(
                    ctx_iv,
                    200,
                )
            )

            min_entry_candles = int(
                (
                    TRAIN_DAYS
                    + TEST_DAYS
                    + FINAL_HOLDOUT_DAYS
                )
                * 86_400_000
                / INTERVAL_MS[interval]
                * 0.5
            )

            entry = to_frame(
                fetch_vision(
                    symbol,
                    interval,
                    start_ms,
                    end_ms,
                )
            )

            h1 = to_frame(
                fetch_vision(
                    symbol,
                    ctx_iv,
                    start_ms
                    - warmup_days
                    * 86_400_000,
                    end_ms,
                )
            )

            if (
                len(entry)
                < min_entry_candles
                or len(h1)
                < min_ctx_len
            ):

                say(
                    f"{symbol} {interval} | "
                    f"données insuffisantes "
                    f"({len(entry)} entrée, "
                    f"{len(h1)} contexte)"
                )

                continue

            entry = entry[
                entry.time >= start_ms
            ].reset_index(
                drop=True
            )

            folds, holdout_start = (
                make_folds(
                    len(entry),
                    interval,
                )
            )

            ef, candidates = (
                make_candidates(
                    entry,
                    h1,
                    ctx_iv,
                )
            )

            L = ef

            say(
                f"{symbol} {interval} | "
                f"{len(entry)} candles | "
                f"{len(candidates)} candidats | "
                f"{len(folds)} folds | "
                f"holdout={FINAL_HOLDOUT_DAYS}j"
            )

            if len(folds) < MIN_ACTIVE_FOLDS:

                say(
                    f"  WARNING: seulement "
                    f"{len(folds)} folds OOS ; "
                    f"minimum requis="
                    f"{MIN_ACTIVE_FOLDS}"
                )

            # ------------------------------------------------
            # WALK FORWARD
            # ------------------------------------------------

            for fi, (
                tr0,
                tr1,
                te0,
                te1,
            ) in enumerate(
                folds,
                1,
            ):

                best = None

                for ci, cand in enumerate(
                    candidates
                ):

                    for tp, sl, hold in EXITS:

                        for profile in PROFILES:

                            all_trades = simulate(
                                L,
                                cand.signal,
                                tp,
                                sl,
                                hold,
                                profile,
                                SLIP.get(
                                    symbol,
                                    DEFAULT_SLIP,
                                ),
                            )

                            train = inside(
                                all_trades,
                                tr0,
                                tr1,
                            )

                            st = stats(
                                train
                            )

                            sc = score(
                                st
                            )

                            if (
                                best is None
                                or sc
                                > best["score"]
                            ):

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

                if (
                    best is None
                    or not np.isfinite(
                        best["score"]
                    )
                ):

                    say(
                        f"  F{fi} "
                        f"| aucune configuration "
                        f"avec >= "
                        f"{MIN_TRAIN_TRADES} "
                        f"trades train"
                    )

                    continue

                test_trades = inside(
                    simulate(
                        L,
                        best["candidate"].signal,
                        best["tp"],
                        best["sl"],
                        best["hold"],
                        best["profile"],
                        SLIP.get(
                            symbol,
                            DEFAULT_SLIP,
                        ),
                    ),
                    te0,
                    te1,
                )

                ts = stats(
                    test_trades
                )

                # ------------------------------------------------
                # MC
                # ------------------------------------------------

                mc = monte_carlo(
                    test_trades,
                    args.capital,
                    args.mc_runs,
                    MC_SEED + fi,
                )

                bench = benchmark_fixed(
                    L,
                    te0,
                    te1,
                )

                bs = stats(
                    bench
                )

                bh = benchmark_buy_hold(
                    L,
                    te0,
                    te1,
                )

                bhs = stats(
                    bh
                )

                rs = (
                    benchmark_random_side_mc(
                        L,
                        best[
                            "candidate"
                        ].signal,
                        best["tp"],
                        best["sl"],
                        best["hold"],
                        best["profile"],
                        SLIP.get(
                            symbol,
                            DEFAULT_SLIP,
                        ),
                        te0,
                        te1,
                        seed=(
                            MC_SEED
                            + fi * 1000
                        ),
                        runs=RANDOM_SIDE_RUNS,
                    )
                )

                edge_vs_random = (
                    ts["mean"]
                    - rs["mean"]
                    if (
                        np.isfinite(
                            ts["mean"]
                        )
                        and np.isfinite(
                            rs["mean"]
                        )
                    )
                    else np.nan
                )

                spec = {
                    "tp": best["tp"],
                    "sl": best["sl"],
                    "hold": best["hold"],
                    "profile": best["profile"],
                }

                stress_rows = stress(
                    L,
                    best["candidate"],
                    spec,
                    te0,
                    te1,
                    symbol,
                )

                stresses.extend(
                    [
                        {
                            **x,
                            "interval": interval,
                            "fold": fi,
                        }
                        for x in stress_rows
                    ]
                )

                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "fold": fi,
                        "candidate":
                            best["candidate_i"],
                        "signal":
                            best["candidate"].name,
                        "regime":
                            best["candidate"].regime,
                        "profile":
                            best["profile"],
                        "tp":
                            best["tp"],
                        "sl":
                            best["sl"],
                        "hold":
                            best["hold"],

                        "train_n":
                            best["train"]["n"],
                        "train_mean":
                            best["train"]["mean"],
                        "train_pf":
                            best["train"]["pf"],

                        "test_n":
                            ts["n"],
                        "test_gross":
                            ts["gross"],
                        "test_mean":
                            ts["mean"],
                        "test_se":
                            ts["se"],
                        "test_t":
                            ts["t"],
                        "test_fees":
                            ts["fees"],
                        "test_win":
                            ts["win"],
                        "test_pf":
                            ts["pf"],
                        "test_median":
                            ts["median"],
                        "test_p25":
                            ts["p25"],
                        "test_p75":
                            ts["p75"],
                        "test_dd":
                            ts["dd"],
                        "test_return":
                            ts["ret"],

                        "mc_enabled":
                            mc["enabled"],
                        "mc_median":
                            mc["median"],
                        "mc_p05":
                            mc["p05"],
                        "mc_p95":
                            mc["p95"],
                        "mc_dd":
                            mc["dd"],

                        "bench_fixed_mean":
                            bs["mean"],
                        "bench_fixed_pf":
                            bs["pf"],

                        "bench_random_mean":
                            rs["mean"],
                        "bench_random_se":
                            rs["se"],
                        "bench_random_p05":
                            rs["p05"],
                        "bench_random_p95":
                            rs["p95"],
                        "bench_random_n":
                            rs["n"],

                        "edge_vs_random":
                            edge_vs_random,

                        "bench_bh_return":
                            bhs["ret"],
                    }
                )

                say(
                    f"  F{fi} "
                    f"{best['candidate'].name} / "
                    f"{best['candidate'].regime} / "
                    f"{best['profile']} | "
                    f"TEST {pct(ts['mean'])} "
                    f"(t={fmt_num(ts['t'], 1)}) | "
                    f"hasard100 "
                    f"{pct(rs['mean'])} | "
                    f"delta "
                    f"{pct(edge_vs_random)} | "
                    f"PF={fmt_num(ts['pf'], 2)} | "
                    f"DD={pct(ts['dd'])} | "
                    f"n={ts['n']}"
                )

            # ------------------------------------------------
            # ROBUSTESSE PROVISOIRE POUR CET ACTIF
            # ------------------------------------------------

            current_wf = pd.DataFrame(
                [
                    x
                    for x in rows
                    if (
                        x["symbol"] == symbol
                        and x["interval"] == interval
                        and x["fold"] != "FINAL"
                    )
                ]
            )

            current_robustness = (
                aggregate_robustness(
                    current_wf
                )
                if not current_wf.empty
                else pd.DataFrame()
            )

            robust_candidates = (
                current_robustness[
                    current_robustness["robust"]
                ].copy()
                if not current_robustness.empty
                else pd.DataFrame()
            )

            # ------------------------------------------------
            # HOLDOUT
            #
            # V4.2 :
            # PAS DE HOLDOUT si aucune configuration
            # ne satisfait les critères de robustesse.
            # ------------------------------------------------

            if (
                holdout_start < len(entry)
                and not robust_candidates.empty
            ):

                robust_candidates = (
                    robust_candidates.sort_values(
                        [
                            "robustness_score",
                            "median_edge_random",
                            "median_pf",
                        ],
                        ascending=False,
                    )
                )

                chosen = (
                    robust_candidates.iloc[0]
                )

                chosen_signal = (
                    chosen["signal"]
                )

                chosen_regime = (
                    chosen["regime"]
                )

                chosen_profile = (
                    chosen["profile"]
                )

                chosen_tp = float(
                    chosen["tp"]
                )

                chosen_sl = float(
                    chosen["sl"]
                )

                chosen_hold = int(
                    chosen["hold"]
                )

                candidate_index = None

                for ci, cand in enumerate(
                    candidates
                ):

                    if (
                        cand.name
                        == chosen_signal
                        and cand.regime
                        == chosen_regime
                    ):

                        candidate_index = ci
                        break

                if candidate_index is None:

                    say(
                        "  FINAL HOLDOUT "
                        "| configuration robuste "
                        "introuvable dans les candidats"
                    )

                else:

                    cand = candidates[
                        candidate_index
                    ]

                    hold_trades = inside(
                        simulate(
                            L,
                            cand.signal,
                            chosen_tp,
                            chosen_sl,
                            chosen_hold,
                            chosen_profile,
                            SLIP.get(
                                symbol,
                                DEFAULT_SLIP,
                            ),
                        ),
                        holdout_start,
                        len(entry),
                    )

                    hs = stats(
                        hold_trades
                    )

                    hmc = monte_carlo(
                        hold_trades,
                        args.capital,
                        args.mc_runs,
                        MC_SEED + 999,
                    )

                    holdout_row = {
                        "symbol": symbol,
                        "interval": interval,
                        "signal": chosen_signal,
                        "regime": chosen_regime,
                        "profile": chosen_profile,
                        "tp": chosen_tp,
                        "sl": chosen_sl,
                        "hold": chosen_hold,
                        "holdout_days":
                            FINAL_HOLDOUT_DAYS,

                        "robust_active_folds":
                            int(
                                chosen[
                                    "active_folds"
                                ]
                            ),

                        "robust_total_trades":
                            int(
                                chosen[
                                    "total_trades"
                                ]
                            ),

                        "robust_positive_ratio":
                            float(
                                chosen[
                                    "positive_fold_ratio"
                                ]
                            ),

                        "robust_beat_random_ratio":
                            float(
                                chosen[
                                    "beat_random_ratio"
                                ]
                            ),

                        "robust_median_pf":
                            float(
                                chosen[
                                    "median_pf"
                                ]
                            ),

                        "robust_median_edge_random":
                            float(
                                chosen[
                                    "median_edge_random"
                                ]
                            ),

                        "robustness_score":
                            float(
                                chosen[
                                    "robustness_score"
                                ]
                            ),

                        "holdout_n":
                            hs["n"],
                        "holdout_mean":
                            hs["mean"],
                        "holdout_t":
                            hs["t"],
                        "holdout_pf":
                            hs["pf"],
                        "holdout_dd":
                            hs["dd"],
                        "holdout_return":
                            hs["ret"],

                        "mc_enabled":
                            hmc["enabled"],
                        "mc_median":
                            hmc["median"],
                        "mc_p05":
                            hmc["p05"],
                        "mc_p95":
                            hmc["p95"],
                        "mc_dd":
                            hmc["dd"],
                    }

                    holdouts.append(
                        holdout_row
                    )

                    rows.append(
                        {
                            "symbol": symbol,
                            "interval": interval,
                            "fold": "FINAL",
                            "candidate":
                                candidate_index,
                            "signal":
                                chosen_signal,
                            "regime":
                                chosen_regime,
                            "profile":
                                chosen_profile,
                            "tp":
                                chosen_tp,
                            "sl":
                                chosen_sl,
                            "hold":
                                chosen_hold,

                            "train_n":
                                np.nan,
                            "train_mean":
                                np.nan,
                            "train_pf":
                                np.nan,

                            "test_n":
                                hs["n"],
                            "test_gross":
                                hs["gross"],
                            "test_mean":
                                hs["mean"],
                            "test_se":
                                hs["se"],
                            "test_t":
                                hs["t"],
                            "test_fees":
                                hs["fees"],
                            "test_win":
                                hs["win"],
                            "test_pf":
                                hs["pf"],
                            "test_median":
                                hs["median"],
                            "test_p25":
                                hs["p25"],
                            "test_p75":
                                hs["p75"],
                            "test_dd":
                                hs["dd"],
                            "test_return":
                                hs["ret"],

                            "mc_enabled":
                                hmc["enabled"],
                            "mc_median":
                                hmc["median"],
                            "mc_p05":
                                hmc["p05"],
                            "mc_p95":
                                hmc["p95"],
                            "mc_dd":
                                hmc["dd"],

                            "bench_fixed_mean":
                                np.nan,
                            "bench_fixed_pf":
                                np.nan,
                            "bench_random_mean":
                                np.nan,
                            "bench_random_se":
                                np.nan,
                            "bench_random_p05":
                                np.nan,
                            "bench_random_p95":
                                np.nan,
                            "bench_random_n":
                                np.nan,
                            "edge_vs_random":
                                np.nan,
                            "bench_bh_return":
                                np.nan,
                        }
                    )

                    say(
                        f"  FINAL HOLDOUT "
                        f"{FINAL_HOLDOUT_DAYS}j | "
                        f"{chosen_signal} | "
                        f"{chosen_profile} | "
                        f"{pct(hs['mean'])} "
                        f"(t={fmt_num(hs['t'], 1)}) | "
                        f"PF={fmt_num(hs['pf'], 2)} | "
                        f"DD={pct(hs['dd'])} | "
                        f"n={hs['n']}"
                    )

            else:

                if holdout_start >= len(entry):

                    say(
                        "  FINAL HOLDOUT "
                        "| données insuffisantes"
                    )

                elif robust_candidates.empty:

                    say(
                        "  FINAL HOLDOUT "
                        "| NON EXÉCUTÉ : "
                        "aucune configuration robuste"
                    )

            say(
                f"  -> {symbol} {interval} "
                f"terminé en "
                f"{(time.time() - t_pair) / 60:.1f} min"
            )

    # ========================================================
    # DATAFRAMES
    # ========================================================

    wf = pd.DataFrame(
        rows
    )

    st = pd.DataFrame(
        stresses
    )

    if wf.empty:

        robustness = pd.DataFrame()
        global_df = pd.DataFrame()

    else:

        robustness = (
            aggregate_robustness(
                wf
            )
        )

        global_df = (
            global_robustness(
                robustness
            )
        )

    wf.to_csv(
        outdir
        / "walk_forward_v42.csv",
        index=False,
    )

    st.to_csv(
        outdir
        / "stress_test_v42.csv",
        index=False,
    )

    robustness.to_csv(
        outdir
        / "robustness_v42.csv",
        index=False,
    )

    global_df.to_csv(
        outdir
        / "global_v42.csv",
        index=False,
    )

    pd.DataFrame(
        holdouts
    ).to_csv(
        outdir
        / "holdout_v42.csv",
        index=False,
    )

    # ========================================================
    # REPORT
    # ========================================================

    report = [
        "# SCALP LAB V4.2 — rapport de recherche",
        "",
        "## Configuration",
        "",
        "- Binance Futures USD-M",
        "- OHLCV uniquement",
        f"- TRAIN : {TRAIN_DAYS} jours",
        f"- TEST : {TEST_DAYS} jours",
        f"- STEP : {STEP_DAYS} jours",
        f"- FINAL HOLDOUT : {FINAL_HOLDOUT_DAYS} jours",
        f"- Frais taker : {FEE_TAKER:.2%}/côté",
        f"- Frais maker : {FEE_MAKER:.2%}/côté",
        f"- Monte-Carlo demandé : {args.mc_runs}",
        "",
        "## Critères de robustesse",
        "",
        f"- folds actifs minimum : {MIN_ACTIVE_FOLDS}",
        f"- trades cumulés minimum : {MIN_TOTAL_TRADES}",
        f"- folds positifs minimum : {MIN_POSITIVE_FOLD_RATIO:.0%}",
        f"- folds > hasard minimum : {MIN_BEAT_RANDOM_RATIO:.0%}",
        f"- PF médian minimum : {MIN_MEDIAN_PF:.2f}",
        f"- edge médian vs hasard minimum : {MIN_MEDIAN_EDGE_RANDOM:.4%}",
        "",
        "Une configuration n'est dite ROBUSTE que si "
        "tous les critères sont satisfaits.",
        "",
        "## Walk-forward OOS",
        "",
    ]

    valid = (
        wf[
            wf["fold"] != "FINAL"
        ]
        if not wf.empty
        else wf
    )

    if not valid.empty:

        for interval in intervals:

            x = valid[
                valid.interval == interval
            ]

            if x.empty:
                continue

            positive = int(
                (
                    pd.to_numeric(
                        x.test_mean,
                        errors="coerce",
                    )
                    > 0
                ).sum()
            )

            edge_values = pd.to_numeric(
                x.edge_vs_random,
                errors="coerce",
            )

            beat_random = int(
                (
                    edge_values > 0
                ).sum()
            )

            test_mean = pd.to_numeric(
                x.test_mean,
                errors="coerce",
            )

            test_pf = pd.to_numeric(
                x.test_pf,
                errors="coerce",
            )

            test_dd = pd.to_numeric(
                x.test_dd,
                errors="coerce",
            )

            test_median = pd.to_numeric(
                x.test_median,
                errors="coerce",
            )

            random_mean = pd.to_numeric(
                x.bench_random_mean,
                errors="coerce",
            )

            report += [
                f"### {interval}",
                "",
                "| mesure | valeur |",
                "|---|---:|",
                f"| folds | {len(x)} |",
                f"| test mean/trade | "
                f"{pct(test_mean.mean())} |",
                f"| folds positifs | "
                f"{positive}/{len(x)} |",
                f"| PF médian | "
                f"{fmt_num(test_pf.median(), 2)} |",
                f"| DD médian | "
                f"{pct(test_dd.median())} |",
                f"| médiane trade | "
                f"{pct(test_median.median())} |",
                f"| hasard moyen | "
                f"{pct(random_mean.mean())} |",
                f"| edge moyen vs hasard | "
                f"{pct(edge_values.mean())} |",
                f"| folds > hasard | "
                f"{beat_random}/{len(x)} |",
                "",
            ]

    report += [
        "## Configurations robustes",
        "",
    ]

    if robustness.empty:

        report.append(
            "Aucune configuration candidate."
        )

    else:

        robust = (
            robustness[
                robustness["robust"]
            ]
            .sort_values(
                [
                    "robustness_score",
                    "median_edge_random",
                    "median_pf",
                ],
                ascending=False,
            )
        )

        report += [
            "| actif | intervalle | signal | régime | "
            "profil | folds | trades | mean OOS | "
            "PF médian | edge médian | score |",
            "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]

        if robust.empty:

            report.append(
                "| — | — | Aucune configuration ne satisfait "
                "les critères | — | — | — | — | — | — | — | — |"
            )

        else:

            for _, r in robust.head(
                30
            ).iterrows():

                report.append(
                    f"| {r.symbol} | "
                    f"{r.interval} | "
                    f"{r.signal} | "
                    f"{r.regime} | "
                    f"{r.profile} | "
                    f"{int(r.active_folds)} | "
                    f"{int(r.total_trades)} | "
                    f"{pct(r.mean_oos)} | "
                    f"{fmt_num(r.median_pf, 2)} | "
                    f"{pct(r.median_edge_random)} | "
                    f"{fmt_num(r.robustness_score, 3)} |"
                )

    report += [
        "",
        "## Analyse globale multi-actifs",
        "",
    ]

    if global_df.empty:

        report.append(
            "Aucune donnée globale."
        )

    else:

        report += [
            "| intervalle | signal | régime | profil | "
            "actifs | actifs robustes | trades | "
            "PF médian | edge médian | global robuste |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]

        for _, r in global_df.head(
            30
        ).iterrows():

            report.append(
                f"| {r.interval} | "
                f"{r.signal} | "
                f"{r.regime} | "
                f"{r.profile} | "
                f"{r.symbols} | "
                f"{r.robust_symbols} | "
                f"{r.total_trades} | "
                f"{fmt_num(r.median_pf, 2)} | "
                f"{pct(r.median_edge_random)} | "
                f"{r.global_robust} |"
            )

    report += [
        "",
        "## Final holdout",
        "",
        "| actif | intervalle | signal | mean | t | PF | DD | n | return |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    if not holdouts:

        report.append(
            "| — | — | Aucun holdout exécuté : "
            "aucune configuration robuste | — | — | — | — | — | — |"
        )

    else:

        for h in holdouts:

            report.append(
                f"| {h['symbol']} | "
                f"{h['interval']} | "
                f"{h['signal']} | "
                f"{pct(h['holdout_mean'])} | "
                f"{fmt_num(h['holdout_t'], 1)} | "
                f"{fmt_num(h['holdout_pf'], 2)} | "
                f"{pct(h['holdout_dd'])} | "
                f"{h['holdout_n']} | "
                f"{pct(h['holdout_return'])} |"
            )

    report += [
        "",
        "## Robustesse des coûts",
        "",
    ]

    if not st.empty:

        g = (
            st.groupby(
                "scenario"
            )
            .agg(
                mean=("mean", "mean"),
                pf=("pf", "median"),
                dd=("dd", "median"),
            )
            .reset_index()
        )

        report += [
            "| scénario | mean/trade | PF médian | DD médian |",
            "|---|---:|---:|---:|",
        ]

        for _, r in g.iterrows():

            report.append(
                f"| {r.scenario} | "
                f"{pct(r['mean'])} | "
                f"{fmt_num(r.pf, 2)} | "
                f"{pct(r.dd)} |"
            )

    else:

        report.append(
            "Aucun test de stress disponible."
        )

    report += [
        "",
        "## Limites",
        "",
        "- OHLCV uniquement.",
        "- Pas de carnet d'ordres.",
        "- Pas de funding.",
        "- Pas de latence réseau réelle.",
        "- Ambiguïté intrabougie TP/SL : priorité SL.",
        "- Exécution maker approximée.",
        "- Monte-Carlo basé sur les trades observés.",
        "- Le final holdout n'est pas utilisé pour le filtre de robustesse.",
        "- Une configuration avec trop peu de trades est exclue.",
        "- Un fold OOS avec n=0 n'est pas considéré comme actif.",
        "- Le holdout final n'est exécuté que si une configuration "
        "passe tous les critères de robustesse.",
        "",
        "## Règle d'interprétation",
        "",
        "Une absence de configuration robuste constitue un résultat "
        "valide de la recherche. Les seuils ne doivent pas être abaissés "
        "après observation des résultats uniquement pour faire apparaître "
        "une configuration positive.",
    ]

    (
        outdir / "summary_v42.md"
    ).write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    # ========================================================
    # CONSOLE FINAL
    # ========================================================

    print("")
    print("=" * 72)
    print("SCALP LAB V4.2 TERMINÉ")
    print("=" * 72)

    print(
        f"Durée : "
        f"{(time.time() - t0) / 60:.1f} min"
    )

    print(
        f"Folds OOS : "
        f"{len(valid)}"
    )

    if not robustness.empty:

        print(
            "Configurations robustes : "
            f"{int(robustness['robust'].sum())}"
        )

    else:

        print(
            "Configurations robustes : 0"
        )

    print(
        f"Monte-Carlo : "
        f"{args.mc_runs} runs"
    )

    print("")
    print(
        "results/summary_v42.md"
    )
    print(
        "results/walk_forward_v42.csv"
    )
    print(
        "results/robustness_v42.csv"
    )
    print(
        "results/global_v42.csv"
    )
    print(
        "results/holdout_v42.csv"
    )
    print(
        "results/stress_test_v42.csv"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()
