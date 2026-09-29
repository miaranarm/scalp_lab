from __future__ import annotations

import argparse
import io
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ============================================================
# V4.3.8 — FORWARD PAPER TRADING
# SOLUSDT / DONCHIAN20 / LONG
# TP 3% / SL 1.5% / HOLD 36h
# ALL_TAKER / PAPER ONLY
# ============================================================

SYMBOL = "SOLUSDT"
TP = 3.0
SL = 1.5
HOLD = 36

CAPITAL = 10000.0
FEE = 0.0005
SLIP = 0.00030

STATE = Path("state/paper_v438.json")
OUT = Path("results")

STATE.parent.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0"}

COLS = [
    "time", "open", "high", "low", "close",
    "volume", "ct", "qv", "trades",
    "tbv", "tqv", "x"
]


def log(x):
    print(x, flush=True)


# ============================================================
# DATA
# ============================================================

def read_zip(b):
    z = pd.read_csv(
        io.BytesIO(b),
        compression="zip"
    )

    if "open_time" in z.columns:
        z = (
            z.rename(columns={"open_time": "time"})
             .iloc[:, :12]
        )
    else:
        z = (
            pd.read_csv(
                io.BytesIO(b),
                compression="zip",
                header=None
            )
            .iloc[:, :12]
        )

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


def get(url):
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

    p = start.to_period("M")
    q = end.to_period("M")

    while p <= q:

        fn = (
            f"{symbol}-{interval}-"
            f"{p.year}-{p.month:02d}.zip"
        )

        url = (
            f"{base}/monthly/klines/"
            f"{symbol}/{interval}/{fn}"
        )

        z = get(url)

        if z is not None:

            rows.append(z)

        elif p == q:

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

                z = get(url)

                if z is not None:
                    rows.append(z)

                d += pd.Timedelta(days=1)

        p += 1

    if not rows:
        raise RuntimeError(
            f"No data: {symbol} {interval}"
        )

    z = pd.concat(
        rows,
        ignore_index=True
    )

    z = z[
        (z.time >= start) &
        (z.time <= end)
    ]

    return (
        z.drop_duplicates("time")
         .sort_values("time")
         .reset_index(drop=True)
    )


# ============================================================
# SIGNAL
# ============================================================

def build(x, h):
    x = x.copy()
    h = h.copy()

    # Donchian 20, uniquement bougies précédentes
    x["dc20"] = (
        x.high
        .rolling(20)
        .max()
        .shift(1)
    )

    # Contexte 4h
    for n in [20, 50, 200]:

        h[f"e{n}"] = (
            h.close
            .ewm(
                span=n,
                adjust=False
            )
            .mean()
        )

    step = (
        h.time
        .diff()
        .mode()
        .iloc[0]
    )

    # Alignement avec les bougies 1h suivantes
    h["time"] += step

    h = h[
        [
            "time",
            "close",
            "e20",
            "e50",
            "e200"
        ]
    ]

    # Evite close_x / close_y
    h = h.rename(
        columns={
            "close": "ctx_close"
        }
    )

    x = pd.merge_asof(
        x.sort_values("time"),
        h.sort_values("time"),
        on="time",
        direction="backward"
    )

    x["trend"] = np.where(
        (
            (x.e20 > x.e50) &
            (x.e50 > x.e200)
        ),
        "trend",

        np.where(
            (
                (x.e20 < x.e50) &
                (x.e50 < x.e200)
            ),
            "down",
            "range"
        )
    )

    # Signal fixe :
    # clôture 1h > Donchian20 précédent
    x["sig"] = (
        x["close"] > x["dc20"]
    ).fillna(False)

    return x


# ============================================================
# STATE
# ============================================================

def load_state():

    if STATE.exists():

        try:
            return json.loads(
                STATE.read_text()
            )

        except Exception:
            log("STATE invalid -> reset")

    return {
        "cash": CAPITAL,
        "equity": CAPITAL,
        "peak": CAPITAL,
        "position": None,
        "trades": [],
        "last_bar": None,
        "started": str(
            pd.Timestamp.now(tz="UTC")
        )
    }


def save_state(s):

    STATE.write_text(
        json.dumps(
            s,
            indent=2,
            default=str
        )
    )


# ============================================================
# TRADE
# ============================================================

def close_trade(
    s,
    p,
    price,
    reason,
    time
):

    entry = p["entry"]

    gross = (
        price / entry - 1
    )

    net = (
        gross -
        FEE -
        FEE
    )

    pnl = (
        s["cash"] *
        net
    )

    s["cash"] += pnl

    p.update(
        {
            "exit": float(price),
            "exit_time": str(time),
            "reason": reason,
            "gross_pct": gross * 100,
            "ret_pct": net * 100,
            "pnl": pnl
        }
    )

    s["trades"].append(p)

    s["position"] = None


# ============================================================
# MAIN
# ============================================================

def main():

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--days",
        type=int,
        default=10
    )

    args = ap.parse_args()

    log("")
    log(
        "V438 | PAPER FORWARD"
    )

    log(
        "SOLUSDT | DONCHIAN20 | LONG"
    )

    log(
        "TP=3% | SL=1.5% | HOLD=36h"
    )

    log(
        "ALL_TAKER | PAPER ONLY"
    )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    s = load_state()

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    log("DATA | SOLUSDT 1h")

    x = fetch(
        SYMBOL,
        "1h",
        args.days
    )

    log(
        f"DATA | 1h={len(x)}"
    )

    log("DATA | SOLUSDT 4h")

    h = fetch(
        SYMBOL,
        "4h",
        args.days + 10
    )

    log(
        f"DATA | 4h={len(h)}"
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    d = build(
        x,
        h
    )

    # La dernière bougie est en cours :
    # on travaille sur la dernière bougie clôturée.
    if len(d) < 3:
        raise RuntimeError(
            "Not enough candles"
        )

    bar = d.iloc[-2]

    bar_time = str(
        bar.time
    )

    log(
        f"BAR | {bar_time}"
    )

    # --------------------------------------------------------
    # EVITER DOUBLE TRAITEMENT
    # --------------------------------------------------------

    if s["last_bar"] == bar_time:

        log(
            "SKIP | already processed"
        )

        return

    s["last_bar"] = bar_time

    # --------------------------------------------------------
    # POSITION EXISTANTE
    # --------------------------------------------------------

    if s["position"]:

        p = s["position"]

        age = (
            pd.Timestamp(bar.time) -
            pd.Timestamp(
                p["entry_time"]
            )
        ).total_seconds() / 3600

        hi = float(bar.high)
        lo = float(bar.low)

        # Même règle conservatrice :
        # SL avant TP si les deux sont touchés.
        if lo <= p["sl"]:

            close_trade(
                s,
                p,
                p["sl"],
                "SL",
                bar.time
            )

            log(
                f"EXIT SL | "
                f"{p['entry']:.3f} -> "
                f"{p['sl']:.3f}"
            )

        elif hi >= p["tp"]:

            close_trade(
                s,
                p,
                p["tp"],
                "TP",
                bar.time
            )

            log(
                f"EXIT TP | "
                f"{p['entry']:.3f} -> "
                f"{p['tp']:.3f}"
            )

        elif age >= HOLD:

            close_trade(
                s,
                p,
                float(bar.close),
                "TIME",
                bar.time
            )

            log(
                f"EXIT TIME | "
                f"{bar.close:.3f}"
            )

    # --------------------------------------------------------
    # NOUVELLE ENTREE
    # --------------------------------------------------------

    if (
        s["position"] is None and
        bool(bar.sig)
    ):

        # Entrée taker + slippage défavorable
        entry = (
            float(bar.open) *
            (1 + SLIP)
        )

        p = {
            "entry_time": bar_time,
            "entry": entry,
            "tp": entry * (
                1 + TP / 100
            ),
            "sl": entry * (
                1 - SL / 100
            )
        }

        s["position"] = p

        log(
            f"ENTRY | "
            f"{bar_time} | "
            f"{entry:.3f} | "
            f"TP={p['tp']:.3f} | "
            f"SL={p['sl']:.3f}"
        )

    # --------------------------------------------------------
    # EQUITY
    # --------------------------------------------------------

    s["equity"] = s["cash"]

    if s["position"]:

        p = s["position"]

        unrealized = (
            float(bar.close) /
            p["entry"] - 1
        )

        s["equity"] = (
            s["cash"] *
            (1 + unrealized)
        )

    s["peak"] = max(
        s["peak"],
        s["equity"]
    )

    dd = (
        s["equity"] /
        s["peak"] -
        1
    ) * 100

    # --------------------------------------------------------
    # STATISTIQUES
    # --------------------------------------------------------

    tr = pd.DataFrame(
        s["trades"]
    )

    n = len(tr)

    if n:

        wins = int(
            (tr.ret_pct > 0).sum()
        )

        losses = (
            -tr.loc[
                tr.ret_pct < 0,
                "ret_pct"
            ].sum()
        )

        gains = (
            tr.loc[
                tr.ret_pct > 0,
                "ret_pct"
            ].sum()
        )

        pf = (
            gains / losses
            if losses > 0
            else np.inf
        )

    else:

        wins = 0
        pf = np.nan

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    log(
        f"STATUS | "
        f"EQ={s['equity']:.2f} | "
        f"CASH={s['cash']:.2f} | "
        f"TRADES={n} | "
        f"WIN={wins} | "
        f"PF={pf:.3f} | "
        f"DD={dd:.2f}% | "
        f"POS={'OPEN' if s['position'] else 'FLAT'}"
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    save_state(s)

    if n:

        tr.to_csv(
            OUT /
            "paper_trades_v438.csv",
            index=False
        )

    summary = [
        "# SCALP LAB V4.3.8",
        "",
        "Forward paper trading.",
        "",
        f"- Symbol: {SYMBOL}",
        "- Signal: Donchian20 LONG",
        f"- TP: {TP}%",
        f"- SL: {SL}%",
        f"- HOLD: {HOLD}h",
        "- Execution: ALL_TAKER",
        "- Mode: PAPER ONLY",
        "",
        f"- Equity: {s['equity']:.2f}",
        f"- Cash: {s['cash']:.2f}",
        f"- Trades: {n}",
        f"- Win rate: "
        f"{(wins/n*100 if n else 0):.1f}%",
        f"- PF: {pf:.3f}",
        f"- DD: {dd:.2f}%",
        f"- Position: "
        f"{'OPEN' if s['position'] else 'FLAT'}",
    ]

    (
        OUT /
        "paper_summary_v438.md"
    ).write_text(
        "\n".join(summary),
        encoding="utf-8"
    )

    log("DONE V438")


if __name__ == "__main__":
    main()
