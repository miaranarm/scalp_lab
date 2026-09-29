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
# V4.3.7
#
# OBJECTIF
# --------
# Stress-test du seul candidat positif de la validation
# indépendante V4.3.6.
#
# CANDIDAT DE RÉFÉRENCE :
# SOLUSDT
# Donchian20 LONG
# regime = all
# maker_both
# TP 3%
# SL 1.5%
# HOLD 36h
#
# IMPORTANT :
# - aucune sélection de signal ici
# - aucune sélection de variante ici
# - les variantes servent uniquement à mesurer la sensibilité
# - le candidat original reste la référence
# ============================================================

BASE_SYMBOL = "SOLUSDT"

BASE_SIGNAL = "donchian20_v0"
BASE_SIDE = "L"
BASE_FAMILY = "donchian"
BASE_REGIME = "all"

BASE_TP = 3.0
BASE_SL = 1.5
BASE_HOLD = 36

VALIDATION_DAYS = 90

# Frais de référence
FT = 0.0005       # taker = 0.05%
FM = 0.0002       # maker = 0.02%

# Slippage de référence
BASE_SLIP = {
    "SOLUSDT": 0.00030,
}

UA = {"User-Agent": "Mozilla/5.0"}

COLS = [
    "time", "open", "high", "low", "close", "volume",
    "ct", "qv", "trades", "tbv", "tqv", "x"
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

    z = z.dropna(
        subset=["time"]
    )

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
        "volume",
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
            "close",
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

    start = (
        end -
        pd.Timedelta(days=days)
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
# SIGNAL
# ============================================================

def build_signal(x, h):
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
        (
            y.close >
            x.dc20h
        )
        .fillna(False)
        .to_numpy(bool)
    )

    return y


# ============================================================
# EXECUTION PROFILES
# ============================================================

EXECUTION_PROFILES = {
    # Référence V4.3.6
    "BASE_MB": {
        "entry": "maker",
        "tp": "maker",
        "sl": "taker",
        "time": "taker",
    },

    # Même stratégie mais entrée immédiatement exécutée
    # comme un ordre taker.
    "TAKER_ENTRY": {
        "entry": "taker",
        "tp": "maker",
        "sl": "taker",
        "time": "taker",
    },

    # Stress d'exécution plus conservateur :
    # entrée + TP + SL + TIME taker.
    "ALL_TAKER": {
        "entry": "taker",
        "tp": "taker",
        "sl": "taker",
        "time": "taker",
    },
}


# ============================================================
# SIMULATION
# ============================================================

def simulate(
    d,
    symbol,
    side,
    execution,
    tp,
    sl,
    hold,
    slip_multiplier=1.0,
    fee_multiplier=1.0,
):
    """
    Trade starts on candle i+1 after signal candle i.

    Execution modes:
      BASE_MB
        entry maker
        TP maker
        SL taker
        TIME taker

      TAKER_ENTRY
        entry taker
        TP maker
        SL taker
        TIME taker

      ALL_TAKER
        entry taker
        TP taker
        SL taker
        TIME taker

    Maker entry:
      LONG  -> next candle low <= signal close
      SHORT -> next candle high >= signal close

    Slippage and fees are stress multipliers.
    """

    if d.empty:
        return pd.DataFrame()

    if execution not in EXECUTION_PROFILES:
        raise ValueError(
            f"Unknown execution profile: {execution}"
        )

    profile = EXECUTION_PROFILES[execution]

    o = d.open.to_numpy(float)
    hi = d.high.to_numpy(float)
    lo = d.low.to_numpy(float)
    cl = d.close.to_numpy(float)
    sig = d.sig.to_numpy(bool)

    n = len(d)

    slip = (
        BASE_SLIP[symbol] *
        slip_multiplier
    )

    rows = []

    i = 0

    while i < n - 1:

        if not sig[i]:
            i += 1
            continue

        signal_close = cl[i]

        entry_i = i + 1

        if entry_i >= n:
            break

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        if profile["entry"] == "maker":

            if side == "L":

                if lo[entry_i] > signal_close:
                    i += 1
                    continue

            else:

                if hi[entry_i] < signal_close:
                    i += 1
                    continue

            entry = signal_close

        else:
            entry = o[entry_i]

        entry_fee_rate = (
            FM
            if profile["entry"] == "maker"
            else FT
        )

        # Entry slippage
        if side == "L":
            entry *= 1 + slip
        else:
            entry *= 1 - slip

        # Fee stress
        entry_fee = (
            entry_fee_rate *
            fee_multiplier
        )

        # ----------------------------------------------------
        # TARGETS
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

        for j in range(
            entry_i,
            end + 1
        ):

            if side == "L":

                hit_sl = (
                    lo[j] <= sl_price
                )

                hit_tp = (
                    hi[j] >= tp_price
                )

            else:

                hit_sl = (
                    hi[j] >= sl_price
                )

                hit_tp = (
                    lo[j] <= tp_price
                )

            # Conservative same-candle rule
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
        # EXIT FEE
        # ----------------------------------------------------

        exit_fee_rate = (
            FM
            if (
                reason == "TP" and
                profile["tp"] == "maker"
            )
            else FT
        )

        exit_fee = (
            exit_fee_rate *
            fee_multiplier
        )

        # ----------------------------------------------------
        # EXIT SLIPPAGE
        # ----------------------------------------------------

        # TP maker : pas de slippage de sortie.
        # TP taker : slippage défavorable.
        #
        # SL et TIME : taker => slippage défavorable.

        if reason == "TP":

            if profile["tp"] == "taker":

                if side == "L":
                    exit_price *= 1 - slip
                else:
                    exit_price *= 1 + slip

        else:

            if side == "L":
                exit_price *= 1 - slip
            else:
                exit_price *= 1 + slip

        # ----------------------------------------------------
        # RETURN
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

        # Pas de trades simultanés
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

    pos = returns[
        returns > 0
    ].sum()

    neg = -returns[
        returns < 0
    ].sum()

    if neg <= 0:
        return (
            np.inf
            if pos > 0
            else 0.0
        )

    return float(
        pos / neg
    )


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
            "tp_count": 0,
            "sl_count": 0,
            "time_count": 0,
        }

    r = trades.ret.to_numpy(float)

    return {
        "trades": len(r),

        "ret": float(
            (
                np.prod(
                    1 + r / 100
                ) - 1
            ) * 100
        ),

        "mean": float(
            np.mean(r)
        ),

        "median": float(
            np.median(r)
        ),

        "pf": profit_factor(r),

        "dd": max_drawdown(r),

        "winrate": float(
            np.mean(r > 0) * 100
        ),

        "edge": float(
            np.mean(r)
        ),

        "tp_count": int(
            (
                trades.reason == "TP"
            ).sum()
        ),

        "sl_count": int(
            (
                trades.reason == "SL"
            ).sum()
        ),

        "time_count": int(
            (
                trades.reason == "TIME"
            ).sum()
        ),
    }


# ============================================================
# EVALUATION
# ============================================================

def evaluate(
    signals,
    start,
    end,
    execution,
    tp,
    sl,
    hold,
    slip_multiplier=1.0,
    fee_multiplier=1.0,
):
    d = signals.copy()

    d = d[
        (d.time >= start) &
        (d.time < end)
    ].reset_index(drop=True)

    trades = simulate(
        d=d,
        symbol=BASE_SYMBOL,
        side=BASE_SIDE,
        execution=execution,
        tp=tp,
        sl=sl,
        hold=hold,
        slip_multiplier=slip_multiplier,
        fee_multiplier=fee_multiplier,
    )

    return metrics(trades), trades


# ============================================================
# PERIODS
# ============================================================

PERIODS = [
    ("P1", 90, 60),
    ("P2", 60, 30),
    ("P3", 30, 0),
]


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
        "V437 | SOL DONCHIAN LONG | "
        "EXECUTION + COST + PARAMETER STRESS"
    )

    log(
        "REFERENCE | "
        "SOLUSDT | donchian20_v0 | LONG | "
        "all | maker_both | "
        "TP=3 | SL=1.5 | HOLD=36"
    )

    # --------------------------------------------------------
    # Common period
    # --------------------------------------------------------

    end = (
        pd.Timestamp.now(tz="UTC")
        .floor("h")
    )

    validation_start = (
        end -
        pd.Timedelta(
            days=VALIDATION_DAYS
        )
    )

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    log("DATA SOLUSDT 1h")

    x = fetch(
        BASE_SYMBOL,
        args.interval,
        args.days
    )

    log(
        f"DATA SOLUSDT: "
        f"{len(x)} 1h"
    )

    log("DATA SOLUSDT 4h")

    h = fetch(
        BASE_SYMBOL,
        "4h",
        args.days + 10
    )

    log(
        f"DATA SOLUSDT: "
        f"{len(h)} 4h"
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    log(
        "SIGNALS SOLUSDT"
    )

    signals = build_signal(
        x,
        h
    )

    # ========================================================
    # A — EXECUTION STRESS
    # ========================================================

    log("")
    log(
        "SECTION A | EXECUTION / "
        "SLIPPAGE / FEES"
    )

    execution_rows = []
    execution_trade_rows = []

    slip_multipliers = [
        1.0,
        1.5,
        2.0,
        3.0,
    ]

    fee_multipliers = [
        1.0,
        1.25,
        1.5,
        2.0,
    ]

    for execution in [
        "BASE_MB",
        "TAKER_ENTRY",
        "ALL_TAKER",
    ]:

        for slip_mult in slip_multipliers:

            for fee_mult in fee_multipliers:

                label = (
                    f"{execution}_"
                    f"S{slip_mult:g}_"
                    f"F{fee_mult:g}"
                )

                m, trades = evaluate(
                    signals,
                    validation_start,
                    end,
                    execution,
                    BASE_TP,
                    BASE_SL,
                    BASE_HOLD,
                    slip_mult,
                    fee_mult,
                )

                row = {
                    "section": "EXECUTION",
                    "scenario": label,
                    "execution": execution,
                    "tp": BASE_TP,
                    "sl": BASE_SL,
                    "hold": BASE_HOLD,
                    "slip_multiplier": slip_mult,
                    "fee_multiplier": fee_mult,
                    **m,
                }

                execution_rows.append(
                    row
                )

                if not trades.empty:

                    for _, t in trades.iterrows():

                        execution_trade_rows.append(
                            {
                                "scenario": label,
                                "execution": execution,
                                "slip_multiplier": slip_mult,
                                "fee_multiplier": fee_mult,
                                **t.to_dict(),
                            }
                        )

                log(
                    f"EXEC | {label} | "
                    f"T={m['trades']} | "
                    f"RET={m['ret']:+.2f}% | "
                    f"PF={m['pf']:.3f} | "
                    f"DD={m['dd']:.2f}%"
                )

    execution_df = pd.DataFrame(
        execution_rows
    )

    execution_df.to_csv(
        OUT /
        "execution_stress_v437.csv",
        index=False
    )

    if execution_trade_rows:

        pd.DataFrame(
            execution_trade_rows
        ).to_csv(
            OUT /
            "execution_trades_v437.csv",
            index=False
        )

    # ========================================================
    # B — PARAMETER SENSITIVITY
    # ========================================================

    log("")
    log(
        "SECTION B | PARAMETER SENSITIVITY"
    )

    # IMPORTANT :
    # These are not new validated candidates.
    # They are sensitivity tests around the fixed reference.

    parameter_variants = [
        (
            "REF_3_1.5_36",
            3.0,
            1.5,
            36,
        ),

        # TP sensitivity
        (
            "TP_2.5_SL_1.5_H36",
            2.5,
            1.5,
            36,
        ),

        (
            "TP_3.5_SL_1.5_H36",
            3.5,
            1.5,
            36,
        ),

        # SL sensitivity
        (
            "TP_3_SL_1.25_H36",
            3.0,
            1.25,
            36,
        ),

        (
            "TP_3_SL_1.75_H36",
            3.0,
            1.75,
            36,
        ),

        # HOLD sensitivity
        (
            "TP_3_SL_1.5_H24",
            3.0,
            1.5,
            24,
        ),

        (
            "TP_3_SL_1.5_H48",
            3.0,
            1.5,
            48,
        ),

        # Combined nearby variants
        (
            "TP_2.5_SL_1.25_H36",
            2.5,
            1.25,
            36,
        ),

        (
            "TP_3.5_SL_1.75_H36",
            3.5,
            1.75,
            36,
        ),
    ]

    parameter_rows = []
    parameter_trade_rows = []

    for (
        label,
        tp,
        sl,
        hold,
    ) in parameter_variants:

        m, trades = evaluate(
            signals,
            validation_start,
            end,
            "BASE_MB",
            tp,
            sl,
            hold,
            1.0,
            1.0,
        )

        row = {
            "section": "PARAMETER",
            "scenario": label,
            "execution": "BASE_MB",
            "tp": tp,
            "sl": sl,
            "hold": hold,
            "slip_multiplier": 1.0,
            "fee_multiplier": 1.0,
            **m,
        }

        parameter_rows.append(
            row
        )

        if not trades.empty:

            for _, t in trades.iterrows():

                parameter_trade_rows.append(
                    {
                        "scenario": label,
                        "execution": "BASE_MB",
                        **t.to_dict(),
                    }
                )

        log(
            f"PARAM | {label} | "
            f"T={m['trades']} | "
            f"RET={m['ret']:+.2f}% | "
            f"PF={m['pf']:.3f} | "
            f"DD={m['dd']:.2f}%"
        )

    parameter_df = pd.DataFrame(
        parameter_rows
    )

    parameter_df.to_csv(
        OUT /
        "parameter_sensitivity_v437.csv",
        index=False
    )

    if parameter_trade_rows:

        pd.DataFrame(
            parameter_trade_rows
        ).to_csv(
            OUT /
            "parameter_trades_v437.csv",
            index=False
        )

    # ========================================================
    # C — PERIOD BREAKDOWN OF REFERENCE
    # ========================================================

    log("")
    log(
        "SECTION C | REFERENCE PERIOD BREAKDOWN"
    )

    period_rows = []
    period_trade_rows = []

    for pname, before, after in PERIODS:

        start = (
            end -
            pd.Timedelta(
                days=before
            )
        )

        period_end = (
            end -
            pd.Timedelta(
                days=after
            )
        )

        m, trades = evaluate(
            signals,
            start,
            period_end,
            "BASE_MB",
            BASE_TP,
            BASE_SL,
            BASE_HOLD,
            1.0,
            1.0,
        )

        period_rows.append(
            {
                "period": pname,
                "start": start,
                "end": period_end,
                **m,
            }
        )

        if not trades.empty:

            for _, t in trades.iterrows():

                period_trade_rows.append(
                    {
                        "period": pname,
                        **t.to_dict(),
                    }
                )

        log(
            f"PERIOD | {pname} | "
            f"T={m['trades']} | "
            f"RET={m['ret']:+.2f}% | "
            f"PF={m['pf']:.3f} | "
            f"DD={m['dd']:.2f}%"
        )

    period_df = pd.DataFrame(
        period_rows
    )

    period_df.to_csv(
        OUT /
        "reference_periods_v437.csv",
        index=False
    )

    if period_trade_rows:

        pd.DataFrame(
            period_trade_rows
        ).to_csv(
            OUT /
            "reference_trades_v437.csv",
            index=False
        )

    # ========================================================
    # D — COMPACT REFERENCE RESULT
    # ========================================================

    ref = execution_df[
        (
            execution_df.execution ==
            "BASE_MB"
        ) &
        (
            execution_df.slip_multiplier ==
            1.0
        ) &
        (
            execution_df.fee_multiplier ==
            1.0
        )
    ].iloc[0]

    # ========================================================
    # MARKDOWN SUMMARY
    # ========================================================

    lines = []

    lines.append(
        "# SCALP LAB V4.3.7"
    )

    lines.append("")
    lines.append(
        "Execution and parameter stress-test "
        "of the fixed V4.3.6 candidate."
    )

    lines.append("")

    lines.append(
        f"- Validation window: "
        f"{validation_start} → {end}"
    )

    lines.append(
        "- Candidate: SOLUSDT / "
        "donchian20_v0 / LONG / all"
    )

    lines.append(
        "- Reference: maker entry + maker TP "
        "+ taker SL/TIME"
    )

    lines.append(
        "- TP=3% / SL=1.5% / HOLD=36h"
    )

    lines.append("")

    lines.append(
        "## Reference result"
    )

    lines.append("")

    lines.append(
        f"- Trades: {int(ref.trades)}"
    )

    lines.append(
        f"- Return: {ref.ret:+.2f}%"
    )

    lines.append(
        f"- PF: {ref.pf:.3f}"
    )

    lines.append(
        f"- DD: {ref.dd:.2f}%"
    )

    lines.append(
        f"- Win rate: {ref.winrate:.1f}%"
    )

    lines.append(
        f"- Edge: {ref.edge:+.4f}%"
    )

    lines.append("")

    # --------------------------------------------------------
    # Execution summary
    # --------------------------------------------------------

    lines.append(
        "## Execution stress"
    )

    lines.append("")

    lines.append(
        "| Execution | Slip | Fee | "
        "Trades | Return | PF | DD |"
    )

    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|"
    )

    # Show only 1x fees in markdown compactly,
    # while complete matrix remains in CSV.
    compact_exec = execution_df[
        execution_df.fee_multiplier == 1.0
    ].copy()

    for _, r in compact_exec.iterrows():

        lines.append(
            f"| {r.execution} | "
            f"{r.slip_multiplier:.1f}x | "
            f"{r.fee_multiplier:.2f}x | "
            f"{int(r.trades)} | "
            f"{r.ret:+.2f}% | "
            f"{r.pf:.3f} | "
            f"{r.dd:.2f}% |"
        )

    lines.append("")

    lines.append(
        "Complete 3 × 4 × 4 execution matrix: "
        "`execution_stress_v437.csv`"
    )

    lines.append("")

    # --------------------------------------------------------
    # Parameter summary
    # --------------------------------------------------------

    lines.append(
        "## Parameter sensitivity"
    )

    lines.append("")

    lines.append(
        "| Scenario | TP | SL | Hold | "
        "Trades | Return | PF | DD |"
    )

    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )

    for _, r in parameter_df.iterrows():

        lines.append(
            f"| {r.scenario} | "
            f"{r.tp:g}% | "
            f"{r.sl:g}% | "
            f"{int(r.hold)}h | "
            f"{int(r.trades)} | "
            f"{r.ret:+.2f}% | "
            f"{r.pf:.3f} | "
            f"{r.dd:.2f}% |"
        )

    lines.append("")

    lines.append(
        "## Reference period breakdown"
    )

    lines.append("")

    lines.append(
        "| Period | Trades | Return | PF | DD |"
    )

    lines.append(
        "|---|---:|---:|---:|---:|"
    )

    for _, r in period_df.iterrows():

        lines.append(
            f"| {r.period} | "
            f"{int(r.trades)} | "
            f"{r.ret:+.2f}% | "
            f"{r.pf:.3f} | "
            f"{r.dd:.2f}% |"
        )

    lines.append("")

    lines.append(
        "## Methodology note"
    )

    lines.append("")

    lines.append(
        "V4.3.7 does not perform candidate selection."
    )

    lines.append(
        "The SOL Donchian LONG candidate was fixed "
        "before this stress test."
    )

    lines.append(
        "Execution and parameter variants are "
        "sensitivity diagnostics, not new independent "
        "validation results."
    )

    lines.append(
        "The maker-entry model remains simplified and "
        "does not model real queue position or partial fills."
    )

    (OUT / "summary_v437.md").write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    # ========================================================
    # FINAL GITHUB LOG
    # ========================================================

    log("")
    log(
        "REFERENCE | "
        f"T={int(ref.trades)} | "
        f"RET={ref.ret:+.2f}% | "
        f"PF={ref.pf:.3f} | "
        f"DD={ref.dd:.2f}%"
    )

    log("")
    log(
        "ARTIFACTS | "
        "execution_stress_v437.csv | "
        "parameter_sensitivity_v437.csv | "
        "reference_periods_v437.csv | "
        "summary_v437.md"
    )

    log("")
    log("DONE V437")


if __name__ == "__main__":
    main()
