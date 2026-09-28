"""
SCALP LAB V3.1 — laboratoire de recherche pour scalping Binance USD-M.

V3.1 = V3 avec :
    - log console compact
    - séparation TRAIN / TEST stricte
    - aucun trade ne peut traverser une frontière TRAIN/TEST
    - stress-test exécuté sur le dataset complet
    - candidat sélectionné conservé par index global
    - nettoyage des anciens résultats V2/V3
    - rapport final V3 uniquement

IMPORTANT:
    V3.1 ne change pas les hypothèses de trading de V3.
    Elle corrige principalement la méthodologie et la lisibilité.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

INTERVAL_MS = {
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
}

FEE_TAKER = 0.0005
FEE_MAKER = 0.0002
THROUGH = 0.00005

SLIP = {
    "BTCUSDT": 0.0001,
    "ETHUSDT": 0.00015,
    "SOLUSDT": 0.0003,
    "XRPUSDT": 0.0003,
    "BNBUSDT": 0.0002,
}

DEFAULT_SLIP = 0.0003

PROFILES = (
    "taker",
    "maker_tp",
    "maker_both",
)

EXITS = [
    (1.5, 1.0, 12),
    (2.0, 1.0, 24),
    (3.0, 1.5, 36),
    (2.0, 2.0, 24),
]

TRAIN_DAYS = 180
TEST_DAYS = 45
STEP_DAYS = 45

MIN_TRAIN_TRADES = 80

MC_RUNS = 5000
MC_SEED = 20260928

DEFAULT_CAPITAL = 100.0


# ============================================================
# V3 CONTEXTE
# ============================================================

EMA_SEPARATION_MIN = 0.0025
EMA_SLOPE_MIN = 0.00020

VOL_LOW_QUANTILE = 0.33
VOL_HIGH_QUANTILE = 0.67

HIGH_VOL_MAX_MULT = 1.75

MAX_DISTANCE_EMA200 = 0.045


# ============================================================
# DONNÉES
# ============================================================

def _read_zip_csv(content: bytes):
    z = zipfile.ZipFile(io.BytesIO(content))

    out = []

    for line in z.read(z.namelist()[0]).decode().splitlines():
        p = line.split(",")

        if p and p[0].strip().isdigit():
            out.append(p[:12])

    return out


def fetch_vision(
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
):
    """Télécharge les klines publiques Binance USD-M."""

    base = "https://data.binance.vision/data/futures/um"

    start = datetime.fromtimestamp(
        start_ms / 1000,
        timezone.utc,
    ).date()

    end = datetime.fromtimestamp(
        end_ms / 1000,
        timezone.utc,
    ).date()

    today = datetime.now(timezone.utc).date()

    rows = []

    day = start.replace(day=1)

    while day <= end:

        nxt = (
            day.replace(day=28) + timedelta(days=4)
        ).replace(day=1)

        if nxt <= today.replace(day=1):

            name = f"{symbol}-{interval}-{day:%Y-%m}"

            url = (
                f"{base}/monthly/klines/"
                f"{symbol}/{interval}/{name}.zip"
            )

            try:
                r = requests.get(
                    url,
                    timeout=90,
                )

                if r.status_code == 200:
                    rows += _read_zip_csv(r.content)

            except requests.RequestException:
                pass

            day = nxt

        else:

            d = day

            while d < today and d <= end:

                name = f"{symbol}-{interval}-{d:%Y-%m-%d}"

                url = (
                    f"{base}/daily/klines/"
                    f"{symbol}/{interval}/{name}.zip"
                )

                try:
                    r = requests.get(
                        url,
                        timeout=90,
                    )

                    if r.status_code == 200:
                        rows += _read_zip_csv(r.content)

                except requests.RequestException:
                    pass

                d += timedelta(days=1)

            break

    return rows


def to_frame(rows):

    if not rows:
        return pd.DataFrame(
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

    d = pd.DataFrame(
        rows,
        columns=[
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
        ],
    )

    for k in [
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        d[k] = pd.to_numeric(
            d[k],
            errors="coerce",
        )

    d = d.dropna(
        subset=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )

    return (
        d.drop_duplicates("time")
        .sort_values("time")
        .reset_index(drop=True)
    )


# ============================================================
# INDICATEURS
# ============================================================

def make_features(
    d: pd.DataFrame,
) -> dict[str, pd.Series]:

    c = d["close"]
    h = d["high"]
    l = d["low"]
    v = d["volume"]

    delta = c.diff()

    up = (
        delta.clip(lower=0)
        .ewm(
            alpha=1 / 14,
            adjust=False,
        )
        .mean()
    )

    dn = (
        (-delta.clip(upper=0))
        .ewm(
            alpha=1 / 14,
            adjust=False,
        )
        .mean()
    )

    rsi = 100 - 100 / (
        1 + up / dn.replace(0, np.nan)
    )

    pc = c.shift(1)

    tr = pd.concat(
        [
            h - l,
            (h - pc).abs(),
            (l - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = (
        tr.ewm(
            alpha=1 / 14,
            adjust=False,
        )
        .mean()
    )

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

    ret = c.pct_change()

    vol20 = ret.rolling(20).std()

    bb_mid = c.rolling(20).mean()
    bb_sd = c.rolling(20).std()

    bb_z = (
        (c - bb_mid)
        / bb_sd.replace(0, np.nan)
    )

    bb_width = (
        (2 * bb_sd)
        / bb_mid.replace(0, np.nan)
    )

    rv20 = v.rolling(20).mean()

    vol_ratio = (
        v / rv20.replace(0, np.nan)
    )

    tp = (h + l + c) / 3

    vwaps = {}

    for n in (48, 96):

        vwaps[n] = (
            (tp * v).rolling(n).sum()
            / v.rolling(n).sum().replace(
                0,
                np.nan,
            )
        )

    ema20_slope = (
        ema20 / ema20.shift(6) - 1
    )

    ema50_slope = (
        ema50 / ema50.shift(12) - 1
    )

    ema_separation = (
        (ema20 - ema50).abs()
        / c.replace(0, np.nan).abs()
    )

    distance_ema200 = (
        (c - ema200).abs()
        / c.replace(0, np.nan).abs()
    )

    atr_pct = (
        atr / c.replace(0, np.nan)
    )

    atr_baseline = (
        atr_pct.rolling(96).median()
    )

    atr_relative = (
        atr_pct
        / atr_baseline.replace(0, np.nan)
    )

    return {
        "o": d["open"],
        "h": h,
        "l": l,
        "c": c,
        "v": v,
        "rsi": rsi,
        "atr": atr,
        "ema9": ema9,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "ret": ret,
        "vol20": vol20,
        "bb_z": bb_z,
        "bb_width": bb_width,
        "vol_ratio": vol_ratio,
        "vwap48": vwaps[48],
        "vwap96": vwaps[96],
        "ema20_slope": ema20_slope,
        "ema50_slope": ema50_slope,
        "ema_separation": ema_separation,
        "distance_ema200": distance_ema200,
        "atr_pct": atr_pct,
        "atr_relative": atr_relative,
    }


# ============================================================
# ALIGNEMENT 1H
# ============================================================

def align_1h_features(
    entry: pd.DataFrame,
    h1: pd.DataFrame,
):

    hf = make_features(h1)

    base = pd.DataFrame(
        {
            "time": entry["time"].values,
        }
    )

    src = pd.DataFrame(
        {
            "time": (
                h1["time"].values
                + INTERVAL_MS["1h"]
            ),
        }
    )

    names = (
        "c",
        "ema20",
        "ema50",
        "ema200",
        "atr",
        "rsi",
        "bb_width",
        "ema20_slope",
        "ema50_slope",
        "ema_separation",
        "distance_ema200",
        "atr_pct",
        "atr_relative",
    )

    for name in names:
        src[name] = hf[name].values

    merged = pd.merge_asof(
        base.sort_values("time"),
        src.sort_values("time"),
        on="time",
        direction="backward",
    )

    return {
        name: merged[name]
        for name in names
    }


# ============================================================
# CONTEXTE V3
# ============================================================

def classify_volatility(
    h1f: dict[str, pd.Series],
):

    atr_rel = np.asarray(
        h1f["atr_relative"],
        dtype=float,
    )

    valid = np.isfinite(atr_rel)

    low = np.zeros_like(valid)
    normal = np.zeros_like(valid)
    high = np.zeros_like(valid)

    if valid.sum() < 100:

        normal[valid] = True

        return {
            "low": low,
            "normal": normal,
            "high": high,
        }

    vals = atr_rel[valid]

    q_low = np.nanquantile(
        vals,
        VOL_LOW_QUANTILE,
    )

    q_high = np.nanquantile(
        vals,
        VOL_HIGH_QUANTILE,
    )

    low = (
        valid
        & (atr_rel <= q_low)
    )

    normal = (
        valid
        & (atr_rel > q_low)
        & (atr_rel <= q_high)
    )

    high = (
        valid
        & (atr_rel > q_high)
        & (atr_rel <= HIGH_VOL_MAX_MULT)
    )

    return {
        "low": low,
        "normal": normal,
        "high": high,
    }


def context_masks(
    h1f: dict[str, pd.Series],
):

    c = np.asarray(
        h1f["c"],
        dtype=float,
    )

    e20 = np.asarray(
        h1f["ema20"],
        dtype=float,
    )

    e50 = np.asarray(
        h1f["ema50"],
        dtype=float,
    )

    e200 = np.asarray(
        h1f["ema200"],
        dtype=float,
    )

    slope20 = np.asarray(
        h1f["ema20_slope"],
        dtype=float,
    )

    slope50 = np.asarray(
        h1f["ema50_slope"],
        dtype=float,
    )

    separation = np.asarray(
        h1f["ema_separation"],
        dtype=float,
    )

    distance = np.asarray(
        h1f["distance_ema200"],
        dtype=float,
    )

    valid = (
        np.isfinite(c)
        & np.isfinite(e20)
        & np.isfinite(e50)
        & np.isfinite(e200)
        & np.isfinite(slope20)
        & np.isfinite(slope50)
        & np.isfinite(separation)
        & np.isfinite(distance)
    )

    strong_up = (
        valid
        & (e20 > e50)
        & (c > e200)
        & (slope20 > EMA_SLOPE_MIN)
        & (slope50 > 0)
        & (separation >= EMA_SEPARATION_MIN)
        & (distance <= MAX_DISTANCE_EMA200)
    )

    strong_down = (
        valid
        & (e20 < e50)
        & (c < e200)
        & (slope20 < -EMA_SLOPE_MIN)
        & (slope50 < 0)
        & (separation >= EMA_SEPARATION_MIN)
        & (distance <= MAX_DISTANCE_EMA200)
    )

    trend_up = (
        valid
        & (e20 > e50)
        & (c > e200)
        & (separation >= EMA_SEPARATION_MIN)
        & (distance <= MAX_DISTANCE_EMA200)
    )

    trend_down = (
        valid
        & (e20 < e50)
        & (c < e200)
        & (separation >= EMA_SEPARATION_MIN)
        & (distance <= MAX_DISTANCE_EMA200)
    )

    range_ = (
        valid
        & (
            separation
            < EMA_SEPARATION_MIN
        )
        & (distance < 0.02)
    )

    vol = classify_volatility(h1f)

    return {
        "strong_trend": (
            strong_up,
            strong_down,
        ),
        "trend": (
            trend_up,
            trend_down,
        ),
        "trend_up": (
            trend_up,
            np.zeros_like(trend_down),
        ),
        "range": (
            range_,
            range_,
        ),
        "all": (
            valid,
            valid,
        ),
        "volatility": vol,
    }


# ============================================================
# SIGNAUX
# ============================================================

@dataclass(frozen=True)
class Candidate:

    name: str
    signal: np.ndarray
    regime: str
    volatility: str


def _sig(
    long_mask,
    short_mask,
):

    long_mask = np.asarray(
        long_mask,
        dtype=bool,
    )

    short_mask = np.asarray(
        short_mask,
        dtype=bool,
    )

    s = np.zeros(
        len(long_mask),
        dtype=np.int8,
    )

    s[long_mask] = 1
    s[short_mask] = -1

    return s


def build_signal_families(
    f: dict[str, pd.Series],
):

    c = f["c"]
    h = f["h"]
    l = f["l"]

    rsi = f["rsi"]
    atr = f["atr"]

    ema20 = f["ema20"]
    ema50 = f["ema50"]
    ema200 = f["ema200"]

    vol_ratio = f["vol_ratio"]

    bb_z = f["bb_z"]

    vwap48 = f["vwap48"]
    vwap96 = f["vwap96"]

    out = []

    for k in (2.0, 2.5):

        for rlo in (25, 30):

            long_ = (
                (bb_z < -k)
                & (rsi < rlo)
            )

            short_ = (
                (bb_z > k)
                & (rsi > 100 - rlo)
            )

            out.append(
                (
                    f"bb_rsi k={k} rsi<{rlo}",
                    _sig(long_, short_),
                )
            )

    for n in (30, 60):

        z = (
            (c - c.rolling(n).mean())
            / c.rolling(n).std().replace(
                0,
                np.nan,
            )
        )

        for thr in (2.0, 2.5):

            out.append(
                (
                    f"zscore n={n} thr={thr}",
                    _sig(
                        z < -thr,
                        z > thr,
                    ),
                )
            )

    for n in (20, 50):

        hi = (
            h.rolling(n)
            .max()
            .shift(1)
        )

        lo = (
            l.rolling(n)
            .min()
            .shift(1)
        )

        for vm in (0.0, 1.5):

            if vm > 0:

                ok = (
                    vol_ratio > vm
                )

            else:

                ok = pd.Series(
                    True,
                    index=c.index,
                )

            out.append(
                (
                    f"donchian n={n} vol>{vm}x",
                    _sig(
                        (c > hi) & ok,
                        (c < lo) & ok,
                    ),
                )
            )

    for n, vw in (
        (48, vwap48),
        (96, vwap96),
    ):

        for k in (2.0, 3.0):

            long_ = (
                c < vw - k * atr
            )

            short_ = (
                c > vw + k * atr
            )

            out.append(
                (
                    f"vwap n={n} k={k}atr",
                    _sig(
                        long_,
                        short_,
                    ),
                )
            )

    for thr in (35, 40):

        up = (
            (ema20 > ema50)
            & (c > ema200)
        )

        down = (
            (ema20 < ema50)
            & (c < ema200)
        )

        out.append(
            (
                f"trend_pullback rsi<{thr}",
                _sig(
                    up & (rsi < thr),
                    down & (rsi > 100 - thr),
                ),
            )
        )

    cross_up = (
        (ema20 > ema50)
        & (
            ema20.shift(1)
            <= ema50.shift(1)
        )
    )

    cross_dn = (
        (ema20 < ema50)
        & (
            ema20.shift(1)
            >= ema50.shift(1)
        )
    )

    out.append(
        (
            "ema20_50_cross",
            _sig(
                cross_up,
                cross_dn,
            ),
        )
    )

    atr_pct = (
        atr / c.replace(
            0,
            np.nan,
        )
    )

    atr_base = (
        atr_pct.rolling(50).mean()
    )

    breakout_hi = (
        h.rolling(20)
        .max()
        .shift(1)
    )

    breakout_lo = (
        l.rolling(20)
        .min()
        .shift(1)
    )

    expanded = (
        atr_pct > atr_base
    )

    out.append(
        (
            "breakout20_atr_expansion",
            _sig(
                (c > breakout_hi)
                & expanded,
                (c < breakout_lo)
                & expanded,
            ),
        )
    )

    out.append(
        (
            "vwap48_trend",
            _sig(
                (c > vwap48)
                & (ema20 > ema50),
                (c < vwap48)
                & (ema20 < ema50),
            )
        )
    )

    return out


# ============================================================
# CANDIDATS V3
# ============================================================

def make_candidates(
    entry: pd.DataFrame,
    h1: pd.DataFrame,
):

    ef = make_features(entry)

    h1f = align_1h_features(
        entry,
        h1,
    )

    ctx = context_masks(h1f)

    base = build_signal_families(
        ef
    )

    candidates = []

    regime_names = (
        "strong_trend",
        "trend",
        "trend_up",
        "range",
        "all",
    )

    volatility_names = (
        "low",
        "normal",
        "high",
    )

    for name, sig in base:

        for regime_name in regime_names:

            long_ok, short_ok = (
                ctx[regime_name]
            )

            for vol_name in volatility_names:

                vol_ok = ctx[
                    "volatility"
                ][vol_name]

                s = sig.copy()

                invalid_long = (
                    (s > 0)
                    & ~long_ok
                )

                invalid_short = (
                    (s < 0)
                    & ~short_ok
                )

                s[
                    invalid_long
                    | invalid_short
                ] = 0

                active = (
                    s != 0
                )

                s[active] *= (
                    vol_ok[active]
                    .astype(np.int8)
                )

                if np.count_nonzero(s) == 0:
                    continue

                candidates.append(
                    Candidate(
                        name=name,
                        signal=s,
                        regime=regime_name,
                        volatility=vol_name,
                    )
                )

    return ef, candidates


# ============================================================
# SIMULATION
# ============================================================

def simulate(
    L,
    sig,
    tp_m,
    sl_m,
    hold,
    prof,
    slip,
    fee_scale=1.0,
    slip_scale=1.0,
):

    o = np.asarray(
        L["o"],
        dtype=float,
    )

    h = np.asarray(
        L["h"],
        dtype=float,
    )

    l = np.asarray(
        L["l"],
        dtype=float,
    )

    c = np.asarray(
        L["c"],
        dtype=float,
    )

    atr = np.asarray(
        L["atr"],
        dtype=float,
    )

    n = len(c)

    maker_entry = (
        prof == "maker_both"
    )

    maker_tp = (
        prof
        in (
            "maker_tp",
            "maker_both",
        )
    )

    fee_taker = (
        FEE_TAKER
        * fee_scale
    )

    fee_maker = (
        FEE_MAKER
        * fee_scale
    )

    slip_eff = (
        slip * slip_scale
    )

    rows = []

    free = 0

    for i in np.flatnonzero(sig).tolist():

        if i < free:
            continue

        k = i + 1

        if k >= n - 1:
            break

        s = int(sig[i])

        a = atr[i]

        if not (
            a > 0
            and np.isfinite(a)
        ):
            continue

        if maker_entry:

            lim = c[i]

            if s > 0:

                if not (
                    l[k]
                    < lim * (1 - THROUGH)
                ):
                    continue

            else:

                if not (
                    h[k]
                    > lim * (1 + THROUGH)
                ):
                    continue

            entry = lim
            e_fee = fee_maker

        else:

            entry = (
                o[k]
                * (1 + s * slip_eff)
            )

            e_fee = fee_taker

        if not (
            np.isfinite(entry)
            and entry > 0
        ):
            continue

        tp = (
            entry
            + s * tp_m * a
        )

        sl = (
            entry
            - s * sl_m * a
        )

        tp_chk = (
            tp * (1 + s * THROUGH)
            if maker_tp
            else tp
        )

        last = (
            min(k + hold, n)
            - 1
        )

        exit_px = None
        kind = None

        j = k

        while j <= last:

            if s > 0:

                hit_sl = (
                    l[j] <= sl
                )

                hit_tp = (
                    h[j] >= tp_chk
                )

            else:

                hit_sl = (
                    h[j] >= sl
                )

                hit_tp = (
                    l[j] <= tp_chk
                )

            if hit_sl:

                exit_px = (
                    sl
                    * (
                        1
                        - s
                        * slip_eff
                    )
                )

                kind = "sl"

                break

            if hit_tp:

                exit_px = (
                    tp
                    if maker_tp
                    else tp
                    * (
                        1
                        - s
                        * slip_eff
                    )
                )

                kind = "tp"

                break

            j += 1

        if exit_px is None:

            j = last

            exit_px = (
                c[j]
                * (
                    1
                    - s
                    * slip_eff
                )
            )

            kind = "time"

        x_fee = (
            fee_maker
            if (
                kind == "tp"
                and maker_tp
            )
            else fee_taker
        )

        gross = (
            s
            * (exit_px - entry)
            / entry
        )

        net = (
            gross
            - e_fee
            - x_fee * exit_px / entry
        )

        rows.append(
            {
                "signal_i": i,
                "entry_i": k,
                "exit_i": j,
                "net": net,
                "gross": gross,
                "kind": kind,
                "duration": j - k + 1,
                "side": s,
            }
        )

        free = j

    return pd.DataFrame(rows)


# ============================================================
# STATISTIQUES
# ============================================================

def basic_stats(
    trades: pd.DataFrame,
):

    if (
        trades is None
        or trades.empty
    ):

        return {
            "n": 0,
            "mean": np.nan,
            "sd": np.nan,
            "win": np.nan,
            "pf": np.nan,
        }

    x = trades[
        "net"
    ].to_numpy(
        dtype=float
    )

    wins = x[x > 0].sum()
    losses = -x[x < 0].sum()

    return {
        "n": len(x),
        "mean": float(x.mean()),
        "sd": (
            float(x.std(ddof=1))
            if len(x) > 1
            else np.nan
        ),
        "win": float((x > 0).mean()),
        "pf": (
            float(wins / losses)
            if losses > 0
            else float("inf")
        ),
    }


def equity_stats(
    trades: pd.DataFrame,
    capital: float,
):

    if (
        trades is None
        or trades.empty
    ):

        return {
            "final": capital,
            "return": 0.0,
            "max_dd": 0.0,
            "worst_trade": np.nan,
            "max_loss_streak": 0,
        }

    x = trades[
        "net"
    ].to_numpy(
        dtype=float
    )

    equity = [capital]
    cur = capital

    for r in x:

        cur *= max(
            0.0,
            1.0 + r,
        )

        equity.append(cur)

    eq = np.asarray(equity)

    peak = np.maximum.accumulate(eq)

    dd = eq / peak - 1.0

    streak = 0
    max_streak = 0

    for r in x:

        if r < 0:

            streak += 1
            max_streak = max(
                max_streak,
                streak,
            )

        else:

            streak = 0

    return {
        "final": float(eq[-1]),
        "return": float(
            eq[-1] / capital - 1
        ),
        "max_dd": float(dd.min()),
        "worst_trade": float(x.min()),
        "max_loss_streak": int(
            max_streak
        ),
    }


# ============================================================
# SCORE TRAIN
# ============================================================

def score_training(
    stats,
    equity,
):

    n = stats["n"]

    if n < MIN_TRAIN_TRADES:
        return -np.inf

    mean = stats["mean"]
    pf = stats["pf"]
    sd = stats["sd"]
    dd = abs(equity["max_dd"])

    if not np.isfinite(mean):
        return -np.inf

    if not np.isfinite(pf):

        pf_component = 2.0

    else:

        pf_component = np.clip(
            pf - 1.0,
            -1.0,
            2.0,
        )

    mean_component = np.clip(
        mean * 1000.0,
        -2.0,
        2.0,
    )

    dd_penalty = np.clip(
        dd * 10.0,
        0.0,
        2.0,
    )

    if (
        np.isfinite(sd)
        and sd > 0
    ):

        stability = np.clip(
            mean / sd,
            -1.0,
            1.0,
        )

    else:

        stability = 0.0

    trade_component = min(
        math.log1p(n) / 6.0,
        1.0,
    )

    score = (
        0.45 * mean_component
        + 0.30 * pf_component
        + 0.15 * stability
        + 0.10 * trade_component
        - 0.15 * dd_penalty
    )

    return float(score)


# ============================================================
# MONTE-CARLO
# ============================================================

def monte_carlo(
    trades: pd.DataFrame,
    capital: float,
    runs=MC_RUNS,
    seed=MC_SEED,
):

    if (
        trades is None
        or len(trades) < 20
    ):

        return {
            "mc_median": np.nan,
            "mc_p05": np.nan,
            "mc_p95": np.nan,
            "mc_dd_median": np.nan,
        }

    x = trades[
        "net"
    ].to_numpy(
        dtype=float
    )

    rng = np.random.default_rng(seed)

    finals = np.empty(runs)
    dds = np.empty(runs)

    for r in range(runs):

        sample = rng.choice(
            x,
            size=len(x),
            replace=True,
        )

        eq = capital
        peak = capital
        worst_dd = 0.0

        for z in sample:

            eq *= max(
                0.0,
                1.0 + z,
            )

            peak = max(
                peak,
                eq,
            )

            worst_dd = min(
                worst_dd,
                eq / peak - 1.0,
            )

        finals[r] = eq
        dds[r] = worst_dd

    return {
        "mc_median": float(
            np.median(finals)
        ),
        "mc_p05": float(
            np.percentile(
                finals,
                5,
            )
        ),
        "mc_p95": float(
            np.percentile(
                finals,
                95,
            )
        ),
        "mc_dd_median": float(
            np.median(dds)
        ),
    }


# ============================================================
# WALK FORWARD
# ============================================================

def make_folds(
    n: int,
    interval: str,
):

    bars_per_day = {
        "5m": 288,
        "15m": 96,
    }[interval]

    train = (
        TRAIN_DAYS
        * bars_per_day
    )

    test = (
        TEST_DAYS
        * bars_per_day
    )

    step = (
        STEP_DAYS
        * bars_per_day
    )

    folds = []

    start = 0

    while (
        start
        + train
        + test
        <= n
    ):

        folds.append(
            (
                start,
                start + train,
                start + train,
                start + train + test,
            )
        )

        start += step

    return folds


# ============================================================
# STRESS TEST V3.1
# ============================================================

def stress_test(
    Lfull,
    candidates,
    symbol: str,
    best_spec: dict,
    test_start: int,
    test_end: int,
):

    """
    Rejoue exactement le candidat sélectionné
    sur le dataset complet puis isole strictement
    la fenêtre TEST.

    IMPORTANT:
        candidates est la liste originale globale.
        Aucun recalcul de candidats n'est effectué.
    """

    cand = candidates[
        int(best_spec["candidate"])
    ]

    scenarios = [
        ("base", 1.0, 1.0),
        ("fees+25%", 1.25, 1.0),
        ("fees+50%", 1.50, 1.0),
        ("fees+100%", 2.00, 1.0),
        ("slip+50%", 1.0, 1.50),
        ("slip+100%", 1.0, 2.00),
        ("fees+50%_slip+100%", 1.50, 2.00),
    ]

    rows = []

    slip = SLIP.get(
        symbol,
        DEFAULT_SLIP,
    )

    for name, fs, ss in scenarios:

        tr_all = simulate(
            Lfull,
            cand.signal,
            float(best_spec["tp"]),
            float(best_spec["sl"]),
            int(best_spec["hold"]),
            best_spec["profile"],
            slip,
            fee_scale=fs,
            slip_scale=ss,
        )

        if tr_all.empty:

            tr = tr_all

        else:

            tr = (
                tr_all[
                    (tr_all.signal_i >= test_start)
                    & (tr_all.signal_i < test_end)
                    & (tr_all.entry_i >= test_start)
                    & (tr_all.exit_i < test_end)
                ]
                .copy()
            )

        st = basic_stats(tr)

        es = equity_stats(
            tr,
            DEFAULT_CAPITAL,
        )

        rows.append(
            {
                "scenario": name,
                "mean": st["mean"],
                "pf": st["pf"],
                "win": st["win"],
                "n": st["n"],
                "return": es["return"],
                "max_dd": es["max_dd"],
            }
        )

    return pd.DataFrame(rows)


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
        default=365,
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

    os.makedirs(
        "results",
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Nettoyage des anciens résultats.
    # --------------------------------------------------------

    for filename in (
        "walk_forward.csv",
        "stress_test.csv",
        "summary_v2.md",
        "summary_v3.md",
    ):

        path = os.path.join(
            "results",
            filename,
        )

        if os.path.exists(path):

            os.remove(path)

    md = []

    def out(s=""):

        print(
            s,
            flush=True,
        )

        md.append(s)

    out(
        "# SCALP LAB V3.1 — "
        "recherche scalping Binance USD-M"
    )

    out("")

    out(
        "Méthode: données Binance USD-M | "
        "signal clôturé → entrée suivante | "
        "1h contexte | 5m/15m entrée"
    )

    out(
        f"Coûts: taker={FEE_TAKER*100:.2f}% "
        f"maker={FEE_MAKER*100:.2f}% par côté | "
        f"WF={TRAIN_DAYS}j/"
        f"{TEST_DAYS}j/"
        f"{STEP_DAYS}j"
    )

    out(
        f"Recherche: "
        f"{len(EXITS)} exits × "
        f"{len(PROFILES)} profils | "
        f"minimum TRAIN={MIN_TRAIN_TRADES}"
    )

    out("")

    all_wf = []
    all_stress = []

    total_start = time.time()

    # ========================================================
    # BOUCLE PRINCIPALE
    # ========================================================

    for interval in intervals:

        if interval not in (
            "5m",
            "15m",
        ):

            raise SystemExit(
                "V3 accepte 5m et 15m."
            )

        for symbol in symbols:

            pair_start = time.time()

            end_ms = int(
                time.time() * 1000
            )

            start_ms = (
                end_ms
                - args.days
                * 86_400_000
            )

            # ------------------------------------------------
            # ENTRY
            # ------------------------------------------------

            entry = to_frame(
                fetch_vision(
                    symbol,
                    interval,
                    start_ms,
                    end_ms,
                )
            )

            entry = (
                entry[
                    entry.time >= start_ms
                ]
                .reset_index(drop=True)
            )

            # ------------------------------------------------
            # 1H
            # ------------------------------------------------

            h1 = to_frame(
                fetch_vision(
                    symbol,
                    "1h",
                    start_ms,
                    end_ms,
                )
            )

            h1 = (
                h1[
                    h1.time >= start_ms
                ]
                .reset_index(drop=True)
            )

            if (
                len(entry) < 20_000
                or len(h1) < 500
            ):

                out(
                    f"{symbol} {interval} | "
                    f"INSUFFISANT | "
                    f"{len(entry)} candles | "
                    f"{len(h1)} h1"
                )

                continue

            folds = make_folds(
                len(entry),
                interval,
            )

            # ------------------------------------------------
            # CANDIDATS
            # ------------------------------------------------

            ef, candidates = (
                make_candidates(
                    entry,
                    h1,
                )
            )

            out(
                f"{symbol} {interval} | "
                f"{len(entry)} candles | "
                f"{len(h1)} h1 | "
                f"{len(candidates)} candidats | "
                f"{len(folds)} folds"
            )

            Lfull = {
                k: ef[k].to_numpy(
                    dtype=float
                )
                for k in (
                    "o",
                    "h",
                    "l",
                    "c",
                    "atr",
                )
            }

            slip = SLIP.get(
                symbol,
                DEFAULT_SLIP,
            )

            # =================================================
            # FOLDS
            # =================================================

            for fold_id, (
                tr0,
                tr1,
                te0,
                te1,
            ) in enumerate(
                folds,
                1,
            ):

                best = None

                # --------------------------------------------
                # TRAIN
                # --------------------------------------------

                for ci, cand in enumerate(
                    candidates
                ):

                    for ei, (
                        tp_m,
                        sl_m,
                        hold,
                    ) in enumerate(
                        EXITS
                    ):

                        for prof in PROFILES:

                            tr_all = simulate(
                                Lfull,
                                cand.signal,
                                tp_m,
                                sl_m,
                                hold,
                                prof,
                                slip,
                            )

                            if tr_all.empty:
                                continue

                            # IMPORTANT:
                            # signal + entrée + sortie
                            # doivent être intégralement
                            # dans TRAIN.

                            tr_train = (
                                tr_all[
                                    (tr_all.signal_i >= tr0)
                                    & (tr_all.signal_i < tr1)
                                    & (tr_all.entry_i >= tr0)
                                    & (tr_all.exit_i < tr1)
                                ]
                                .copy()
                            )

                            if (
                                len(tr_train)
                                < MIN_TRAIN_TRADES
                            ):
                                continue

                            st = basic_stats(
                                tr_train
                            )

                            es = equity_stats(
                                tr_train,
                                args.capital,
                            )

                            score = score_training(
                                st,
                                es,
                            )

                            if (
                                best is None
                                or score
                                > best["score"]
                            ):

                                best = {
                                    "candidate": ci,
                                    "signal": cand.name,
                                    "regime": cand.regime,
                                    "volatility": cand.volatility,
                                    "exit": ei,
                                    "tp": tp_m,
                                    "sl": sl_m,
                                    "hold": hold,
                                    "profile": prof,
                                    "train_n": st["n"],
                                    "train_mean": st["mean"],
                                    "train_pf": st["pf"],
                                    "train_dd": es["max_dd"],
                                    "train_return": es["return"],
                                    "score": score,
                                }

                if best is None:

                    out(
                        f"  Fold {fold_id}/{len(folds)} "
                        "→ aucun candidat TRAIN"
                    )

                    continue

                # --------------------------------------------
                # TEST
                # --------------------------------------------

                cand = candidates[
                    int(
                        best["candidate"]
                    )
                ]

                te_all = simulate(
                    Lfull,
                    cand.signal,
                    float(best["tp"]),
                    float(best["sl"]),
                    int(best["hold"]),
                    best["profile"],
                    slip,
                )

                if te_all.empty:

                    te = te_all

                else:

                    # IMPORTANT:
                    # le trade doit être entièrement
                    # contenu dans TEST.

                    te = (
                        te_all[
                            (te_all.signal_i >= te0)
                            & (te_all.signal_i < te1)
                            & (te_all.entry_i >= te0)
                            & (te_all.exit_i < te1)
                        ]
                        .copy()
                    )

                st_te = basic_stats(te)

                es_te = equity_stats(
                    te,
                    args.capital,
                )

                mc = monte_carlo(
                    te,
                    args.capital,
                    runs=args.mc_runs,
                    seed=(
                        MC_SEED
                        + fold_id
                    ),
                )

                row = {
                    "symbol": symbol,
                    "interval": interval,
                    "fold": fold_id,
                    "train_start": tr0,
                    "train_end": tr1,
                    "test_start": te0,
                    "test_end": te1,
                    "signal": best["signal"],
                    "regime": best["regime"],
                    "volatility": best["volatility"],
                    "profile": best["profile"],
                    "tp": best["tp"],
                    "sl": best["sl"],
                    "hold": best["hold"],
                    "train_n": best["train_n"],
                    "train_mean": best["train_mean"],
                    "train_pf": best["train_pf"],
                    "train_return": best["train_return"],
                    "train_max_dd": best["train_dd"],
                    "train_score": best["score"],
                    "test_n": st_te["n"],
                    "test_mean": st_te["mean"],
                    "test_pf": st_te["pf"],
                    "test_win": st_te["win"],
                    "test_return": es_te["return"],
                    "test_max_dd": es_te["max_dd"],
                    "worst_trade": es_te["worst_trade"],
                    "max_loss_streak": es_te["max_loss_streak"],
                    "mc_median": mc["mc_median"],
                    "mc_p05": mc["mc_p05"],
                    "mc_p95": mc["mc_p95"],
                    "mc_dd_median": mc["mc_dd_median"],
                }

                all_wf.append(row)

                # --------------------------------------------
                # STRESS
                # --------------------------------------------

                stress = stress_test(
                    Lfull,
                    candidates,
                    symbol,
                    best,
                    te0,
                    te1,
                )

                stress["symbol"] = symbol
                stress["interval"] = interval
                stress["fold"] = fold_id
                stress["signal"] = best["signal"]
                stress["regime"] = best["regime"]
                stress["volatility"] = best["volatility"]
                stress["profile"] = best["profile"]

                all_stress.append(stress)

                out(
                    f"  Fold {fold_id}/{len(folds)} → "
                    f"{best['signal']} / "
                    f"{best['regime']} / "
                    f"{best['volatility']} / "
                    f"{best['profile']} | "
                    f"TEST "
                    f"{st_te['mean']*100:+.4f}% | "
                    f"PF={st_te['pf']:.2f} | "
                    f"DD={es_te['max_dd']*100:.2f}% | "
                    f"n={st_te['n']}"
                )

            pair_elapsed = time.time() - pair_start

            out(
                f"  → terminé en "
                f"{pair_elapsed/60:.1f} min"
            )

    # ========================================================
    # EXPORT
    # ========================================================

    if not all_wf:

        raise SystemExit(
            "Aucun résultat walk-forward."
        )

    WF = pd.DataFrame(
        all_wf
    )

    ST = (
        pd.concat(
            all_stress,
            ignore_index=True,
        )
        if all_stress
        else pd.DataFrame()
    )

    WF.to_csv(
        "results/walk_forward.csv",
        index=False,
    )

    ST.to_csv(
        "results/stress_test.csv",
        index=False,
    )

    # ========================================================
    # RÉSUMÉ GLOBAL
    # ========================================================

    out("")
    out("## Résultat global walk-forward")
    out("")

    out(
        "| intervalle | folds | "
        "test mean/trade | "
        "folds positifs | "
        "return médian | "
        "DD médian | PF médian |"
    )

    out(
        "|---|---:|---:|---:|---:|---:|---:|"
    )

    for iv in sorted(
        WF.interval.unique()
    ):

        x = WF[
            WF.interval == iv
        ]

        out(
            f"| {iv} | "
            f"{len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}"
            f"/{len(x)} | "
            f"{x.test_return.median()*100:+.2f}% | "
            f"{x.test_max_dd.median()*100:.2f}% | "
            f"{x.test_pf.median():.2f} |"
        )

    # ========================================================
    # PAR SYMBOLE
    # ========================================================

    out("")
    out("## Résultat par symbole")
    out("")

    out(
        "| symbole | intervalle | folds | "
        "test moyen | positifs | "
        "return médian | DD médian |"
    )

    out(
        "|---|---|---:|---:|---:|---:|---:|"
    )

    for (
        sym,
        iv,
    ), x in WF.groupby(
        [
            "symbol",
            "interval",
        ]
    ):

        out(
            f"| {sym} | {iv} | "
            f"{len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}"
            f"/{len(x)} | "
            f"{x.test_return.median()*100:+.2f}% | "
            f"{x.test_max_dd.median()*100:.2f}% |"
        )

    # ========================================================
    # PAR RÉGIME
    # ========================================================

    out("")
    out("## Résultat par régime V3")
    out("")

    out(
        "| régime | folds | "
        "test moyen | positifs | "
        "PF médian | DD médian |"
    )

    out(
        "|---|---:|---:|---:|---:|---:|"
    )

    for regime, x in WF.groupby(
        "regime"
    ):

        out(
            f"| {regime} | "
            f"{len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}"
            f"/{len(x)} | "
            f"{x.test_pf.median():.2f} | "
            f"{x.test_max_dd.median()*100:.2f}% |"
        )

    # ========================================================
    # PAR VOLATILITÉ
    # ========================================================

    out("")
    out("## Résultat par volatilité V3")
    out("")

    out(
        "| volatilité | folds | "
        "test moyen | positifs | "
        "PF médian | DD médian |"
    )

    out(
        "|---|---:|---:|---:|---:|---:|"
    )

    for volatility, x in WF.groupby(
        "volatility"
    ):

        out(
            f"| {volatility} | "
            f"{len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}"
            f"/{len(x)} | "
            f"{x.test_pf.median():.2f} | "
            f"{x.test_max_dd.median()*100:.2f}% |"
        )

    # ========================================================
    # ROBUSTESSE DES COÛTS
    # ========================================================

    out("")
    out("## Robustesse des coûts")
    out("")

    if not ST.empty:

        for scenario, x in ST.groupby(
            "scenario"
        ):

            out(
                f"- **{scenario}** : "
                f"mean/trade "
                f"{x['mean'].mean()*100:+.4f}% ; "
                f"PF médian "
                f"{x['pf'].median():.2f} ; "
                f"DD médian "
                f"{x['max_dd'].median()*100:.2f}%"
            )

    # ========================================================
    # DISTRIBUTION
    # ========================================================

    out("")
    out("## Distribution des choix V3")
    out("")

    regime_counts = (
        WF["regime"]
        .value_counts()
        .to_dict()
    )

    vol_counts = (
        WF["volatility"]
        .value_counts()
        .to_dict()
    )

    out(
        f"- régimes sélectionnés: "
        f"{regime_counts}"
    )

    out(
        f"- volatilités sélectionnées: "
        f"{vol_counts}"
    )

    # ========================================================
    # VERDICT TECHNIQUE
    # ========================================================

    positive_folds = int(
        (
            WF.test_mean > 0
        ).sum()
    )

    total_folds = len(WF)

    median_test = float(
        WF.test_mean.median()
    )

    median_pf = float(
        WF.test_pf.median()
    )

    out("")
    out("## Verdict V3")

    if (
        total_folds >= 8
        and positive_folds / total_folds >= 0.60
        and median_test > 0
        and median_pf > 1.0
    ):

        out(
            "Le laboratoire observe "
            "un avantage hors échantillon "
            "potentiellement robuste. "
            "Ce résultat doit encore être "
            "confirmé sur une période "
            "supplémentaire et en paper trading "
            "avant toute utilisation réelle."
        )

    else:

        out(
            "Le laboratoire ne trouve pas encore "
            "de preuve suffisante d'un avantage "
            "robuste hors échantillon. "
            "Les filtres de contexte V3 doivent "
            "être évalués sur leurs résultats "
            "TEST et non sur leur performance TRAIN."
        )

    out("")

    out(
        "Limites: bougies OHLCV, pas de carnet "
        "d'ordres, exécution limite approximée, "
        "pas de funding, pas de latence réseau, "
        "et Monte-Carlo basé sur les trades observés."
    )

    # ========================================================
    # ÉCRITURE RAPPORT
    # ========================================================

    with open(
        "results/summary_v3.md",
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "\n".join(md)
        )

    elapsed = time.time() - total_start

    print("")
    print("=" * 60)
    print("V3.1 TERMINÉE")
    print("=" * 60)
    print(
        f"Durée totale : {elapsed/60:.1f} min"
    )
    print(
        f"Folds analysés : {len(WF)}"
    )
    print(
        "results/summary_v3.md"
    )
    print(
        "results/walk_forward.csv"
    )
    print(
        "results/stress_test.csv"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
