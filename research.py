"""
Laboratoire de recherche pour un bot de scalping Binance USDT-M (petit capital).

Objectif : savoir AVANT de construire le bot si une stratégie simple survit
aux frais, avec une validation honnête (hors échantillon).

Méthode
  * Données : bougies publiques Binance USD-M (data.binance.vision), sans clé API.
  * 5 familles de signaux x quelques paramètres (20 signaux) x 4 réglages de
    sortie (TP/SL en multiples d'ATR + sortie sur durée) = 80 stratégies.
  * 3 profils de frais : tout au marché / TP en ordre limite / entrée+TP limite.
  * Position fixe (aucune martingale), une seule position à la fois.
  * Découpage temporel : 60 % « apprentissage » (choix des paramètres),
    40 % « test » jamais utilisé pour choisir. Seul le test compte.
  * Référence « hasard » : la médiane des 80 stratégies sur la période de test.

Usage
    python research.py                                  # BTC/ETH/SOL, 5m et 15m, 365 j
    python research.py --symbols BTCUSDT --intervals 5m --days 180
    python research.py --synthetic rw                   # test sans réseau, marche aléatoire
    python research.py --synthetic mr                   # test sans réseau, avec un vrai avantage planté
"""
import argparse
import io
import math
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

INTERVAL_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
               "30m": 1_800_000, "1h": 3_600_000}

# --- Hypothèses de coûts (USDT-M, palier VIP0, sans remise BNB) --------------
FEE_TAKER = 0.0005          # 0,05 % par côté
FEE_MAKER = 0.0002          # 0,02 % par côté
THROUGH = 0.00005           # un ordre limite n'est exécuté que si le prix le TRAVERSE de 0,005 %
SLIP = {"BTCUSDT": 0.0001, "ETHUSDT": 0.00015, "SOLUSDT": 0.0003,
        "XRPUSDT": 0.0003, "BNBUSDT": 0.0002}     # glissement par côté, ordres au marché
DEFAULT_SLIP = 0.0003

PROFILES = ("taker", "maker_tp", "maker_both")
EXITS = [(1.5, 1.0, 12), (2.0, 1.0, 24), (3.0, 1.5, 36), (2.0, 2.0, 24)]  # (TP xATR, SL xATR, durée max en bougies)
TRAIN_FRACTION = 0.6
MIN_TRAIN_TRADES = 150


# ------------------------------------------------------------------ données
def _read_zip_csv(content):
    z = zipfile.ZipFile(io.BytesIO(content))
    out = []
    for line in z.read(z.namelist()[0]).decode().splitlines():
        p = line.split(",")
        if p and p[0].strip().isdigit():
            out.append(p[:12])
    return out


def fetch_vision(symbol, interval, start_ms, end_ms):
    base = "https://data.binance.vision/data/futures/um"
    start = datetime.fromtimestamp(start_ms / 1000, timezone.utc).date()
    end = datetime.fromtimestamp(end_ms / 1000, timezone.utc).date()
    today = datetime.now(timezone.utc).date()
    rows, day = [], start.replace(day=1)
    while day <= end:
        nxt = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        if nxt <= today.replace(day=1):
            name = f"{symbol}-{interval}-{day:%Y-%m}"
            r = requests.get(f"{base}/monthly/klines/{symbol}/{interval}/{name}.zip", timeout=90)
            if r.status_code == 200:
                rows += _read_zip_csv(r.content)
            day = nxt
        else:
            d = day
            while d < today and d <= end:
                name = f"{symbol}-{interval}-{d:%Y-%m-%d}"
                r = requests.get(f"{base}/daily/klines/{symbol}/{interval}/{name}.zip", timeout=90)
                if r.status_code == 200:
                    rows += _read_zip_csv(r.content)
                d += timedelta(days=1)
            break
    return rows


def to_frame(rows):
    d = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume",
                                    "x", "q", "n", "tb", "tq", "i"])
    for k in ["time", "open", "high", "low", "close", "volume"]:
        d[k] = pd.to_numeric(d[k], errors="coerce")
    d = d.dropna(subset=["time", "open", "high", "low", "close", "volume"])
    return d.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def synthetic(kind, n, seed, interval, sub=6, edge=1.0):
    """rw = marche aléatoire (aucun avantage). mr = retour à la moyenne planté."""
    rng = np.random.default_rng(seed)
    N = n * sub
    rw = np.cumsum(rng.normal(0, 0.0009 / math.sqrt(sub), N))
    if kind == "mr":
        eps = rng.normal(0, 0.00035 * edge, N)
        x = np.zeros(N)
        for t in range(1, N):
            x[t] = 0.985 * x[t - 1] + eps[t]
        rw = rw + x
    p = (80000 * np.exp(rw)).reshape(n, sub)
    step = INTERVAL_MS[interval]
    t0 = 1_700_000_000_000
    return pd.DataFrame({
        "time": t0 + np.arange(n) * step,
        "open": p[:, 0], "high": p.max(1), "low": p.min(1), "close": p[:, -1],
        "volume": rng.uniform(50, 500, n),
    })


# --------------------------------------------------------------- indicateurs
def features(d):
    c, h, l, v = d.close, d.high, d.low, d.volume
    F = {"o": d.open.values, "h": h.values, "l": l.values, "c": c.values, "v": v.values}
    dlt = c.diff()
    up = dlt.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-dlt.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    F["rsi"] = (100 - 100 / (1 + up / dn.replace(0, np.nan))).values
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    F["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean().values
    F["ema20"] = c.ewm(span=20, adjust=False).mean().values
    F["ema50"] = c.ewm(span=50, adjust=False).mean().values
    F["ema200"] = c.ewm(span=200, adjust=False).mean().values
    F["_c"], F["_h"], F["_l"], F["_v"] = c, h, l, v
    return F


def _sig(long_mask, short_mask):
    s = np.zeros(len(long_mask), dtype=np.int8)
    s[np.asarray(long_mask)] = 1
    s[np.asarray(short_mask)] = -1
    return s


def combos(F):
    """20 signaux. Signal calculé sur la bougie i CLÔTURÉE, exécuté à la bougie i+1."""
    c, h, l, v = F["_c"], F["_h"], F["_l"], F["_v"]
    out = []
    for k in (2.0, 2.5):
        mid, sd = c.rolling(20).mean(), c.rolling(20).std()
        for rlo in (25, 30):
            out.append((f"bb_rsi k={k} rsi<{rlo}",
                        _sig((c < mid - k * sd) & (F["rsi"] < rlo),
                             (c > mid + k * sd) & (F["rsi"] > 100 - rlo))))
    for n in (30, 60):
        z = (c - c.rolling(n).mean()) / c.rolling(n).std()
        for thr in (2.0, 2.5):
            out.append((f"zscore n={n} thr={thr}", _sig(z < -thr, z > thr)))
    for n in (20, 50):
        hi, lo = h.rolling(n).max().shift(1), l.rolling(n).min().shift(1)
        for vm in (0.0, 1.5):
            ok = (v > vm * v.rolling(20).mean()) if vm > 0 else pd.Series(True, index=c.index)
            out.append((f"donchian n={n} vol>{vm}x", _sig((c > hi) & ok, (c < lo) & ok)))
    tp_ = (h + l + c) / 3
    for n in (48, 96):
        vw = (tp_ * v).rolling(n).sum() / v.rolling(n).sum()
        for k in (2.0, 3.0):
            a = pd.Series(F["atr"], index=c.index)
            out.append((f"vwap n={n} k={k}atr", _sig(c < vw - k * a, c > vw + k * a)))
    for thr in (35, 40):
        upt = (F["ema20"] > F["ema50"]) & (c.values > F["ema200"])
        dnt = (F["ema20"] < F["ema50"]) & (c.values < F["ema200"])
        out.append((f"trend_pullback rsi<{thr}",
                    _sig(upt & (F["rsi"] < thr), dnt & (F["rsi"] > 100 - thr))))
    for thr in (30, 45):   # variante plus rare, retournement plus profond
        upt = (F["ema20"] > F["ema50"]) & (c.values > F["ema200"])
        dnt = (F["ema20"] < F["ema50"]) & (c.values < F["ema200"])
        out.append((f"trend_deep_pullback rsi<{thr}",
                    _sig(upt & (F["rsi"] < thr - 10), dnt & (F["rsi"] > 110 - thr))))
    return out


# ---------------------------------------------------------------- simulation
def simulate(L, sig, tp_m, sl_m, hold, prof, slip):
    """Renvoie (indices_signal, net_pct, brut_pct, durée) de chaque trade."""
    o, h, l, c, atr = L["o"], L["h"], L["l"], L["c"], L["atr"]
    n = len(c)
    maker_entry = prof == "maker_both"
    maker_tp = prof in ("maker_tp", "maker_both")
    I, NET, GRO, DUR = [], [], [], []
    free = 0
    for i in np.flatnonzero(sig).tolist():
        if i < free:
            continue
        k = i + 1
        if k >= n - 1:
            break
        s = int(sig[i])
        a = atr[i]
        if not (a > 0):
            continue
        if maker_entry:
            lim = c[i]
            if s > 0:
                if not (l[k] < lim * (1 - THROUGH)):
                    continue
            elif not (h[k] > lim * (1 + THROUGH)):
                continue
            entry, e_fee = lim, FEE_MAKER
        else:
            entry, e_fee = o[k] * (1 + s * slip), FEE_TAKER
        tp = entry + s * tp_m * a
        sl = entry - s * sl_m * a
        tp_chk = tp * (1 + s * THROUGH) if maker_tp else tp
        last = min(k + hold, n) - 1
        exit_px = kind = None
        j = k
        while j <= last:
            if s > 0:
                hit_sl, hit_tp = l[j] <= sl, h[j] >= tp_chk
            else:
                hit_sl, hit_tp = h[j] >= sl, l[j] <= tp_chk
            if hit_sl:                                  # égalité -> SL d'abord (prudent)
                exit_px, kind = sl * (1 - s * slip), "sl"
                break
            if hit_tp:
                exit_px = tp if maker_tp else tp * (1 - s * slip)
                kind = "tp"
                break
            j += 1
        if exit_px is None:
            j = last
            exit_px, kind = c[j] * (1 - s * slip), "time"
        x_fee = FEE_MAKER if (kind == "tp" and maker_tp) else FEE_TAKER
        gross = s * (exit_px - entry) / entry
        I.append(i)
        GRO.append(gross)
        NET.append(gross - e_fee - x_fee * exit_px / entry)
        DUR.append(j - k + 1)
        free = j
    return (np.array(I), np.array(NET), np.array(GRO), np.array(DUR))


def split_stats(I, NET, GRO, split):
    def blk(mask):
        x = NET[mask]
        m = len(x)
        if m < 2:
            return dict(n=m, mean=float("nan"), sd=float("nan"), gross=float("nan"),
                        win=float("nan"), pf=float("nan"))
        w, lo = x[x > 0].sum(), -x[x < 0].sum()
        return dict(n=m, mean=x.mean(), sd=x.std(ddof=1), gross=GRO[mask].mean(),
                    win=(x > 0).mean(), pf=(w / lo) if lo > 0 else float("inf"))
    return blk(I < split), blk(I >= split)


# ------------------------------------------------------------------- rapport
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--intervals", default="5m,15m")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--synthetic", choices=["rw", "mr"], default=None)
    ap.add_argument("--n", type=int, default=40000, help="bougies par série synthétique")
    ap.add_argument("--capital", type=float, default=100.0)
    ap.add_argument("--edge", type=float, default=1.0, help="force du retour à la moyenne planté (test synthétique)")
    a = ap.parse_args()
    symbols = a.symbols.split(",")
    intervals = a.intervals.split(",")

    md = []
    def out(s=""):
        print(s, flush=True)
        md.append(s)

    out(f"# Recherche scalping — {'SYNTHÉTIQUE ' + a.synthetic if a.synthetic else 'données réelles Binance USD-M'}")
    out(f"Coûts : taker {FEE_TAKER*100:.2f}% / maker {FEE_MAKER*100:.2f}% par côté, "
        f"glissement au marché {min(SLIP.values())*100:.3f}–{max(SLIP.values())*100:.3f}% par côté, "
        f"ordre limite exécuté seulement si le prix le traverse de {THROUGH*100:.3f}%.")
    out(f"Découpage : {TRAIN_FRACTION*100:.0f}% apprentissage / {100-TRAIN_FRACTION*100:.0f}% test. "
        "Position fixe, sans martingale.\n")

    allrows = []                       # une ligne par (symbole, intervalle, profil, stratégie)
    L_cache = {}
    for iv in intervals:
        for si, sym in enumerate(symbols):
            if a.synthetic:
                d = synthetic(a.synthetic, a.n, seed=si + 7, interval=iv, edge=a.edge)
            else:
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - a.days * 86_400_000
                print(f"Téléchargement {sym} {iv}...", flush=True)
                d = to_frame(fetch_vision(sym, iv, start_ms, end_ms))
                d = d[d.time >= start_ms].reset_index(drop=True)
            if len(d) < 2000:
                print(f"  {sym} {iv}: données insuffisantes ({len(d)} bougies), ignoré")
                continue
            F = features(d)
            L = {k: F[k].tolist() for k in ("o", "h", "l", "c", "atr")}
            days = (d.time.iloc[-1] - d.time.iloc[0]) / 86_400_000
            split = int(len(d) * TRAIN_FRACTION)
            oos_days = days * (1 - TRAIN_FRACTION)
            L_cache[(sym, iv)] = (L, days, oos_days, split, combos(F))
            slip = SLIP.get(sym, DEFAULT_SLIP)
            out(f"- {sym} {iv} : {len(d)} bougies, {days:.0f} jours")
            t0 = time.time()
            for name, sig in L_cache[(sym, iv)][4]:
                for ei, (tpm, slm, hold) in enumerate(EXITS):
                    for prof in PROFILES:
                        I, NET, GRO, DUR = simulate(L, sig, tpm, slm, hold, prof, slip)
                        if len(I) == 0:
                            continue
                        tr, te = split_stats(I, NET, GRO, split)
                        allrows.append(dict(sym=sym, iv=iv, prof=prof, sig=name, ex=ei,
                                            tp=tpm, sl=slm, hold=hold,
                                            n_tr=tr["n"], m_tr=tr["mean"],
                                            n_te=te["n"], m_te=te["mean"], sd_te=te["sd"],
                                            g_te=te["gross"], w_te=te["win"], pf_te=te["pf"],
                                            oos_days=oos_days))
            print(f"  simulé en {time.time()-t0:.0f}s", flush=True)

    R = pd.DataFrame(allrows)
    if R.empty:
        raise SystemExit("Aucun résultat.")
    os.makedirs("results", exist_ok=True)
    R.to_csv("results/all_strategies.csv", index=False)

    out("\n## 1. Repère « hasard » : toutes les stratégies sur la période de TEST")
    out("Si rien n'a d'avantage, la moyenne par trade tend vers −(coût aller-retour).")
    out("| profil | stratégies | médiane net/trade | part > 0 | meilleure (à ne PAS utiliser) |")
    out("|---|---|---|---|---|")
    for prof in PROFILES:
        x = R[(R.prof == prof) & (R.n_te >= 100)]
        if len(x):
            out(f"| {prof} | {len(x)} | {x.m_te.median()*100:+.4f}% | {(x.m_te>0).mean()*100:.0f}% | "
                f"{x.m_te.max()*100:+.4f}% |")

    out("\n## 2. Procédure honnête : on choisit sur l'APPRENTISSAGE, on juge sur le TEST")
    out("Pour chaque symbole/intervalle/profil : meilleure stratégie à l'apprentissage "
        f"(≥ {MIN_TRAIN_TRADES} trades), puis ses résultats sur le test.\n")
    out("| intervalle | profil | symbole | stratégie choisie | net/trade apprent. | net/trade TEST | "
        "brut/trade TEST (après glissement, avant frais) | trades TEST | % gagnants | facteur de profit |")
    out("|---|---|---|---|---|---|---|---|---|---|")
    picks = []
    for iv in intervals:
        for prof in PROFILES:
            for sym in symbols:
                x = R[(R.iv == iv) & (R.prof == prof) & (R.sym == sym) & (R.n_tr >= MIN_TRAIN_TRADES)]
                if x.empty:
                    continue
                b = x.loc[x.m_tr.idxmax()]
                picks.append(b)
                out(f"| {iv} | {prof} | {sym} | {b.sig} (TP{b.tp}/SL{b.sl}/{int(b.hold)}b) | "
                    f"{b.m_tr*100:+.4f}% | {b.m_te*100:+.4f}% | {b.g_te*100:+.4f}% | {int(b.n_te)} | "
                    f"{b.w_te*100:.0f}% | {b.pf_te:.2f} |")
    P = pd.DataFrame(picks)

    out("\n## 3. Résultat agrégé sur le TEST (stratégies choisies à l'apprentissage)")
    out(f"Estimation du gain par jour pour un capital de {a.capital:.0f} USDT, position = capital "
        "(levier 1), un symbole.\n")
    out("| intervalle | profil | net moyen/trade | IC95 | t | symboles > 0 | trades/jour/symbole | "
        "USDT/jour/symbole |")
    out("|---|---|---|---|---|---|---|---|")
    winners = []
    for iv in intervals:
        for prof in PROFILES:
            x = P[(P.iv == iv) & (P.prof == prof)] if not P.empty else P
            if x is None or len(x) == 0:
                continue
            n = x.n_te.values
            mu = (x.m_te.values * n).sum() / n.sum()
            var = ((x.sd_te.values ** 2) * n).sum() / n.sum()
            se = math.sqrt(var / n.sum())
            t = mu / se if se > 0 else 0
            tpd = (x.n_te / x.oos_days).mean()
            pos = int((x.m_te > 0).sum())
            out(f"| {iv} | {prof} | {mu*100:+.4f}% | ±{1.96*se*100:.4f}% | {t:+.1f} | "
                f"{pos}/{len(x)} | {tpd:.1f} | {mu*a.capital*tpd:+.3f} |")
            if mu > 0 and t >= 2.5 and pos >= max(2, math.ceil(0.75 * len(x))):
                winners.append((iv, prof, mu, t, tpd))

    out("\n## 4. Verdict")
    if winners:
        out("Au moins une combinaison passe le filtre (net > 0, t ≥ 2,5, ≥ 75 % des symboles positifs) :")
        for iv, prof, mu, t, tpd in winners:
            out(f"- {iv} / {prof} : {mu*100:+.4f}% par trade (t={t:.1f}), "
                f"≈ {mu*a.capital*tpd:+.2f} USDT/jour/symbole pour {a.capital:.0f} USDT.")
        out("Prochaine étape : valider sur d'autres périodes/symboles, puis papier-trading avant tout argent réel.")
    else:
        out("Aucune combinaison ne passe le filtre (net > 0, t ≥ 2,5, ≥ 75 % des symboles positifs) "
            "sur la période de TEST : pas d'avantage exploitable détecté avec ces signaux et ces coûts.")
    out("\nLimites : bougies (pas de carnet d'ordres) ; exécution des ordres limites approximée par la "
        "règle de traversée ; pas de frais de financement ; un an de marché ; résultats passés.")

    with open("results/summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()
