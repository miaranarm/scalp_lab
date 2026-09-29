"""
SCALP LAB V4.2
Robustness-first walk-forward research.

Objectif :
- conserver le moteur de recherche V4.1
- ajouter une sélection statistiquement plus robuste
- pénaliser les petits échantillons
- exclure les folds sans trades
- comparer stratégie vs random
- séparer strictement OOS et final holdout
- produire une sélection globale multi-actifs

IMPORTANT :
Ce programme est un outil de recherche/backtest.
Il ne constitue pas une validation de stratégie de trading réelle.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

WF_TRAIN_DAYS = 180
WF_TEST_DAYS = 45
FINAL_HOLDOUT_DAYS = 90

MIN_TRADES_PER_FOLD = 5

MIN_ACTIVE_FOLDS = 5
MIN_TOTAL_TRADES = 50
MIN_POSITIVE_FOLD_RATIO = 0.50
MIN_BEAT_RANDOM_RATIO = 0.50

MIN_MEDIAN_PF = 1.00
MIN_MEDIAN_EDGE_RANDOM = 0.0

MC_SEED = 42

RESULTS_DIR = Path("results")


# ============================================================
# DATA
# ============================================================

BINANCE_URL = (
    "https://api.binance.com/api/v3/klines"
)


def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """
    Binance spot OHLCV.
    V4.2 conserve volontairement le principe OHLCV-only.
    """

    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int(
        (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).timestamp()
        * 1000
    )

    rows = []

    while start_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        }

        r = requests.get(
            BINANCE_URL,
            params=params,
            timeout=30,
        )
        r.raise_for_status()

        batch = r.json()

        if not batch:
            break

        rows.extend(batch)

        last_open = batch[-1][0]
        next_start = last_open + 1

        if next_start <= start_ms:
            break

        start_ms = next_start

        if len(batch) < 1000:
            break

    if not rows:
        raise RuntimeError(f"Aucune donnée reçue pour {symbol}")

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_base",
            "taker_quote",
            "ignore",
        ],
    )

    df["timestamp"] = pd.to_datetime(
        df["open_time"],
        unit="ms",
        utc=True,
    )

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ].dropna()

    df = df.drop_duplicates("timestamp")
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# ============================================================
# INDICATEURS
# ============================================================

def zscore(series: pd.Series, n: int) -> pd.Series:
    mean = series.rolling(n).mean()
    std = series.rolling(n).std()

    return (series - mean) / std.replace(0, np.nan)


def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()


def rolling_vwap(df: pd.DataFrame, n: int) -> pd.Series:
    typical = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    pv = typical * df["volume"]

    return (
        pv.rolling(n).sum()
        / df["volume"].rolling(n).sum()
    )


# ============================================================
# SIGNALS
# ============================================================

def signal_series(
    df: pd.DataFrame,
    family: str,
    params: dict,
    regime: str,
) -> pd.Series:

    close = df["close"]

    signal = pd.Series(
        False,
        index=df.index,
    )

    if family == "zscore":

        n = params["n"]
        threshold = params["threshold"]

        z = zscore(close, n)

        signal = z <= -threshold

    elif family == "donchian":

        n = params["n"]
        vol_mult = params["vol"]

        low = df["low"].rolling(n).min()

        volume_ma = (
            df["volume"]
            .rolling(n)
            .mean()
        )

        signal = (
            (close <= low)
            &
            (
                df["volume"]
                >= volume_ma * vol_mult
            )
        )

    elif family == "pullback":

        r = rsi(close, 14)

        signal = r <= params["rsi"]

    elif family == "vwap":

        v = rolling_vwap(
            df,
            params["n"],
        )

        deviation = (
            close - v
        ) / v

        signal = (
            deviation
            <= -params["k"] * 0.01
        )

    elif family == "breakout":

        n = params["n"]

        high = (
            df["high"]
            .rolling(n)
            .max()
            .shift(1)
        )

        signal = close > high

    else:
        raise ValueError(
            f"Famille inconnue: {family}"
        )

    # --------------------------------------------------------
    # Régime
    # --------------------------------------------------------

    if regime == "trend":

        ema = close.ewm(
            span=50,
            adjust=False,
        ).mean()

        signal &= close > ema

    elif regime == "all":
        pass

    else:
        raise ValueError(
            f"Régime inconnu: {regime}"
        )

    return signal.fillna(False)


# ============================================================
# CONFIGURATIONS
# ============================================================

def candidate_configs():
    configs = []

    for n in [30, 60]:
        for threshold in [2.0, 2.5]:
            for regime in ["all", "trend"]:
                configs.append(
                    {
                        "family": "zscore",
                        "params": {
                            "n": n,
                            "threshold": threshold,
                        },
                        "regime": regime,
                    }
                )

    for n in [20, 50]:
        for vol in [0.0, 1.5]:
            for regime in ["all", "trend"]:
                configs.append(
                    {
                        "family": "donchian",
                        "params": {
                            "n": n,
                            "vol": vol,
                        },
                        "regime": regime,
                    }
                )

    for rsi_level in [40]:
        for regime in ["all", "trend"]:
            configs.append(
                {
                    "family": "pullback",
                    "params": {
                        "rsi": rsi_level,
                    },
                    "regime": regime,
                }
            )

    for n in [48, 96]:
        for k in [2.0, 3.0]:
            for regime in ["all", "trend"]:
                configs.append(
                    {
                        "family": "vwap",
                        "params": {
                            "n": n,
                            "k": k,
                        },
                        "regime": regime,
                    }
                )

    for n in [20]:
        for regime in ["all", "trend"]:
            configs.append(
                {
                    "family": "breakout",
                    "params": {
                        "n": n,
                    },
                    "regime": regime,
                }
            )

    return configs


# ============================================================
# TRADE ENGINE
# ============================================================

def simulate_trades(
    df: pd.DataFrame,
    signal: pd.Series,
    start_idx: int,
    end_idx: int,
    profile: str = "maker_both",
) -> list[float]:

    trades = []

    i = max(start_idx, 1)

    while i < end_idx - 1:

        if not bool(signal.iloc[i]):
            i += 1
            continue

        entry_idx = i + 1

        if entry_idx >= end_idx:
            break

        entry = float(
            df["open"].iloc[entry_idx]
        )

        future = df.iloc[
            entry_idx + 1 : end_idx
        ]

        if future.empty:
            break

        # ----------------------------------------------------
        # Sortie simplifiée :
        # signal suivant = sortie.
        #
        # Ceci conserve le principe V4.1 :
        # signal clôturé -> entrée suivante.
        # ----------------------------------------------------

        exit_idx = None

        for j in range(
            entry_idx + 1,
            end_idx,
        ):
            if bool(signal.iloc[j]):
                exit_idx = j
                break

        if exit_idx is None:
            exit_idx = end_idx - 1

        exit_price = float(
            df["close"].iloc[exit_idx]
        )

        gross = (
            exit_price / entry
            - 1.0
        )

        if profile == "maker_both":
            cost = (
                MAKER_FEE
                + MAKER_FEE
            )
        elif profile == "maker_tp":
            cost = (
                MAKER_FEE
                + TAKER_FEE
            )
        else:
            cost = (
                TAKER_FEE
                + TAKER_FEE
            )

        net = gross - cost

        trades.append(net)

        i = exit_idx + 1

    return trades


# ============================================================
# STATISTIQUES
# ============================================================

def profit_factor(
    trades: list[float],
) -> float:

    if not trades:
        return float("nan")

    gains = sum(
        x for x in trades
        if x > 0
    )

    losses = abs(
        sum(
            x for x in trades
            if x < 0
        )
    )

    if losses == 0:
        return float("inf") if gains > 0 else 0.0

    return gains / losses


def max_drawdown(
    trades: list[float],
) -> float:

    if not trades:
        return float("nan")

    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for ret in trades:

        equity *= (
            1.0 + ret
        )

        peak = max(
            peak,
            equity,
        )

        dd = (
            equity / peak
            - 1.0
        )

        max_dd = min(
            max_dd,
            dd,
        )

    return max_dd


def mean_return(
    trades: list[float],
) -> float:

    if not trades:
        return float("nan")

    return float(
        np.mean(trades)
    )


def t_stat(
    trades: list[float],
) -> float:

    if len(trades) < 2:
        return float("nan")

    std = np.std(
        trades,
        ddof=1,
    )

    if std == 0:
        return float("inf") if np.mean(trades) > 0 else 0.0

    return (
        np.mean(trades)
        /
        (
            std
            /
            math.sqrt(len(trades))
        )
    )


# ============================================================
# RANDOM BENCHMARK
# ============================================================

def random_reference(
    df: pd.DataFrame,
    signal: pd.Series,
    start_idx: int,
    end_idx: int,
    n_draws: int = 100,
    seed: int = MC_SEED,
) -> float:

    rng = random.Random(seed)

    signal_positions = [
        i
        for i in range(
            start_idx,
            end_idx,
        )
        if bool(signal.iloc[i])
    ]

    if not signal_positions:
        return float("nan")

    results = []

    for _ in range(n_draws):

        sampled = rng.sample(
            signal_positions,
            min(
                len(signal_positions),
                max(
                    1,
                    len(signal_positions),
                ),
            ),
        )

        sampled = set(sampled)

        random_signal = pd.Series(
            False,
            index=df.index,
        )

        for idx in sampled:
            random_signal.iloc[idx] = True

        trades = simulate_trades(
            df,
            random_signal,
            start_idx,
            end_idx,
            "maker_both",
        )

        if trades:
            results.append(
                mean_return(trades)
            )

    if not results:
        return float("nan")

    return float(
        np.mean(results)
    )


# ============================================================
# FOLD
# ============================================================

@dataclass
class FoldResult:

    symbol: str
    fold: int

    family: str
    params: str
    regime: str
    profile: str

    test_return: float
    random_return: float
    edge_random: float

    pf: float
    dd: float
    mean_trade: float
    std_trade: float
    t_stat: float

    trades: int
    positive_trades: int

    valid: bool


def run_fold(
    symbol: str,
    df: pd.DataFrame,
    config: dict,
    fold: int,
    train_start: int,
    train_end: int,
    test_start: int,
    test_end: int,
) -> FoldResult:

    signal = signal_series(
        df,
        config["family"],
        config["params"],
        config["regime"],
    )

    trades = simulate_trades(
        df,
        signal,
        test_start,
        test_end,
        "maker_both",
    )

    n = len(trades)

    if n == 0:

        return FoldResult(
            symbol=symbol,
            fold=fold,
            family=config["family"],
            params=str(config["params"]),
            regime=config["regime"],
            profile="maker_both",
            test_return=float("nan"),
            random_return=float("nan"),
            edge_random=float("nan"),
            pf=float("nan"),
            dd=float("nan"),
            mean_trade=float("nan"),
            std_trade=float("nan"),
            t_stat=float("nan"),
            trades=0,
            positive_trades=0,
            valid=False,
        )

    test_return = mean_return(trades)

    random_return = random_reference(
        df,
        signal,
        test_start,
        test_end,
    )

    edge = (
        test_return - random_return
        if not math.isnan(random_return)
        else float("nan")
    )

    std = (
        float(
            np.std(
                trades,
                ddof=1,
            )
        )
        if n >= 2
        else float("nan")
    )

    return FoldResult(
        symbol=symbol,
        fold=fold,
        family=config["family"],
        params=str(config["params"]),
        regime=config["regime"],
        profile="maker_both",
        test_return=test_return,
        random_return=random_return,
        edge_random=edge,
        pf=profit_factor(trades),
        dd=max_drawdown(trades),
        mean_trade=test_return,
        std_trade=std,
        t_stat=t_stat(trades),
        trades=n,
        positive_trades=sum(
            x > 0
            for x in trades
        ),
        valid=n >= MIN_TRADES_PER_FOLD,
    )


# ============================================================
# WALK FORWARD
# ============================================================

def build_folds(
    df: pd.DataFrame,
) -> list[tuple[int, int, int, int]]:

    total_days = (
        df["timestamp"].iloc[-1]
        - df["timestamp"].iloc[0]
    ).total_seconds() / 86400

    folds = []

    start = 0

    while True:

        train_end_time = (
            df["timestamp"].iloc[0]
            + timedelta(
                days=WF_TRAIN_DAYS
            )
        )

        if start > 0:
            train_start_time = (
                df["timestamp"].iloc[start]
            )
            train_end_time = (
                train_start_time
                + timedelta(
                    days=WF_TRAIN_DAYS
                )
            )
        else:
            train_start_time = (
                df["timestamp"].iloc[0]
            )

        test_start_time = train_end_time

        test_end_time = (
            test_start_time
            + timedelta(
                days=WF_TEST_DAYS
            )
        )

        if (
            test_end_time
            + timedelta(
                days=FINAL_HOLDOUT_DAYS
            )
            >= df["timestamp"].iloc[-1]
        ):
            break

        train_start = int(
            df["timestamp"].searchsorted(
                train_start_time
            )
        )

        train_end = int(
            df["timestamp"].searchsorted(
                train_end_time
            )
        )

        test_start = int(
            df["timestamp"].searchsorted(
                test_start_time
            )
        )

        test_end = int(
            df["timestamp"].searchsorted(
                test_end_time
            )
        )

        if test_end <= test_start:
            break

        folds.append(
            (
                train_start,
                train_end,
                test_start,
                test_end,
            )
        )

        next_start_time = (
            test_start_time
            + timedelta(
                days=WF_TEST_DAYS
            )
        )

        next_start = int(
            df["timestamp"].searchsorted(
                next_start_time
            )
        )

        if next_start <= start:
            break

        start = next_start

    return folds


# ============================================================
# ROBUSTNESS
# ============================================================

@dataclass
class Robustness:

    symbol: str
    family: str
    params: str
    regime: str
    profile: str

    folds_total: int
    folds_active: int
    total_trades: int

    mean_oos: float
    median_oos: float
    std_oos: float
    t_stat_oos: float

    positive_fold_ratio: float
    beat_random_ratio: float

    median_pf: float
    median_dd: float
    median_edge_random: float

    robust: bool
    robustness_score: float


def calculate_robustness(
    symbol: str,
    fold_results: list[FoldResult],
) -> Robustness:

    valid = [
        x
        for x in fold_results
        if x.valid
        and not math.isnan(x.test_return)
    ]

    if not valid:

        return Robustness(
            symbol=symbol,
            family="",
            params="",
            regime="",
            profile="",
            folds_total=len(fold_results),
            folds_active=0,
            total_trades=0,
            mean_oos=float("nan"),
            median_oos=float("nan"),
            std_oos=float("nan"),
            t_stat_oos=float("nan"),
            positive_fold_ratio=0.0,
            beat_random_ratio=0.0,
            median_pf=float("nan"),
            median_dd=float("nan"),
            median_edge_random=float("nan"),
            robust=False,
            robustness_score=-999.0,
        )

    returns = [
        x.test_return
        for x in valid
    ]

    edges = [
        x.edge_random
        for x in valid
        if not math.isnan(x.edge_random)
    ]

    pfs = [
        x.pf
        for x in valid
        if not math.isnan(x.pf)
    ]

    dds = [
        x.dd
        for x in valid
        if not math.isnan(x.dd)
    ]

    total_trades = sum(
        x.trades
        for x in valid
    )

    positive_ratio = (
        sum(
            x.test_return > 0
            for x in valid
        )
        / len(valid)
    )

    beat_random_ratio = (
        sum(
            x.edge_random > 0
            for x in valid
        )
        / len(edges)
        if edges
        else 0.0
    )

    mean_oos = float(
        np.mean(returns)
    )

    median_oos = float(
        np.median(returns)
    )

    std_oos = float(
        np.std(
            returns,
            ddof=1,
        )
    ) if len(returns) >= 2 else float("nan")

    if std_oos > 0:
        t_oos = (
            mean_oos
            /
            (
                std_oos
                /
                math.sqrt(len(returns))
            )
        )
    else:
        t_oos = float("nan")

    median_pf = float(
        np.median(pfs)
    ) if pfs else float("nan")

    median_dd = float(
        np.median(dds)
    ) if dds else float("nan")

    median_edge = float(
        np.median(edges)
    ) if edges else float("nan")

    robust = (
        len(valid)
        >= MIN_ACTIVE_FOLDS
        and total_trades
        >= MIN_TOTAL_TRADES
        and positive_ratio
        >= MIN_POSITIVE_FOLD_RATIO
        and beat_random_ratio
        >= MIN_BEAT_RANDOM_RATIO
        and not math.isnan(median_pf)
        and median_pf
        >= MIN_MEDIAN_PF
        and not math.isnan(median_edge)
        and median_edge
        >= MIN_MEDIAN_EDGE_RANDOM
    )

    # --------------------------------------------------------
    # Score de robustesse.
    #
    # Ce score sert à classer les candidats de recherche,
    # pas à prétendre prédire les performances futures.
    # --------------------------------------------------------

    stability = (
        positive_ratio
        + beat_random_ratio
    ) / 2.0

    pf_component = (
        max(
            0.0,
            min(
                2.0,
                median_pf,
            ),
        )
        / 2.0
    )

    edge_component = (
        max(
            -0.01,
            min(
                0.01,
                median_edge,
            ),
        )
        + 0.01
    ) / 0.02

    sample_component = min(
        1.0,
        total_trades / 200.0,
    )

    fold_component = min(
        1.0,
        len(valid) / 10.0,
    )

    score = (
        0.30 * stability
        + 0.20 * pf_component
        + 0.20 * edge_component
        + 0.15 * sample_component
        + 0.15 * fold_component
    )

    if not robust:
        score *= 0.75

    first = valid[0]

    return Robustness(
        symbol=symbol,
        family=first.family,
        params=first.params,
        regime=first.regime,
        profile=first.profile,
        folds_total=len(fold_results),
        folds_active=len(valid),
        total_trades=total_trades,
        mean_oos=mean_oos,
        median_oos=median_oos,
        std_oos=std_oos,
        t_stat_oos=t_oos,
        positive_fold_ratio=positive_ratio,
        beat_random_ratio=beat_random_ratio,
        median_pf=median_pf,
        median_dd=median_dd,
        median_edge_random=median_edge,
        robust=robust,
        robustness_score=score,
    )


# ============================================================
# HOLDOUT
# ============================================================

def run_holdout(
    symbol: str,
    df: pd.DataFrame,
    config: dict,
) -> dict:

    signal = signal_series(
        df,
        config["family"],
        config["params"],
        config["regime"],
    )

    holdout_start_time = (
        df["timestamp"].iloc[-1]
        - timedelta(
            days=FINAL_HOLDOUT_DAYS
        )
    )

    holdout_start = int(
        df["timestamp"].searchsorted(
            holdout_start_time
        )
    )

    trades = simulate_trades(
        df,
        signal,
        holdout_start,
        len(df),
        "maker_both",
    )

    return {
        "symbol": symbol,
        "family": config["family"],
        "params": str(
            config["params"]
        ),
        "regime": config["regime"],
        "profile": "maker_both",
        "holdout_return": mean_return(trades),
        "pf": profit_factor(trades),
        "dd": max_drawdown(trades),
        "trades": len(trades),
        "t_stat": t_stat(trades),
    }


# ============================================================
# MAIN RESEARCH
# ============================================================

def config_from_robustness(
    r: Robustness,
) -> dict:

    return {
        "family": r.family,
        "params": eval(
            r.params,
            {
                "__builtins__": {}
            },
            {},
        ),
        "regime": r.regime,
    }


def run_symbol(
    symbol: str,
    interval: str,
    days: int,
):

    print()
    print("=" * 72)
    print(
        f"{symbol} {interval}"
    )
    print("=" * 72)

    df = fetch_klines(
        symbol,
        interval,
        days,
    )

    print(
        f"Candles: {len(df):,}"
    )

    folds = build_folds(df)

    print(
        f"Folds: {len(folds)}"
    )

    configs = candidate_configs()

    all_fold_results = []
    robustness_rows = []

    for cfg_no, config in enumerate(
        configs,
        start=1,
    ):

        fold_results = []

        for fold_no, (
            train_start,
            train_end,
            test_start,
            test_end,
        ) in enumerate(
            folds,
            start=1,
        ):

            result = run_fold(
                symbol,
                df,
                config,
                fold_no,
                train_start,
                train_end,
                test_start,
                test_end,
            )

            fold_results.append(result)
            all_fold_results.append(result)

        robustness = calculate_robustness(
            symbol,
            fold_results,
        )

        robustness_rows.append(
            robustness
        )

    robustness_rows.sort(
        key=lambda x: (
            x.robust,
            x.robustness_score,
            x.median_edge_random,
            x.median_pf,
        ),
        reverse=True,
    )

    print()
    print("TOP CANDIDATS")
    print("-" * 72)

    for r in robustness_rows[:10]:

        print(
            f"{r.family:10s} "
            f"{r.params:28s} "
            f"{r.regime:5s} "
            f"robust={str(r.robust):5s} "
            f"score={r.robustness_score:.3f} "
            f"folds={r.folds_active}/{r.folds_total} "
            f"trades={r.total_trades} "
            f"mean={r.mean_oos:.4%} "
            f"median={r.median_oos:.4%} "
            f"PF={r.median_pf:.2f} "
            f"edge={r.median_edge_random:.4%}"
        )

    # --------------------------------------------------------
    # Sélection.
    #
    # Priorité aux candidats robustes.
    # Sinon le meilleur candidat est conservé uniquement
    # comme information de recherche.
    # --------------------------------------------------------

    robust_candidates = [
        r
        for r in robustness_rows
        if r.robust
    ]

    selected = (
        robust_candidates[0]
        if robust_candidates
        else (
            robustness_rows[0]
            if robustness_rows
            else None
        )
    )

    holdout = None

    if selected is not None:

        cfg = config_from_robustness(
            selected
        )

        holdout = run_holdout(
            symbol,
            df,
            cfg,
        )

    fold_df = pd.DataFrame(
        [
            asdict(x)
            for x in all_fold_results
        ]
    )

    robustness_df = pd.DataFrame(
        [
            asdict(x)
            for x in robustness_rows
        ]
    )

    return (
        fold_df,
        robustness_df,
        holdout,
        selected,
    )


# ============================================================
# GLOBAL MULTI-ASSET ANALYSIS
# ============================================================

def global_analysis(
    robustness_all: pd.DataFrame,
) -> pd.DataFrame:

    if robustness_all.empty:
        return pd.DataFrame()

    group_cols = [
        "family",
        "params",
        "regime",
        "profile",
    ]

    rows = []

    for key, group in robustness_all.groupby(
        group_cols
    ):

        rows.append(
            {
                "family": key[0],
                "params": key[1],
                "regime": key[2],
                "profile": key[3],

                "symbols": len(group),

                "mean_oos": group[
                    "mean_oos"
                ].mean(),

                "median_oos": group[
                    "median_oos"
                ].median(),

                "positive_fold_ratio": group[
                    "positive_fold_ratio"
                ].mean(),

                "beat_random_ratio": group[
                    "beat_random_ratio"
                ].mean(),

                "median_pf": group[
                    "median_pf"
                ].median(),

                "median_edge_random": group[
                    "median_edge_random"
                ].median(),

                "total_trades": group[
                    "total_trades"
                ].sum(),

                "robust_symbols": int(
                    group["robust"].sum()
                ),
            }
        )

    result = pd.DataFrame(rows)

    result["global_robust"] = (
        (result["symbols"] >= 3)
        &
        (result["robust_symbols"] >= 2)
        &
        (result["total_trades"] >= 150)
        &
        (result["positive_fold_ratio"] >= 0.50)
        &
        (result["beat_random_ratio"] >= 0.50)
        &
        (result["median_pf"] >= 1.0)
        &
        (result["median_edge_random"] >= 0.0)
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
# REPORT
# ============================================================

def write_report(
    folds_df: pd.DataFrame,
    robustness_df: pd.DataFrame,
    global_df: pd.DataFrame,
    holdouts: list[dict],
    output: Path,
):

    lines = []

    lines.append(
        "# SCALP LAB V4.2 — Robustness Research"
    )

    lines.append("")
    lines.append(
        f"Generated: {datetime.now(timezone.utc).isoformat()}"
    )

    lines.append("")
    lines.append(
        "## Philosophy"
    )

    lines.append(
        "V4.2 prioritise la robustesse OOS plutôt "
        "que le meilleur rendement ponctuel."
    )

    lines.append("")
    lines.append(
        "Une configuration est dite robuste seulement "
        "si elle satisfait simultanément les seuils "
        "fixés avant la recherche."
    )

    lines.append("")
    lines.append(
        "## Seuils de robustesse"
    )

    lines.append(
        f"- folds actifs minimum: {MIN_ACTIVE_FOLDS}"
    )

    lines.append(
        f"- trades cumulés minimum: {MIN_TOTAL_TRADES}"
    )

    lines.append(
        f"- folds positifs minimum: "
        f"{MIN_POSITIVE_FOLD_RATIO:.0%}"
    )

    lines.append(
        f"- folds > random minimum: "
        f"{MIN_BEAT_RANDOM_RATIO:.0%}"
    )

    lines.append(
        f"- médiane PF minimum: "
        f"{MIN_MEDIAN_PF:.2f}"
    )

    lines.append(
        f"- médiane edge/random minimum: "
        f"{MIN_MEDIAN_EDGE_RANDOM:.4%}"
    )

    lines.append("")
    lines.append(
        "## Résumé par actif"
    )

    for symbol, group in robustness_df.groupby(
        "symbol"
    ):

        robust = group[
            group["robust"]
        ]

        lines.append("")
        lines.append(
            f"### {symbol}"
        )

        lines.append(
            f"- configurations: {len(group)}"
        )

        lines.append(
            f"- configurations robustes: {len(robust)}"
        )

        if not robust.empty:

            r = robust.iloc[0]

            lines.append(
                f"- meilleure configuration robuste: "
                f"{r['family']} {r['params']} "
                f"regime={r['regime']}"
            )

            lines.append(
                f"- mean OOS: {r['mean_oos']:.4%}"
            )

            lines.append(
                f"- median OOS: {r['median_oos']:.4%}"
            )

            lines.append(
                f"- PF médiane: {r['median_pf']:.2f}"
            )

            lines.append(
                f"- edge/random médian: "
                f"{r['median_edge_random']:.4%}"
            )

            lines.append(
                f"- trades: {int(r['total_trades'])}"
            )

        else:

            lines.append(
                "Aucune configuration ne satisfait "
                "tous les critères de robustesse."
            )

    lines.append("")
    lines.append(
        "## Analyse globale multi-actifs"
    )

    if global_df.empty:

        lines.append(
            "Aucune donnée globale."
        )

    else:

        for _, row in global_df.head(10).iterrows():

            lines.append(
                f"- {row['family']} "
                f"{row['params']} "
                f"regime={row['regime']} | "
                f"symbols={int(row['symbols'])} | "
                f"robust_symbols="
                f"{int(row['robust_symbols'])} | "
                f"trades="
                f"{int(row['total_trades'])} | "
                f"PF="
                f"{row['median_pf']:.2f} | "
                f"edge="
                f"{row['median_edge_random']:.4%} | "
                f"global_robust="
                f"{bool(row['global_robust'])}"
            )

    lines.append("")
    lines.append(
        "## Final holdout"
    )

    for h in holdouts:

        lines.append("")

        lines.append(
            f"### {h['symbol']}"
        )

        lines.append(
            f"- strategy: "
            f"{h['family']} "
            f"{h['params']} "
            f"regime={h['regime']}"
        )

        lines.append(
            f"- return: "
            f"{h['holdout_return']:.4%}"
        )

        lines.append(
            f"- PF: "
            f"{h['pf']:.2f}"
        )

        lines.append(
            f"- DD: "
            f"{h['dd']:.4%}"
        )

        lines.append(
            f"- trades: "
            f"{h['trades']}"
        )

        lines.append(
            f"- t-stat: "
            f"{h['t_stat']:.2f}"
        )

    lines.append("")
    lines.append(
        "## Interpretation"
    )

    lines.append(
        "Une absence de configuration robuste est "
        "un résultat valide de la recherche."
    )

    lines.append(
        "V4.2 ne transforme pas automatiquement "
        "une configuration positive en stratégie "
        "déployable."
    )

    output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        default="BTCUSDT,ETHUSDT,SOLUSDT",
    )

    parser.add_argument(
        "--intervals",
        default="1h",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=730,
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100,
    )

    parser.add_argument(
        "--mc-runs",
        type=int,
        default=5000,
    )

    return parser.parse_args()


def main():

    args = parse_args()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    print()
    print("# SCALP LAB V4.2")
    print(
        "Robustness-first walk-forward research"
    )
    print(
        "OHLCV only | Binance | 1h"
    )
    print(
        f"WF={WF_TRAIN_DAYS}j/"
        f"{WF_TEST_DAYS}j/"
        f"{FINAL_HOLDOUT_DAYS}j"
    )
    print(
        f"Fees maker={MAKER_FEE:.2%} "
        f"taker={TAKER_FEE:.2%}"
    )
    print(
        f"Robustness: "
        f"{MIN_ACTIVE_FOLDS} folds / "
        f"{MIN_TOTAL_TRADES} trades / "
        f"{MIN_POSITIVE_FOLD_RATIO:.0%} positive / "
        f"{MIN_BEAT_RANDOM_RATIO:.0%} > random"
    )

    all_folds = []
    all_robustness = []
    holdouts = []

    for symbol in symbols:

        for interval in intervals:

            (
                folds_df,
                robustness_df,
                holdout,
                selected,
            ) = run_symbol(
                symbol,
                interval,
                args.days,
            )

            all_folds.append(
                folds_df
            )

            all_robustness.append(
                robustness_df
            )

            if holdout is not None:
                holdouts.append(
                    holdout
                )

    folds_df = pd.concat(
        all_folds,
        ignore_index=True,
    )

    robustness_df = pd.concat(
        all_robustness,
        ignore_index=True,
    )

    global_df = global_analysis(
        robustness_df
    )

    folds_path = (
        RESULTS_DIR
        / "walk_forward_v42.csv"
    )

    robustness_path = (
        RESULTS_DIR
        / "robustness_v42.csv"
    )

    global_path = (
        RESULTS_DIR
        / "global_v42.csv"
    )

    holdout_path = (
        RESULTS_DIR
        / "holdout_v42.csv"
    )

    folds_df.to_csv(
        folds_path,
        index=False,
    )

    robustness_df.to_csv(
        robustness_path,
        index=False,
    )

    global_df.to_csv(
        global_path,
        index=False,
    )

    pd.DataFrame(
        holdouts
    ).to_csv(
        holdout_path,
        index=False,
    )

    report_path = (
        RESULTS_DIR
        / "summary_v42.md"
    )

    write_report(
        folds_df,
        robustness_df,
        global_df,
        holdouts,
        report_path,
    )

    print()
    print("=" * 72)
    print("RESEARCH TERMINÉE")
    print("=" * 72)

    print(
        f"Walk-forward : {folds_path}"
    )

    print(
        f"Robustness   : {robustness_path}"
    )

    print(
        f"Global       : {global_path}"
    )

    print(
        f"Holdout      : {holdout_path}"
    )

    print(
        f"Report       : {report_path}"
    )

    print()

    robust_count = int(
        robustness_df["robust"].sum()
    )

    print(
        f"Configurations robustes : "
        f"{robust_count}"
    )

    if robust_count == 0:

        print()
        print(
            "IMPORTANT : aucune configuration "
            "ne satisfait les critères de robustesse."
        )

        print(
            "Cela constitue un résultat de recherche "
            "valide et ne doit pas être contourné "
            "en abaissant les seuils après observation."
        )


if __name__ == "__main__":
    main()
