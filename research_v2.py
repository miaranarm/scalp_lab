"""
SCALP LAB V2 — laboratoire de recherche pour scalping Binance USD-M.

Objectif:
    Chercher un avantage robuste AVANT de construire le bot.

V2 ajoute à la V1:
    - données 1h + timeframe d'entrée (5m/15m)
    - filtre de régime 1h
    - familles de signaux supplémentaires
    - validation walk-forward
    - simulation du capital et drawdown
    - bootstrap/Monte-Carlo des trades
    - stress-test frais/slippage
    - export CSV + résumé Markdown

Important:
    - aucune optimisation sur la période TEST d'un fold
    - signal calculé sur une bougie clôturée, entrée sur la suivante
    - pas de martingale
    - une position à la fois par symbole
    - le moteur reste volontairement OHLCV: pas de carnet d'ordres
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

FEE_TAKER = 0.0005       # 0,05 % / côté
FEE_MAKER = 0.0002       # 0,02 % / côté
THROUGH = 0.00005        # 0,005 % de traversée pour limite

SLIP = {
    "BTCUSDT": 0.0001,
    "ETHUSDT": 0.00015,
    "SOLUSDT": 0.0003,
    "XRPUSDT": 0.0003,
    "BNBUSDT": 0.0002,
}
DEFAULT_SLIP = 0.0003

PROFILES = ("taker", "maker_tp", "maker_both")

# TP ATR, SL ATR, durée maximale
EXITS = [
    (1.5, 1.0, 12),
    (2.0, 1.0, 24),
    (3.0, 1.5, 36),
    (2.0, 2.0, 24),
]

# Walk-forward:
# avec 365 jours, 180 + 45 + 45 + 45 + 45 couvre une grande partie
# tout en gardant plusieurs tests indépendants.
TRAIN_DAYS = 180
TEST_DAYS = 45
STEP_DAYS = 45
MIN_TRAIN_TRADES = 80

# Monte-Carlo
MC_RUNS = 5000
MC_SEED = 20260928

# capital
DEFAULT_CAPITAL = 100.0


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


def fetch_vision(symbol: str, interval: str, start_ms: int, end_ms: int):
    """Télécharge les klines publiques Binance USD-M."""
    base = "https://data.binance.vision/data/futures/um"
    start = datetime.fromtimestamp(start_ms / 1000, timezone.utc).date()
    end = datetime.fromtimestamp(end_ms / 1000, timezone.utc).date()
    today = datetime.now(timezone.utc).date()

    rows = []
    day = start.replace(day=1)

    while day <= end:
        nxt = (day.replace(day=28) + timedelta(days=4)).replace(day=1)

        if nxt <= today.replace(day=1):
            name = f"{symbol}-{interval}-{day:%Y-%m}"
            url = f"{base}/monthly/klines/{symbol}/{interval}/{name}.zip"
            r = requests.get(url, timeout=90)
            if r.status_code == 200:
                rows += _read_zip_csv(r.content)
            day = nxt
        else:
            d = day
            while d < today and d <= end:
                name = f"{symbol}-{interval}-{d:%Y-%m-%d}"
                url = f"{base}/daily/klines/{symbol}/{interval}/{name}.zip"
                r = requests.get(url, timeout=90)
                if r.status_code == 200:
                    rows += _read_zip_csv(r.content)
                d += timedelta(days=1)
            break

    return rows


def to_frame(rows):
    d = pd.DataFrame(
        rows,
        columns=[
            "time", "open", "high", "low", "close", "volume",
            "x", "q", "n", "tb", "tq", "i",
        ],
    )

    for k in ["time", "open", "high", "low", "close", "volume"]:
        d[k] = pd.to_numeric(d[k], errors="coerce")

    d = d.dropna(
        subset=["time", "open", "high", "low", "close", "volume"]
    )
    return (
        d.drop_duplicates("time")
        .sort_values("time")
        .reset_index(drop=True)
    )


# ============================================================
# INDICATEURS
# ============================================================

def make_features(d: pd.DataFrame) -> dict[str, pd.Series]:
    c = d["close"]
    h = d["high"]
    l = d["low"]
    v = d["volume"]

    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))

    pc = c.shift(1)
    tr = pd.concat(
        [(h - l), (h - pc).abs(), (l - pc).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

    ema9 = c.ewm(span=9, adjust=False).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()

    ret = c.pct_change()
    vol20 = ret.rolling(20).std()

    bb_mid = c.rolling(20).mean()
    bb_sd = c.rolling(20).std()
    bb_z = (c - bb_mid) / bb_sd.replace(0, np.nan)
    bb_width = (2 * bb_sd) / bb_mid.replace(0, np.nan)

    rv20 = v.rolling(20).mean()
    vol_ratio = v / rv20.replace(0, np.nan)

    tp = (h + l + c) / 3
    vwaps = {}
    for n in (48, 96):
        vwaps[n] = (
            (tp * v).rolling(n).sum()
            / v.rolling(n).sum().replace(0, np.nan)
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
    }


def align_1h_features(
    entry: pd.DataFrame,
    h1: pd.DataFrame,
) -> dict[str, pd.Series]:
    """
    Aligne les valeurs 1h sur chaque bougie d'entrée.

    IMPORTANT:
    merge_asof utilise la dernière bougie 1h dont le timestamp est
    <= au timestamp de la bougie d'entrée. On ne regarde donc pas
    une bougie 1h future.
    """
    hf = make_features(h1)

    base = pd.DataFrame({"time": entry["time"].values})

    # Binance donne le timestamp d'OUVERTURE de la bougie 1h.
    # Pour éviter tout look-ahead, une bougie 1h ouverte à 10:00
    # n'est utilisable qu'à partir de 11:00.
    src = pd.DataFrame({
        "time": h1["time"].values + INTERVAL_MS["1h"],
    })

    for name in ("c", "ema20", "ema50", "ema200", "atr", "rsi", "bb_width"):
        src[name] = hf[name].values

    merged = pd.merge_asof(
        base.sort_values("time"),
        src.sort_values("time"),
        on="time",
        direction="backward",
    )

    return {
        "c": merged["c"],
        "ema20": merged["ema20"],
        "ema50": merged["ema50"],
        "ema200": merged["ema200"],
        "atr": merged["atr"],
        "rsi": merged["rsi"],
        "bb_width": merged["bb_width"],
    }


# ============================================================
# SIGNAUX
# ============================================================

@dataclass(frozen=True)
class Candidate:
    name: str
    signal: np.ndarray
    regime: str


def _sig(long_mask, short_mask):
    long_mask = np.asarray(long_mask, dtype=bool)
    short_mask = np.asarray(short_mask, dtype=bool)

    s = np.zeros(len(long_mask), dtype=np.int8)
    s[long_mask] = 1
    s[short_mask] = -1
    return s


def regime_masks(entry_f: dict, h1f: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """
    Régimes déterminés sur 1h.

    trend_up / trend_down:
        EMA20 > EMA50 et close > EMA200, ou inverse.

    trend:
        accepte long en tendance haussière et short en tendance baissière.

    range:
        EMA20/EMA50 proches et prix pas fortement éloigné de EMA200.

    all:
        aucun filtre de régime.
    """
    c = np.asarray(h1f["c"], dtype=float)
    e20 = np.asarray(h1f["ema20"], dtype=float)
    e50 = np.asarray(h1f["ema50"], dtype=float)
    e200 = np.asarray(h1f["ema200"], dtype=float)

    valid = np.isfinite(c) & np.isfinite(e20) & np.isfinite(e50) & np.isfinite(e200)

    up = valid & (e20 > e50) & (c > e200)
    down = valid & (e20 < e50) & (c < e200)

    dist = np.abs(c - e200) / np.maximum(np.abs(c), 1e-12)
    close_emas = np.abs(e20 - e50) / np.maximum(np.abs(c), 1e-12) < 0.003
    range_ = valid & close_emas & (dist < 0.02)

    return {
        "all": (valid, valid),
        "trend": (up, down),
        "trend_up": (up, np.zeros_like(down)),
        "range": (range_, range_),
    }


def build_signal_families(f: dict[str, pd.Series]):
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

    # 1) Bollinger + RSI mean reversion
    for k in (2.0, 2.5):
        for rlo in (25, 30):
            long_ = (bb_z < -k) & (rsi < rlo)
            short_ = (bb_z > k) & (rsi > 100 - rlo)
            out.append(
                (f"bb_rsi k={k} rsi<{rlo}", _sig(long_, short_))
            )

    # 2) Z-score
    for n in (30, 60):
        z = (c - c.rolling(n).mean()) / c.rolling(n).std().replace(0, np.nan)
        for thr in (2.0, 2.5):
            out.append(
                (f"zscore n={n} thr={thr}", _sig(z < -thr, z > thr))
            )

    # 3) Donchian breakout + volume
    for n in (20, 50):
        hi = h.rolling(n).max().shift(1)
        lo = l.rolling(n).min().shift(1)
        for vm in (0.0, 1.5):
            ok = vol_ratio > vm if vm > 0 else pd.Series(True, index=c.index)
            out.append(
                (
                    f"donchian n={n} vol>{vm}x",
                    _sig((c > hi) & ok, (c < lo) & ok),
                )
            )

    # 4) VWAP deviation
    for n, vw in ((48, vwap48), (96, vwap96)):
        for k in (2.0, 3.0):
            long_ = c < vw - k * atr
            short_ = c > vw + k * atr
            out.append(
                (f"vwap n={n} k={k}atr", _sig(long_, short_))
            )

    # 5) Trend pullback
    for thr in (35, 40):
        up = (ema20 > ema50) & (c > ema200)
        down = (ema20 < ema50) & (c < ema200)
        out.append(
            (
                f"trend_pullback rsi<{thr}",
                _sig(up & (rsi < thr), down & (rsi > 100 - thr)),
            )
        )

    # 6) EMA momentum cross
    cross_up = (ema20 > ema50) & (ema20.shift(1) <= ema50.shift(1))
    cross_dn = (ema20 < ema50) & (ema20.shift(1) >= ema50.shift(1))
    out.append(("ema20_50_cross", _sig(cross_up, cross_dn)))

    # 7) Breakout + ATR expansion
    atr_pct = atr / c.replace(0, np.nan)
    atr_base = atr_pct.rolling(50).mean()
    breakout_hi = h.rolling(20).max().shift(1)
    breakout_lo = l.rolling(20).min().shift(1)
    expanded = atr_pct > atr_base
    out.append(
        (
            "breakout20_atr_expansion",
            _sig((c > breakout_hi) & expanded, (c < breakout_lo) & expanded),
        )
    )

    # 8) VWAP trend continuation
    out.append(
        (
            "vwap48_trend",
            _sig((c > vwap48) & (ema20 > ema50), (c < vwap48) & (ema20 < ema50)),
        )
    )

    return out


def make_candidates(entry: pd.DataFrame, h1: pd.DataFrame):
    ef = make_features(entry)
    h1f = align_1h_features(entry, h1)
    regimes = regime_masks(ef, h1f)

    base = build_signal_families(ef)
    candidates = []

    for name, sig in base:
        for regime_name, (long_ok, short_ok) in regimes.items():
            s = sig.copy()
            s[(s > 0) & ~long_ok] = 0
            s[(s < 0) & ~short_ok] = 0
            candidates.append(
                Candidate(
                    name=name,
                    signal=s,
                    regime=regime_name,
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
    """
    Retourne un DataFrame de trades.

    Signal sur i fermé.
    Entrée sur k=i+1.
    """
    o = np.asarray(L["o"], dtype=float)
    h = np.asarray(L["h"], dtype=float)
    l = np.asarray(L["l"], dtype=float)
    c = np.asarray(L["c"], dtype=float)
    atr = np.asarray(L["atr"], dtype=float)

    n = len(c)
    maker_entry = prof == "maker_both"
    maker_tp = prof in ("maker_tp", "maker_both")

    fee_taker = FEE_TAKER * fee_scale
    fee_maker = FEE_MAKER * fee_scale
    through = THROUGH
    slip_eff = slip * slip_scale

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

        if not (a > 0 and np.isfinite(a)):
            continue

        if maker_entry:
            lim = c[i]
            if s > 0:
                if not (l[k] < lim * (1 - through)):
                    continue
            else:
                if not (h[k] > lim * (1 + through)):
                    continue
            entry = lim
            e_fee = fee_maker
        else:
            entry = o[k] * (1 + s * slip_eff)
            e_fee = fee_taker

        if not np.isfinite(entry) or entry <= 0:
            continue

        tp = entry + s * tp_m * a
        sl = entry - s * sl_m * a
        tp_chk = tp * (1 + s * through) if maker_tp else tp

        last = min(k + hold, n) - 1
        exit_px = None
        kind = None
        j = k

        while j <= last:
            if s > 0:
                hit_sl = l[j] <= sl
                hit_tp = h[j] >= tp_chk
            else:
                hit_sl = h[j] >= sl
                hit_tp = l[j] <= tp_chk

            # En cas d'ambiguïté OHLC, SL d'abord.
            if hit_sl:
                exit_px = sl * (1 - s * slip_eff)
                kind = "sl"
                break

            if hit_tp:
                exit_px = tp if maker_tp else tp * (1 - s * slip_eff)
                kind = "tp"
                break

            j += 1

        if exit_px is None:
            j = last
            exit_px = c[j] * (1 - s * slip_eff)
            kind = "time"

        x_fee = fee_maker if (kind == "tp" and maker_tp) else fee_taker

        gross = s * (exit_px - entry) / entry
        net = gross - e_fee - x_fee * exit_px / entry

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

def basic_stats(trades: pd.DataFrame):
    if trades is None or trades.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "sd": np.nan,
            "win": np.nan,
            "pf": np.nan,
        }

    x = trades["net"].to_numpy(dtype=float)

    wins = x[x > 0].sum()
    losses = -x[x < 0].sum()

    return {
        "n": len(x),
        "mean": float(x.mean()),
        "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
        "win": float((x > 0).mean()),
        "pf": float(wins / losses) if losses > 0 else float("inf"),
    }


def equity_stats(trades: pd.DataFrame, capital: float):
    if trades is None or trades.empty:
        return {
            "final": capital,
            "return": 0.0,
            "max_dd": 0.0,
            "worst_trade": np.nan,
            "max_loss_streak": 0,
        }

    x = trades["net"].to_numpy(dtype=float)

    # Position = 100 % du capital disponible.
    equity = [capital]
    cur = capital

    for r in x:
        cur *= max(0.0, 1.0 + r)
        equity.append(cur)

    eq = np.asarray(equity)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0

    streak = 0
    max_streak = 0
    for r in x:
        if r < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return {
        "final": float(eq[-1]),
        "return": float(eq[-1] / capital - 1),
        "max_dd": float(dd.min()),
        "worst_trade": float(x.min()),
        "max_loss_streak": int(max_streak),
    }


def monte_carlo(trades: pd.DataFrame, capital: float, runs=MC_RUNS, seed=MC_SEED):
    """
    Bootstrap des trades avec remise.

    Ce n'est PAS une preuve indépendante: c'est un test de sensibilité
    de la distribution des trades observés.
    """
    if trades is None or len(trades) < 20:
        return {
            "mc_median": np.nan,
            "mc_p05": np.nan,
            "mc_p95": np.nan,
            "mc_dd_median": np.nan,
        }

    x = trades["net"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)

    finals = np.empty(runs)
    dds = np.empty(runs)

    for r in range(runs):
        sample = rng.choice(x, size=len(x), replace=True)
        eq = capital
        peak = capital
        worst_dd = 0.0

        for z in sample:
            eq *= max(0.0, 1.0 + z)
            peak = max(peak, eq)
            worst_dd = min(worst_dd, eq / peak - 1.0)

        finals[r] = eq
        dds[r] = worst_dd

    return {
        "mc_median": float(np.median(finals)),
        "mc_p05": float(np.percentile(finals, 5)),
        "mc_p95": float(np.percentile(finals, 95)),
        "mc_dd_median": float(np.median(dds)),
    }


# ============================================================
# WALK-FORWARD
# ============================================================

def make_folds(n: int, interval: str):
    """
    Folds calendaires exprimés en nombre de bougies.

    Le premier fold utilise TRAIN_DAYS puis TEST_DAYS.
    Les folds suivants avancent de STEP_DAYS.
    """
    bars_per_day = {
        "5m": 288,
        "15m": 96,
    }[interval]

    train = TRAIN_DAYS * bars_per_day
    test = TEST_DAYS * bars_per_day
    step = STEP_DAYS * bars_per_day

    folds = []
    start = 0

    while start + train + test <= n:
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


def score_training(stats):
    """
    Score uniquement utilisé pour choisir sur TRAIN.

    Il favorise:
        - moyenne nette positive
        - PF > 1
        - nombre de trades suffisant

    Aucun élément du TEST n'entre ici.
    """
    if stats["n"] < MIN_TRAIN_TRADES:
        return -np.inf

    if not np.isfinite(stats["mean"]):
        return -np.inf

    return stats["mean"]


# ============================================================
# RECHERCHE D'UN FOLD
# ============================================================

def evaluate_candidates(
    entry: pd.DataFrame,
    h1: pd.DataFrame,
    symbols_name: str,
    interval: str,
    capital: float,
    fee_scale=1.0,
    slip_scale=1.0,
):
    ef, candidates = make_candidates(entry, h1)

    L = {
        k: ef[k].to_numpy(dtype=float)
        for k in ("o", "h", "l", "c", "atr")
    }

    slip = SLIP.get(symbols_name, DEFAULT_SLIP)

    results = []

    for ci, cand in enumerate(candidates):
        for ei, (tp_m, sl_m, hold) in enumerate(EXITS):
            for prof in PROFILES:
                tr = simulate(
                    L,
                    cand.signal,
                    tp_m,
                    sl_m,
                    hold,
                    prof,
                    slip,
                    fee_scale=fee_scale,
                    slip_scale=slip_scale,
                )

                if tr.empty:
                    continue

                st = basic_stats(tr)

                results.append(
                    {
                        "candidate": ci,
                        "signal": cand.name,
                        "regime": cand.regime,
                        "exit": ei,
                        "tp": tp_m,
                        "sl": sl_m,
                        "hold": hold,
                        "profile": prof,
                        "trades": tr,
                        "n": st["n"],
                        "mean": st["mean"],
                        "sd": st["sd"],
                        "win": st["win"],
                        "pf": st["pf"],
                    }
                )

    return results


# ============================================================
# RAPPORT
# ============================================================

def stress_test(
    entry: pd.DataFrame,
    h1: pd.DataFrame,
    symbol: str,
    interval: str,
    best_spec: dict,
):
    """
    Rejoue uniquement la stratégie sélectionnée avec plusieurs coûts.
    """
    ef, candidates = make_candidates(entry, h1)

    L = {
        k: ef[k].to_numpy(dtype=float)
        for k in ("o", "h", "l", "c", "atr")
    }

    cand = candidates[int(best_spec["candidate"])]

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

    for name, fs, ss in scenarios:
        tr = simulate(
            L,
            cand.signal,
            float(best_spec["tp"]),
            float(best_spec["sl"]),
            int(best_spec["hold"]),
            best_spec["profile"],
            SLIP.get(symbol, DEFAULT_SLIP),
            fee_scale=fs,
            slip_scale=ss,
        )

        st = basic_stats(tr)
        es = equity_stats(tr, DEFAULT_CAPITAL)

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


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--symbols",
        default="BTCUSDT,ETHUSDT,SOLUSDT",
    )
    ap.add_argument(
        "--intervals",
        default="5m,15m",
        help="timeframes d'entrée; 1h est téléchargé automatiquement",
    )
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    ap.add_argument("--mc-runs", type=int, default=MC_RUNS)

    args = ap.parse_args()

    symbols = [x.strip() for x in args.symbols.split(",") if x.strip()]
    intervals = [x.strip() for x in args.intervals.split(",") if x.strip()]

    os.makedirs("results", exist_ok=True)

    md = []

    def out(s=""):
        print(s, flush=True)
        md.append(s)

    out("# SCALP LAB V2 — recherche scalping Binance USD-M")
    out("")
    out("## Méthode")
    out(
        "- données réelles Binance USD-M, bougies publiques"
    )
    out(
        f"- coûts: taker {FEE_TAKER*100:.2f}% / maker "
        f"{FEE_MAKER*100:.2f}% par côté"
    )
    out(
        "- slippage spécifique par symbole + stress-test"
    )
    out(
        "- signal sur bougie clôturée, entrée sur bougie suivante"
    )
    out(
        "- 1h = régime, 5m/15m = setup et entrée"
    )
    out(
        f"- walk-forward: {TRAIN_DAYS}j train / "
        f"{TEST_DAYS}j test / pas de {STEP_DAYS}j"
    )
    out(
        "- position fixe, aucune martingale, une position à la fois"
    )
    out("")

    all_wf = []
    all_stress = []

    for interval in intervals:
        if interval not in ("5m", "15m"):
            raise SystemExit("V2 accepte 5m et 15m comme timeframes d'entrée.")

        for symbol in symbols:
            out(f"## {symbol} {interval}")

            end_ms = int(time.time() * 1000)
            start_ms = end_ms - args.days * 86_400_000

            out(f"Téléchargement {symbol} {interval}...")
            entry = to_frame(
                fetch_vision(symbol, interval, start_ms, end_ms)
            )
            entry = entry[entry.time >= start_ms].reset_index(drop=True)

            out(f"Téléchargement {symbol} 1h...")
            h1 = to_frame(
                fetch_vision(symbol, "1h", start_ms, end_ms)
            )
            h1 = h1[h1.time >= start_ms].reset_index(drop=True)

            if len(entry) < 20_000 or len(h1) < 500:
                out(
                    f"INSUFFISANT: {len(entry)} bougies {interval}, "
                    f"{len(h1)} bougies 1h"
                )
                continue

            folds = make_folds(len(entry), interval)

            out(
                f"- {len(entry)} bougies {interval}, "
                f"{len(h1)} bougies 1h, {len(folds)} folds"
            )

            # Les candidats sont calculés sur toute la série, mais leurs
            # indicateurs utilisent uniquement le passé. La sélection
            # reste faite exclusivement avec les indices TRAIN.
            ef, candidates = make_candidates(entry, h1)
            Lfull = {
                k: ef[k].to_numpy(dtype=float)
                for k in ("o", "h", "l", "c", "atr")
            }

            slip = SLIP.get(symbol, DEFAULT_SLIP)

            for fold_id, (tr0, tr1, te0, te1) in enumerate(folds, 1):
                best = None

                for ci, cand in enumerate(candidates):
                    for ei, (tp_m, sl_m, hold) in enumerate(EXITS):
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

                            # sélection STRICTEMENT sur TRAIN:
                            # le signal_i doit être dans [tr0,tr1)
                            tr_train = tr_all[
                                (tr_all.signal_i >= tr0)
                                & (tr_all.signal_i < tr1)
                            ].copy()

                            if len(tr_train) < MIN_TRAIN_TRADES:
                                continue

                            st = basic_stats(tr_train)
                            score = score_training(st)

                            if best is None or score > best["score"]:
                                best = {
                                    "candidate": ci,
                                    "signal": cand.name,
                                    "regime": cand.regime,
                                    "exit": ei,
                                    "tp": tp_m,
                                    "sl": sl_m,
                                    "hold": hold,
                                    "profile": prof,
                                    "train_n": st["n"],
                                    "train_mean": st["mean"],
                                    "train_pf": st["pf"],
                                    "score": score,
                                }

                if best is None:
                    out(f"  fold {fold_id}: aucune stratégie avec assez de trades")
                    continue

                # Rejoue la stratégie choisie et ne garde que TEST.
                cand = candidates[int(best["candidate"])]

                te_all = simulate(
                    Lfull,
                    cand.signal,
                    float(best["tp"]),
                    float(best["sl"]),
                    int(best["hold"]),
                    best["profile"],
                    slip,
                )

                te = te_all[
                    (te_all.signal_i >= te0)
                    & (te_all.signal_i < te1)
                ].copy()

                st_te = basic_stats(te)
                es_te = equity_stats(te, args.capital)
                mc = monte_carlo(
                    te,
                    args.capital,
                    runs=args.mc_runs,
                    seed=MC_SEED + fold_id,
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
                    "profile": best["profile"],
                    "tp": best["tp"],
                    "sl": best["sl"],
                    "hold": best["hold"],
                    "train_n": best["train_n"],
                    "train_mean": best["train_mean"],
                    "train_pf": best["train_pf"],
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

                out(
                    f"  fold {fold_id}: "
                    f"{best['signal']} / {best['regime']} / {best['profile']} "
                    f"→ TEST {st_te['mean']*100:+.4f}% "
                    f"PF={st_te['pf']:.2f} "
                    f"DD={es_te['max_dd']*100:.2f}% "
                    f"n={st_te['n']}"
                )

                # Stress-test de la stratégie sélectionnée sur ce fold.
                stress = stress_test(
                    entry.iloc[te0:te1].reset_index(drop=True),
                    h1,
                    symbol,
                    interval,
                    best,
                )
                stress["symbol"] = symbol
                stress["interval"] = interval
                stress["fold"] = fold_id
                stress["signal"] = best["signal"]
                stress["regime"] = best["regime"]
                stress["profile"] = best["profile"]
                all_stress.append(stress)

    if not all_wf:
        raise SystemExit("Aucun résultat walk-forward.")

    WF = pd.DataFrame(all_wf)
    ST = pd.concat(all_stress, ignore_index=True) if all_stress else pd.DataFrame()

    WF.to_csv("results/walk_forward.csv", index=False)
    ST.to_csv("results/stress_test.csv", index=False)

    # ========================================================
    # RÉSUMÉ GLOBAL
    # ========================================================

    out("")
    out("## Résultat global walk-forward")
    out("")
    out(
        "| intervalle | folds | test mean/trade | folds positifs | "
        "return médian | DD médian | PF médian |"
    )
    out("|---|---:|---:|---:|---:|---:|---:|")

    for iv in sorted(WF.interval.unique()):
        x = WF[WF.interval == iv]

        out(
            f"| {iv} | {len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}/{len(x)} | "
            f"{x.test_return.median()*100:+.2f}% | "
            f"{x.test_max_dd.median()*100:.2f}% | "
            f"{x.test_pf.median():.2f} |"
        )

    out("")
    out("## Résultat par symbole")

    out(
        "| symbole | intervalle | folds | test moyen | positifs | "
        "return médian | DD médian |"
    )
    out("|---|---|---:|---:|---:|---:|---:|")

    for (sym, iv), x in WF.groupby(["symbol", "interval"]):
        out(
            f"| {sym} | {iv} | {len(x)} | "
            f"{x.test_mean.mean()*100:+.4f}% | "
            f"{int((x.test_mean > 0).sum())}/{len(x)} | "
            f"{x.test_return.median()*100:+.2f}% | "
            f"{x.test_max_dd.median()*100:.2f}% |"
        )

    out("")
    out("## Robustesse des coûts")

    if not ST.empty:
        for scenario, x in ST.groupby("scenario"):
            out(
                f"- **{scenario}** : "
                f"mean/trade {x['mean'].mean()*100:+.4f}% ; "
                f"PF médian {x['pf'].median():.2f} ; "
                f"DD médian {x['max_dd'].median()*100:.2f}%"
            )

    # ========================================================
    # VERDICT TECHNIQUE
    # ========================================================

    positive_folds = int((WF.test_mean > 0).sum())
    total_folds = len(WF)
    median_test = float(WF.test_mean.median())

    out("")
    out("## Verdict V2")

    if total_folds >= 4 and positive_folds / total_folds >= 0.60 and median_test > 0:
        out(
            "Le laboratoire trouve un signal potentiellement robuste "
            "sur plusieurs folds walk-forward. Ce résultat doit encore "
            "être confirmé sur des données/périodes supplémentaires puis "
            "en paper trading."
        )
    else:
        out(
            "Le laboratoire ne trouve pas encore de preuve suffisante "
            "d'un avantage robuste hors échantillon sur les folds testés. "
            "Il faut améliorer les hypothèses/signaux ou étendre "
            "l'échantillon avant de construire le bot réel."
        )

    out("")
    out(
        "Limites: bougies OHLCV, pas de carnet d'ordres, exécution limite "
        "approximée, pas de funding, pas de latence réseau, et Monte-Carlo "
        "basé sur les trades observés."
    )

    with open("results/summary_v2.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()
