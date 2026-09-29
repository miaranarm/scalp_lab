from __future__ import annotations

import argparse
import io
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

OUT = Path("results")
OUT.mkdir(exist_ok=True)

# ============================================================
# CONFIGURATION
# ============================================================

VALIDATION_DAYS = 90

FT = 0.0005          # taker
FM = 0.0002          # maker

SLIP = {
    "BTCUSDT": 0.00010,
    "ETHUSDT": 0.00015,
    "SOLUSDT": 0.00030,
}

UA = {"User-Agent": "Mozilla/5.0"}

COLS = [
    "time", "open", "high", "low", "close", "volume",
    "ct", "qv", "trades", "tbv", "tqv", "x"
]

# ============================================================
# CANDIDATS FIGÉS
#
# Aucun classement effectué avec les données de validation.
# ============================================================

CANDIDATES = [
    {
        "id": "ETH_DONCHIAN_SHORT_ALL_TAKER_2_2_24",
        "symbol": "ETHUSDT",
        "sig": "donchian20_v0_short",
        "side": "S",
        "family": "donchian",
        "regime": "all",
        "profile": "taker",
        "tp": 2.0,
        "sl": 2.0,
        "hold": 24,
    },
    {
        "id": "ETH_DONCHIAN_SHORT_TREND_TAKER_2_2_24",
        "symbol": "ETHUSDT",
        "sig": "donchian20_v0_short",
        "side": "S",
        "family": "donchian",
        "regime": "trend",
        "profile": "taker",
        "tp": 2.0,
        "sl": 2.0,
        "hold": 24,
    },
    {
        "id": "ETH_MEAN96_SHORT_TREND_MB_3_1.5_36",
        "symbol": "ETHUSDT",
        "sig": "mean96_k2_short",
        "side": "S",
        "family": "mean",
        "regime": "trend",
        "profile": "maker_both",
        "tp": 3.0,
        "sl": 1.5,
        "hold": 36,
    },
    {
        "id": "ETH_VWAP48_SHORT_TREND_MB_3_1.5_36",
        "symbol": "ETHUSDT",
        "sig": "vwap48_k2_short",
        "side": "S",
        "family": "vwap",
        "regime": "trend",
        "profile": "maker_both",
        "tp": 3.0,
        "sl": 1.5,
        "hold": 36,
    },
    {
        "id": "SOL_DONCHIAN_LONG_ALL_MB_3_1.5_36",
        "symbol": "SOLUSDT",
        "sig": "donchian20_v0",
        "side": "L",
        "family": "donchian",
        "regime": "all",
        "profile": "maker_both",
        "tp": 3.0,
        "sl": 1.5,
        "hold": 36,
    },
    {
        "id": "SOL_MEAN96_SHORT_TREND_MB_2_2_24",
        "symbol": "SOLUSDT",
        "sig": "mean96_k2_short",
        "side": "S",
        "family": "mean",
        "regime": "trend",
        "profile": "maker_both",
        "tp": 2.0,
        "sl": 2.0,
        "hold": 24,
    },
    {
        "id": "SOL_VWAP48_SHORT_TREND_MB_3_1.5_36",
        "symbol": "SOLUSDT",
        "sig": "vwap48_k2_short",
        "side": "S",
        "family": "vwap",
        "regime": "trend",
        "profile": "maker_both",
        "tp": 3.0,
        "sl": 1.5,
        "hold": 36,
    },
    {
        "id": "BTC_DONCHIAN_SHORT_ALL_MB_2_1_24",
        "symbol": "BTCUSDT",
        "sig": "donchian20_v0_short",
        "side": "S",
        "family": "donchian",
        "regime": "all",
        "profile": "maker_both",
        "tp": 2.0,
        "sl": 1.0,
        "hold": 24,
    },
]

PERIODS = [
    ("P1", 90, 60),
    ("P2", 60, 30),
    ("P3", 30, 0),
]

# ============================================================
# LOG
# ============================================================

def log(x):
    print(x, flush=True)


# ============================================================
# DATA
# ============================================================

def months(a, b):
    p = pd.Period(a, "M")
    q = pd.Period(b, "M")

    while p <= q:
        yield p
        p += 1


def read_zip(content):
    z = pd.read_csv(
        io.BytesIO(content),
        compression="zip"
    )

    if "open_time" not in z.columns:
        z = pd.read_csv(
            io.BytesIO(content),
            compression="zip",
            header=None
        ).iloc[:, :12]

        z.columns = COLS

    else:
        z = z.rename(
            columns={"open_time": "time"}
        ).iloc[:, :12]

        z.columns = COLS

    z["time"] = pd.to_numeric(
        z["time"],
        errors="coerce"
    )

    z = z.dropna(subset=["time"])

    z["time"] = pd.to_datetime(
        z["time"],
        unit="ms",
        utc=True
    )

    for c in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:
        z[c] = pd.to_numeric(
            z[c],
            errors="coerce"
        )

    return z.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    )


def get_file(url):
    try:
        r = requests.get(
            url,
            headers=UA,
            timeout=30
        )

        if r.status_code == 200:
            return read_zip(r.content)

    except Exception:
        pass

    return None


def fetch(symbol, interval, days):
    end = (
        pd.Timestamp.now(tz="UTC")
        .floor("h")
    )

    start = end - pd.Timedelta(
        days=days
    )

    base = (
        "https://data.binance.vision/"
        "data/futures/um"
    )

    rows = []

    for p in months(start, end):

        fn = (
            f"{symbol}-{interval}-"
            f"{p.year}-{p.month:02d}.zip"
        )

        url = (
            f"{base}/monthly/klines/"
            f"{symbol}/{interval}/{fn}"
        )

        z = get_file(url)

        if z is not None:
            rows.append(z)
            continue

        # Current month fallback
        if p == end.to_period("M"):

            d = p.start_time.tz_localize("UTC")

            while d <= end:

                fn = (
                    f"{symbol}-{interval}-"
                    f"{d:%Y-%m-%d}.zip"
                )

                url = (
                    f"{base}/daily/klines/"
                    f"{symbol}/{interval}/{fn}"
                )

                z = get_file(url)

                if z is not None:
                    rows.append(z)

                d += pd.Timedelta(days=1)

    if not rows:
        raise RuntimeError(
            f"No data for {symbol} {interval}"
        )

    z = pd.concat(
        rows,
        ignore_index=True
    )

    z = z[
        (z.time >= start) &
        (z.time <= end)
    ]

    z = (
        z.drop_duplicates("time")
         .sort_values("time")
         .reset_index(drop=True)
    )

    return z


# ============================================================
# INDICATEURS
# ============================================================

def atr(x, n=14):
    h = x.high
    l = x.low
    c = x.close

    tr = pd.concat(
        [
            h - l,
            (h - c.shift()).abs(),
            (l - c.shift()).abs(),
        ],
        axis=1
    ).max(axis=1)

    return tr.rolling(n).mean()


def features(x):
    x = x.copy()

    x["atr14"] = atr(x)

    x["ema20"] = x.close.ewm(
        span=20,
        adjust=False
    ).mean()

    x["ema50"] = x.close.ewm(
        span=50,
        adjust=False
    ).mean()

    x["ema200"] = x.close.ewm(
        span=200,
        adjust=False
    ).mean()

    d = x.close.diff()

    up = (
        d.clip(lower=0)
         .rolling(14)
         .mean()
    )

    dn = (
        -d.clip(upper=0)
    ).rolling(14).mean()

    x["rsi"] = (
        100 -
        100 /
        (
            1 +
            up /
            dn.replace(0, np.nan)
        )
    )

    x["vwap48"] = (
        (x.close * x.volume).rolling(48).sum()
        /
        x.volume.rolling(48).sum()
    )

    x["mean96"] = (
        x.close.rolling(96).mean()
    )

    x["z48"] = (
        (x.close - x.close.rolling(48).mean())
        /
        x.close.rolling(48).std()
    )

    x["z96"] = (
        (x.close - x.close.rolling(96).mean())
        /
        x.close.rolling(96).std()
    )

    x["dc20h"] = (
        x.high
        .rolling(20)
        .max()
        .shift(1)
    )

    x["dc50h"] = (
        x.high
        .rolling(50)
        .max()
        .shift(1)
    )

    x["dc20l"] = (
        x.low
        .rolling(20)
        .min()
        .shift(1)
    )

    x["dc50l"] = (
        x.low
        .rolling(50)
        .min()
        .shift(1)
    )

    return x


def context(x, h):
    h = h.copy()

    h["ema20_ctx"] = (
        h.close
        .ewm(span=20, adjust=False)
        .mean()
    )

    h["ema50_ctx"] = (
        h.close
        .ewm(span=50, adjust=False)
        .mean()
    )

    h["ema200_ctx"] = (
        h.close
        .ewm(span=200, adjust=False)
        .mean()
    )

    h["atr14_ctx"] = atr(h)

    h = h[
        [
            "time",
            "close",
            "ema20_ctx",
            "ema50_ctx",
            "ema200_ctx",
            "atr14_ctx",
        ]
    ]

    h = h.rename(
        columns={
            "close": "close_ctx"
        }
    )

    step = (
        h.time.diff()
        .mode()
        .iloc[0]
    )

    # Align closed 4h candle to subsequent 1h bars
    h["time"] += step

    return pd.merge_asof(
        x.sort_values("time"),
        h.sort_values("time"),
        on="time",
        direction="backward"
    )


# ============================================================
# SIGNALS
# ============================================================

def build_signals(x, h):
    x = context(
        features(x),
        h
    )

    x["trend"] = np.where(
        (
            (x.ema20_ctx > x.ema50_ctx) &
            (x.ema50_ctx > x.ema200_ctx)
        ),
        "trend",

        np.where(
            (
                (x.ema20_ctx < x.ema50_ctx) &
                (x.ema50_ctx < x.ema200_ctx)
            ),
            "down",
            "range"
        )
    )

    signals = {}

    def add(name, mask, side, family):
        y = x[
            [
                "time",
                "open",
                "high",
                "low",
                "close",
                "atr14",
                "trend",
            ]
        ].copy()

        y["sig"] = (
            mask.fillna(False)
                .to_numpy(bool)
        )

        y["side"] = side
        y["family"] = family

        signals[name] = y

    # --------------------------------------------------------
    # LONG
    # --------------------------------------------------------

    add(
        "vwap48_k2",
        x.close > x.vwap48 + 2 * x.atr14,
        "L",
        "vwap"
    )

    add(
        "mean96_k2",
        x.close > x.mean96 + 2 * x.atr14,
        "L",
        "mean"
    )

    add(
        "vwap48_k3",
        x.close > x.vwap48 + 3 * x.atr14,
        "L",
        "vwap"
    )

    add(
        "donchian20_v0",
        x.close > x.dc20h,
        "L",
        "donchian"
    )

    add(
        "donchian20_v1.5",
        x.close > x.dc20h + 1.5 * x.atr14,
        "L",
        "donchian"
    )

    add(
        "donchian50_v1.5",
        x.close > x.dc50h + 1.5 * x.atr14,
        "L",
        "donchian"
    )

    add(
        "zscore48_t2",
        x.z48 > 2,
        "L",
        "zscore"
    )

    add(
        "zscore96_t2.5",
        x.z96 > 2.5,
        "L",
        "zscore"
    )

    add(
        "pullbackRSI35",
        (
            (x.rsi < 35) &
            (x.close > x.ema50)
        ),
        "L",
        "rsi"
    )

    add(
        "pullbackRSI40",
        (
            (x.rsi < 40) &
            (x.close > x.ema50)
        ),
        "L",
        "rsi"
    )

    # --------------------------------------------------------
    # SHORT
    # --------------------------------------------------------

    add(
        "vwap48_k2_short",
        x.close < x.vwap48 - 2 * x.atr14,
        "S",
        "vwap"
    )

    add(
        "mean96_k2_short",
        x.close < x.mean96 - 2 * x.atr14,
        "S",
        "mean"
    )

    add(
        "vwap48_k3_short",
        x.close < x.vwap48 - 3 * x.atr14,
        "S",
        "vwap"
    )

    add(
        "donchian20_v0_short",
        x.close < x.dc20l,
        "S",
        "donchian"
    )

    add(
        "donchian20_v1.5_short",
        x.close < x.dc20l - 1.5 * x.atr14,
        "S",
        "donchian"
    )

    add(
        "donchian50_v1.5_short",
        x.close < x.dc50l - 1.5 * x.atr14,
        "S",
        "donchian"
    )

    add(
        "zscore48_t2_short",
        x.z48 < -2,
        "S",
        "zscore"
    )

    add(
        "zscore96_t2.5_short",
        x.z96 < -2.5,
        "S",
        "zscore"
    )

    add(
        "pullbackRSI35_short",
        (
            (x.rsi > 65) &
            (x.close < x.ema50)
        ),
        "S",
        "rsi"
    )

    add(
        "pullbackRSI40_short",
        (
            (x.rsi > 60) &
            (x.close < x.ema50)
        ),
        "S",
        "rsi"
    )

    return signals


# ============================================================
# SIMULATION
# ============================================================

def simulate(
    d,
    symbol,
    side,
    profile,
    tp,
    sl,
    hold
):
    """
    Trade begins on candle i+1 after signal candle i.

    Taker:
      entry taker
      TP taker
      SL taker
      TIME taker

    Maker_both:
      entry maker
      TP maker
      SL taker
      TIME taker

    Maker_tp:
      entry maker
      TP maker
      SL taker
      TIME taker

    Maker entry is simplified:
      LONG: next candle low <= signal close
      SHORT: next candle high >= signal close
    """

    if d.empty:
        return pd.DataFrame()

    o = d.open.to_numpy(float)
    hi = d.high.to_numpy(float)
    lo = d.low.to_numpy(float)
    cl = d.close.to_numpy(float)
    atrv = d.atr14.to_numpy(float)
    sig = d.sig.to_numpy(bool)

    n = len(d)

    rows = []

    i = 0

    while i < n - 1:

        if not sig[i]:
            i += 1
            continue

        entry_ref = cl[i]

        # ----------------------------------------------------
        # Entry
        # ----------------------------------------------------

        entry_i = i + 1

        if entry_i >= n:
            break

        if profile in ("maker_both", "maker_tp"):

            if side == "L":

                if lo[entry_i] > entry_ref:
                    i += 1
                    continue

            else:

                if hi[entry_i] < entry_ref:
                    i += 1
                    continue

            entry = entry_ref

        else:
            entry = o[entry_i]

        # Slippage on entry
        if side == "L":
            entry *= 1 + SLIP[symbol]
        else:
            entry *= 1 - SLIP[symbol]

        entry_fee = (
            FM
            if profile in ("maker_both", "maker_tp")
            else FT
        )

        # ----------------------------------------------------
        # Targets
        # ----------------------------------------------------

        if side == "L":

            tp_price = (
                entry *
                (1 + tp / 100)
            )

            sl_price = (
                entry *
                (1 - sl / 100)
            )

        else:

            tp_price = (
                entry *
                (1 - tp / 100)
            )

            sl_price = (
                entry *
                (1 + sl / 100)
            )

        end = min(
            entry_i + hold,
            n - 1
        )

        exit_i = end
        reason = "TIME"
        exit_price = cl[end]

        for j in range(entry_i, end + 1):

            if side == "L":

                hit_sl = lo[j] <= sl_price
                hit_tp = hi[j] >= tp_price

            else:

                hit_sl = hi[j] >= sl_price
                hit_tp = lo[j] <= tp_price

            # Conservative same-candle rule:
            # SL before TP.
            if hit_sl:
                exit_i = j
                exit_price = sl_price
                reason = "SL"
                break

            if hit_tp:
                exit_i = j
                exit_price = tp_price
                reason = "TP"
                break

        # ----------------------------------------------------
        # Exit fee
        # ----------------------------------------------------

        if reason == "TP":
            exit_fee = (
                FM
                if profile in ("maker_both", "maker_tp")
                else FT
            )
        else:
            exit_fee = FT

        # Exit slippage
        if reason == "TIME":
            if side == "L":
                exit_price *= 1 - SLIP[symbol]
            else:
                exit_price *= 1 + SLIP[symbol]

        elif reason == "SL":
            if side == "L":
                exit_price *= 1 - SLIP[symbol]
            else:
                exit_price *= 1 + SLIP[symbol]

        elif reason == "TP":
            if side == "L":
                exit_price *= 1 - SLIP[symbol]
            else:
                exit_price *= 1 + SLIP[symbol]

        # ----------------------------------------------------
        # Gross / net return
        # ----------------------------------------------------

        if side == "L":
            gross = (
                exit_price / entry - 1
            )
        else:
            gross = (
                entry / exit_price - 1
            )

        net = (
            gross -
            entry_fee -
            exit_fee
        )

        rows.append(
            {
                "entry_time": d.time.iloc[entry_i],
                "exit_time": d.time.iloc[exit_i],
                "side": side,
                "entry": entry,
                "exit": exit_price,
                "reason": reason,
                "ret": net * 100,
            }
        )

        # No overlapping trades
        i = exit_i + 1

    return pd.DataFrame(rows)


# ============================================================
# STATISTICS
# ============================================================

def max_drawdown(returns):
    if len(returns) == 0:
        return 0.0

    eq = np.cumprod(
        1 + returns / 100
    )

    peak = np.maximum.accumulate(eq)

    dd = (
        eq / peak - 1
    ) * 100

    return float(dd.min())


def profit_factor(returns):
    if len(returns) == 0:
        return np.nan

    pos = returns[returns > 0].sum()
    neg = -returns[returns < 0].sum()

    if neg <= 0:
        return np.inf if pos > 0 else 0.0

    return float(pos / neg)


def metrics(trades):
    if trades.empty:
        return {
            "trades": 0,
            "ret": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "pf": np.nan,
            "dd": 0.0,
            "winrate": 0.0,
            "edge": 0.0,
            "tp": 0,
            "sl": 0,
            "time": 0,
        }

    r = trades.ret.to_numpy(float)

    return {
        "trades": len(r),
        "ret": float(
            (np.prod(1 + r / 100) - 1) * 100
        ),
        "mean": float(np.mean(r)),
        "median": float(np.median(r)),
        "pf": profit_factor(r),
        "dd": max_drawdown(r),
        "winrate": float(
            np.mean(r > 0) * 100
        ),
        "edge": float(np.mean(r)),
        "tp": int(
            (trades.reason == "TP").sum()
        ),
        "sl": int(
            (trades.reason == "SL").sum()
        ),
        "time": int(
            (trades.reason == "TIME").sum()
        ),
    }


def random_benchmark(trades, seed=12345):
    """
    Random-direction sanity benchmark.

    Trade timing is preserved.
    Direction is randomized.
    Magnitude uses the absolute observed return.

    This is a sanity benchmark, not a formal statistical test.
    """

    if trades.empty:
        return {
            "rand_ret": 0.0,
            "rand_pf": np.nan,
            "rand_edge": 0.0,
        }

    rng = np.random.default_rng(seed)

    r = trades.ret.to_numpy(float)

    random_sign = rng.choice(
        [-1.0, 1.0],
        size=len(r)
    )

    rr = (
        np.abs(r) *
        random_sign
    )

    return {
        "rand_ret": float(
            (np.prod(1 + rr / 100) - 1) * 100
        ),
        "rand_pf": profit_factor(rr),
        "rand_edge": float(
            np.mean(rr)
        ),
    }


# ============================================================
# ONE CANDIDATE
# ============================================================

def evaluate_candidate(
    candidate,
    signals,
    period_name,
    start,
    end
):
    sig_name = candidate["sig"]

    if sig_name not in signals:
        raise RuntimeError(
            f"Missing signal {sig_name}"
        )

    d = signals[sig_name].copy()

    d = d[
        (d.time >= start) &
        (d.time < end)
    ].reset_index(drop=True)

    # Regime filtering
    if candidate["regime"] == "trend":

        d = d[
            d.trend.isin(
                ["trend", "down"]
            )
        ].reset_index(drop=True)

    trades = simulate(
        d,
        candidate["symbol"],
        candidate["side"],
        candidate["profile"],
        candidate["tp"],
        candidate["sl"],
        candidate["hold"]
    )

    m = metrics(trades)

    rb = random_benchmark(
        trades
    )

    out = {
        "id": candidate["id"],
        "symbol": candidate["symbol"],
        "sig": candidate["sig"],
        "side": candidate["side"],
        "family": candidate["family"],
        "regime": candidate["regime"],
        "profile": candidate["profile"],
        "tp": candidate["tp"],
        "sl": candidate["sl"],
        "hold": candidate["hold"],
        "period": period_name,
        "start": start,
        "end": end,
        **m,
        **rb,
    }

    return out, trades


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--days",
        type=int,
        default=730
    )

    parser.add_argument(
        "--interval",
        default="1h"
    )

    args = parser.parse_args()

    log(
        "V436 | FIXED CANDIDATES | "
        f"VALIDATION={VALIDATION_DAYS}d"
    )

    # --------------------------------------------------------
    # Determine common current period
    # --------------------------------------------------------

    end = (
        pd.Timestamp.now(tz="UTC")
        .floor("h")
    )

    validation_start = (
        end -
        pd.Timedelta(days=VALIDATION_DAYS)
    )

    # --------------------------------------------------------
    # Data cache
    # --------------------------------------------------------

    symbols = sorted(
        set(c["symbol"] for c in CANDIDATES)
    )

    cache = {}

    for symbol in symbols:

        log(
            f"DATA {symbol} "
            f"{args.interval}"
        )

        x = fetch(
            symbol,
            args.interval,
            args.days
        )

        # 4h context
        h = fetch(
            symbol,
            "4h",
            args.days + 10
        )

        cache[symbol] = (
            x,
            h
        )

        log(
            f"DATA {symbol}: "
            f"{len(x)} 1h | "
            f"{len(h)} 4h"
        )

    # --------------------------------------------------------
    # Build signals
    # --------------------------------------------------------

    signal_cache = {}

    for symbol in symbols:

        x, h = cache[symbol]

        log(
            f"SIGNALS {symbol}"
        )

        signal_cache[symbol] = (
            build_signals(x, h)
        )

    # --------------------------------------------------------
    # Evaluate all 8 candidates
    # --------------------------------------------------------

    rows = []
    trade_rows = []

    for n, candidate in enumerate(
        CANDIDATES,
        1
    ):

        symbol = candidate["symbol"]

        log(
            f"[{n}/{len(CANDIDATES)}] "
            f"{candidate['id']}"
        )

        signals = signal_cache[symbol]

        # ----------------------------------------------------
        # P1/P2/P3
        # ----------------------------------------------------

        for pname, before, after in PERIODS:

            start = (
                end -
                pd.Timedelta(days=before)
            )

            period_end = (
                end -
                pd.Timedelta(days=after)
            )

            result, trades = (
                evaluate_candidate(
                    candidate,
                    signals,
                    pname,
                    start,
                    period_end
                )
            )

            rows.append(result)

            if not trades.empty:
                for _, t in trades.iterrows():

                    trade_rows.append(
                        {
                            "id": candidate["id"],
                            "period": pname,
                            **t.to_dict(),
                        }
                    )

        # ----------------------------------------------------
        # Full 90-day validation
        # ----------------------------------------------------

        result, trades = (
            evaluate_candidate(
                candidate,
                signals,
                "FULL90",
                validation_start,
                end
            )
        )

        rows.append(result)

        if not trades.empty:

            for _, t in trades.iterrows():

                trade_rows.append(
                    {
                        "id": candidate["id"],
                        "period": "FULL90",
                        **t.to_dict(),
                    }
                )

    # ========================================================
    # OUTPUT
    # ========================================================

    result_df = pd.DataFrame(rows)

    trades_df = pd.DataFrame(
        trade_rows
    )

    # --------------------------------------------------------
    # Compact summary
    # --------------------------------------------------------

    full = result_df[
        result_df.period == "FULL90"
    ].copy()

    full = full.sort_values(
        ["symbol", "id"]
    )

    summary_cols = [
        "id",
        "symbol",
        "sig",
        "side",
        "regime",
        "profile",
        "tp",
        "sl",
        "hold",
        "trades",
        "ret",
        "mean",
        "median",
        "pf",
        "dd",
        "winrate",
        "edge",
        "tp",
        "sl",
        "time",
        "rand_ret",
        "rand_pf",
        "rand_edge",
    ]

    full[
        summary_cols
    ].to_csv(
        OUT / "validation_v436.csv",
        index=False
    )

    result_df.to_csv(
        OUT / "validation_periods_v436.csv",
        index=False
    )

    if not trades_df.empty:
        trades_df.to_csv(
            OUT / "validation_trades_v436.csv",
            index=False
        )

    # --------------------------------------------------------
    # Monthly breakdown
    # --------------------------------------------------------

    monthly_rows = []

    if not trades_df.empty:

        t = trades_df.copy()

        t["month"] = pd.to_datetime(
            t.entry_time,
            utc=True
        ).dt.strftime("%Y-%m")

        for (cid, month), g in t.groupby(
            ["id", "month"]
        ):

            r = g.ret.to_numpy(float)

            monthly_rows.append(
                {
                    "id": cid,
                    "month": month,
                    "trades": len(r),
                    "ret": float(
                        (np.prod(
                            1 + r / 100
                        ) - 1) * 100
                    ),
                    "mean": float(
                        np.mean(r)
                    ),
                    "pf": profit_factor(r),
                    "dd": max_drawdown(r),
                }
            )

    monthly_df = pd.DataFrame(
        monthly_rows
    )

    if not monthly_df.empty:

        monthly_df.to_csv(
            OUT / "validation_monthly_v436.csv",
            index=False
        )

    # --------------------------------------------------------
    # Markdown summary
    # --------------------------------------------------------

    lines = []

    lines.append(
        "# SCALP LAB V4.3.6"
    )

    lines.append("")
    lines.append(
        "Fixed-candidate out-of-sample validation."
    )

    lines.append("")
    lines.append(
        f"- Validation: {validation_start} → {end}"
    )

    lines.append(
        f"- Candidates: {len(CANDIDATES)}"
    )

    lines.append(
        "- Selection performed before validation: YES"
    )

    lines.append(
        "- Validation used for selection: NO"
    )

    lines.append("")

    lines.append(
        "| Candidate | Trades | Return | PF | DD | Win% | Edge | Random PF |"
    )

    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )

    for _, r in full.iterrows():

        pf = (
            f"{r.pf:.3f}"
            if pd.notna(r.pf)
            else "NA"
        )

        rpf = (
            f"{r.rand_pf:.3f}"
            if pd.notna(r.rand_pf)
            else "NA"
        )

        lines.append(
            f"| {r.id} | "
            f"{int(r.trades)} | "
            f"{r.ret:.2f}% | "
            f"{pf} | "
            f"{r.dd:.2f}% | "
            f"{r.winrate:.1f}% | "
            f"{r.edge:.4f}% | "
            f"{rpf} |"
        )

    lines.append("")
    lines.append(
        "## Period breakdown"
    )

    lines.append("")

    lines.append(
        "| Candidate | Period | Trades | Return | PF | DD |"
    )

    lines.append(
        "|---|---|---:|---:|---:|---:|"
    )

    for _, r in result_df.iterrows():

        pf = (
            f"{r.pf:.3f}"
            if pd.notna(r.pf)
            else "NA"
        )

        lines.append(
            f"| {r.id} | "
            f"{r.period} | "
            f"{int(r.trades)} | "
            f"{r.ret:.2f}% | "
            f"{pf} | "
            f"{r.dd:.2f}% |"
        )

    (OUT / "summary_v436.md").write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Compact GitHub log
    # --------------------------------------------------------

    log("")
    log(
        "RESULTS | "
        f"candidates={len(CANDIDATES)} "
        f"rows={len(result_df)} "
        f"errors=0"
    )

    for _, r in full.iterrows():

        log(
            f"{r.id} | "
            f"T={int(r.trades)} | "
            f"RET={r.ret:+.2f}% | "
            f"PF={r.pf:.3f} | "
            f"DD={r.dd:.2f}%"
        )

    log("")
    log("DONE V436")


if __name__ == "__main__":
    main()
