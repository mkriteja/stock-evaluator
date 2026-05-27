"""
pillars/momentum.py — MOMENTUM pillar (25% weight)

Five signals:
  1. Price Momentum (12M-1M)  — Jegadeesh & Titman (1993), 150yr validation
  2. EMA Trend Regime         — 20/50/200 EMA: Golden Cross, price above/below
  3. MACD (12/26/9)           — Trend confirmation; histogram direction
  4. Volume Trend (OBV)       — Institutional accumulation/distribution
  5. Market Regime Filter     — S&P 500 vs 200-EMA (crash protection)

All momentum signals are volatility-scaled to reduce crash risk.
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional


# ── Technical indicator helpers (no external lib dependency) ─────────────────

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(prices: pd.Series, n: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=n - 1, min_periods=n).mean()
    avg_loss = loss.ewm(com=n - 1, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(prices: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def _realized_vol(returns: pd.Series, window: int = 20) -> float:
    """Annualized realized volatility over last `window` trading days."""
    if len(returns) < window:
        return 0.20  # default 20%
    rv = returns.tail(window).std() * np.sqrt(252)
    return float(rv) if rv > 0 else 0.20


# ── Signal computers ─────────────────────────────────────────────────────────

def compute_price_momentum(hist: pd.DataFrame) -> Dict:
    """
    Jegadeesh & Titman 12M-1M momentum.
    Returns 1M, 3M, 6M, 12M-1M returns and a composite score.
    """
    out = {"ret_1m": None, "ret_3m": None, "ret_6m": None, "ret_12m1m": None,
           "score": 50.0, "label": "N/A", "vol_scaled_score": None}

    if hist is None or hist.empty or len(hist) < 30:
        out["label"] = "Insufficient price history"
        return out

    close = hist["Close"].dropna()
    if len(close) < 30:
        out["label"] = "Insufficient price history"
        return out

    returns = close.pct_change().dropna()
    rv = _realized_vol(returns)

    def ret(days):
        if len(close) < days + 1:
            return None
        return float((close.iloc[-1] / close.iloc[-days]) - 1)

    r1 = ret(21)
    r3 = ret(63)
    r6 = ret(126)
    r12 = ret(252)
    r1m = ret(21)

    if r12 is not None and r1m is not None:
        r12m1m = ((close.iloc[-1] / close.iloc[-252]) - 1) - ((close.iloc[-1] / close.iloc[-21]) - 1) \
            if len(close) >= 252 else r12
    else:
        r12m1m = r6 or r3

    out["ret_1m"] = round(r1 * 100, 2) if r1 is not None else None
    out["ret_3m"] = round(r3 * 100, 2) if r3 is not None else None
    out["ret_6m"] = round(r6 * 100, 2) if r6 is not None else None
    out["ret_12m1m"] = round(r12m1m * 100, 2) if r12m1m is not None else None

    # Score: 12M-1M return of +30% → 90; 0% → 55; -30% → 20
    primary = r12m1m or r6 or r3 or r1 or 0
    raw_score = float(np.clip(55 + primary * 120, 0, 100))

    # Volatility scaling: high vol reduces confidence in momentum signal
    vol_scalar = np.clip(0.15 / rv, 0.5, 1.5)  # normalize to 15% baseline vol
    scaled_score = float(np.clip(50 + (raw_score - 50) * vol_scalar, 0, 100))

    out["score"] = round(raw_score, 1)
    out["vol_scaled_score"] = round(scaled_score, 1)
    out["realized_vol_pct"] = round(rv * 100, 1)

    if primary > 0.30:
        out["label"] = "Very strong momentum"
    elif primary > 0.15:
        out["label"] = "Strong momentum"
    elif primary > 0.05:
        out["label"] = "Moderate momentum"
    elif primary > -0.05:
        out["label"] = "Neutral"
    elif primary > -0.20:
        out["label"] = "Weak (negative momentum)"
    else:
        out["label"] = "Strong downtrend"

    return out


def compute_ema_regime(hist: pd.DataFrame, week52_high=None, current_price=None) -> Dict:
    """
    EMA 20/50/200 crossover analysis + 52-week high proximity.
    Golden Cross (50 > 200) = bull regime.
    """
    out = {"ema20": None, "ema50": None, "ema200": None, "current": None,
           "regime": "N/A", "week52_prox_pct": None, "score": 50.0, "label": "N/A"}

    if hist is None or hist.empty:
        return out

    close = hist["Close"].dropna()
    if len(close) < 30:
        return out

    ema20 = float(_ema(close, 20).iloc[-1])
    ema50 = float(_ema(close, 50).iloc[-1]) if len(close) >= 50 else None
    ema200 = float(_ema(close, 200).iloc[-1]) if len(close) >= 200 else None
    price = float(close.iloc[-1])

    out["ema20"] = round(ema20, 2)
    out["ema50"] = round(ema50, 2) if ema50 else None
    out["ema200"] = round(ema200, 2) if ema200 else None
    out["current"] = round(price, 2)

    # 52W high proximity (merged from 52-week-high signal)
    w52h = week52_high or (float(close.tail(252).max()) if len(close) >= 252 else float(close.max()))
    prox = price / w52h if w52h > 0 else None
    out["week52_prox_pct"] = round(prox * 100, 1) if prox else None

    # Scoring
    scores = []

    # Price vs EMAs
    if price > ema20:
        scores.append(70.0)
    else:
        scores.append(35.0)
    if ema50:
        if price > ema50:
            scores.append(72.0)
        else:
            scores.append(32.0)
    if ema200:
        if price > ema200:
            scores.append(75.0)
        else:
            scores.append(25.0)

    # Golden / Death cross
    if ema50 and ema200:
        if ema50 > ema200:
            scores.append(80.0)
            out["regime"] = "Golden Cross (Bull)"
        else:
            scores.append(25.0)
            out["regime"] = "Death Cross (Bear)"
    else:
        out["regime"] = "Short history"

    # 52W high proximity score
    if prox:
        prox_score = float(np.clip((prox - 0.60) / (1.0 - 0.60) * 80 + 10, 10, 95))
        scores.append(prox_score)

    final_score = float(np.mean(scores)) if scores else 50.0
    out["score"] = round(final_score, 1)

    above_all = all([
        price > ema20,
        ema50 and price > ema50,
        ema200 and price > ema200,
    ])
    if above_all and ema50 and ema200 and ema50 > ema200:
        out["label"] = "Strong bull regime — above all EMAs"
    elif price > ema20 and (ema50 is None or price > ema50):
        out["label"] = "Short-term uptrend"
    elif ema50 and ema200 and ema50 < ema200:
        out["label"] = "Bear regime — death cross"
    else:
        out["label"] = "Mixed signals"

    return out


def compute_macd_signal(hist: pd.DataFrame) -> Dict:
    """MACD(12,26,9) — trend confirmation, histogram direction."""
    out = {"macd": None, "signal": None, "histogram": None,
           "hist_direction": "N/A", "crossover": "N/A", "score": 50.0, "label": "N/A"}

    if hist is None or hist.empty or len(hist) < 40:
        out["label"] = "Insufficient history"
        return out

    close = hist["Close"].dropna()
    macd_line, signal_line, histogram = _macd(close)

    m = float(macd_line.iloc[-1])
    s = float(signal_line.iloc[-1])
    h = float(histogram.iloc[-1])
    h_prev = float(histogram.iloc[-2]) if len(histogram) >= 2 else h

    out["macd"] = round(m, 4)
    out["signal"] = round(s, 4)
    out["histogram"] = round(h, 4)
    out["hist_direction"] = "Expanding" if abs(h) > abs(h_prev) else "Contracting"

    score = 50.0
    # MACD above zero line → bullish bias
    if m > 0:
        score += 15
    else:
        score -= 15
    # MACD above signal line → bullish
    if m > s:
        score += 15
        out["crossover"] = "Bullish (MACD > Signal)"
    else:
        score -= 15
        out["crossover"] = "Bearish (MACD < Signal)"
    # Histogram expanding in positive territory → strongest bull
    if h > 0 and h > h_prev:
        score += 20
    elif h < 0 and h < h_prev:
        score -= 20
    elif h > 0:
        score += 5
    else:
        score -= 5

    out["score"] = round(float(np.clip(score, 0, 100)), 1)
    if score > 75:
        out["label"] = "Strong bullish momentum"
    elif score > 55:
        out["label"] = "Bullish"
    elif score > 45:
        out["label"] = "Neutral"
    elif score > 30:
        out["label"] = "Bearish"
    else:
        out["label"] = "Strong bearish momentum"
    return out


def compute_volume_trend(hist: pd.DataFrame) -> Dict:
    """
    OBV (On-Balance Volume) trend — is price movement backed by volume?
    Rising OBV = institutional accumulation.
    """
    out = {"obv_trend": "N/A", "vol_20d_vs_90d": None, "score": 50.0, "label": "N/A"}

    if hist is None or hist.empty or "Volume" not in hist.columns or len(hist) < 30:
        out["label"] = "No volume data"
        return out

    close = hist["Close"].dropna()
    volume = hist["Volume"].dropna()
    if len(volume) < 30:
        out["label"] = "Insufficient volume history"
        return out

    obv = _obv(close, volume)

    # OBV trend: compare 20-day avg to 90-day avg
    obv_20 = float(obv.tail(20).mean())
    obv_90 = float(obv.tail(90).mean()) if len(obv) >= 90 else float(obv.mean())
    obv_rising = obv_20 > obv_90

    # Volume trend: recent avg volume vs. longer-term avg
    vol_20 = float(volume.tail(20).mean())
    vol_90 = float(volume.tail(90).mean()) if len(volume) >= 90 else float(volume.mean())
    vol_ratio = vol_20 / vol_90 if vol_90 > 0 else 1.0
    out["vol_20d_vs_90d"] = round(vol_ratio, 2)

    # OBV slope (linear regression direction)
    obv_tail = obv.tail(20).values
    x = np.arange(len(obv_tail))
    slope = np.polyfit(x, obv_tail, 1)[0]
    out["obv_trend"] = "Rising" if slope > 0 else "Falling"

    score = 50.0
    if obv_rising:
        score += 20
    else:
        score -= 20
    if slope > 0:
        score += 15
    else:
        score -= 15
    # Volume expansion on recent moves
    if vol_ratio > 1.15:
        score += 15
    elif vol_ratio < 0.85:
        score -= 10

    out["score"] = round(float(np.clip(score, 0, 100)), 1)
    if score > 70:
        out["label"] = "Strong institutional accumulation"
    elif score > 55:
        out["label"] = "Bullish volume profile"
    elif score > 45:
        out["label"] = "Neutral volume"
    elif score > 30:
        out["label"] = "Distribution pressure"
    else:
        out["label"] = "Heavy distribution"
    return out


def compute_market_regime(spy_hist: pd.DataFrame) -> Dict:
    """
    Market regime filter: is S&P 500 above its 200-day EMA?
    CFA research (Dec 2025): this filter cuts momentum drawdowns by ~50%.
    """
    out = {"spy_above_200ema": None, "regime": "Unknown", "score": 50.0,
           "drawdown_protection": "N/A"}

    if spy_hist is None or spy_hist.empty or len(spy_hist) < 50:
        out["regime"] = "Filter unavailable"
        return out

    close = spy_hist["Close"].dropna()
    ema200 = _ema(close, 200) if len(close) >= 200 else _ema(close, 50)
    spy_price = float(close.iloc[-1])
    ema_val = float(ema200.iloc[-1])
    above = spy_price > ema_val
    out["spy_above_200ema"] = above
    out["spy_price"] = round(spy_price, 2)
    out["spy_ema200"] = round(ema_val, 2)

    if above:
        out["regime"] = "Risk-ON (SPY > 200 EMA)"
        out["score"] = 75.0
        out["drawdown_protection"] = "Momentum signals at full weight"
    else:
        out["regime"] = "Risk-OFF (SPY < 200 EMA)"
        out["score"] = 30.0
        out["drawdown_protection"] = "⚠ Momentum signals reduced — bear market"
    return out


def compute(data: Dict[str, Any]) -> Dict:
    """Compute the MOMENTUM pillar score (0–100), with market regime scaling."""
    hist = data.get("history", pd.DataFrame())
    spy_hist = data.get("spy_history", pd.DataFrame())

    price_mom = compute_price_momentum(hist)
    ema_regime = compute_ema_regime(
        hist,
        week52_high=data.get("week52_high"),
        current_price=data.get("current_price")
    )
    macd_sig = compute_macd_signal(hist)
    vol_trend = compute_volume_trend(hist)
    mkt_regime = compute_market_regime(spy_hist)

    # Use vol-scaled score for price momentum if available
    pm_score = price_mom.get("vol_scaled_score") or price_mom.get("score", 50.0)

    weights = {
        "price_momentum": 0.30,
        "ema_regime": 0.25,
        "macd": 0.20,
        "volume": 0.15,
        "market_regime": 0.10,
    }
    raw_pillar = (
        pm_score * weights["price_momentum"]
        + ema_regime["score"] * weights["ema_regime"]
        + macd_sig["score"] * weights["macd"]
        + vol_trend["score"] * weights["volume"]
        + mkt_regime["score"] * weights["market_regime"]
    )

    # Market regime scaling: if SPY in bear market, dampen momentum scores
    regime_scalar = 0.70 if not mkt_regime.get("spy_above_200ema", True) else 1.0
    pillar_score = float(np.clip(50 + (raw_pillar - 50) * regime_scalar, 0, 100))

    return {
        "pillar": "Momentum",
        "score": round(pillar_score, 1),
        "weight": 0.25,
        "market_regime": mkt_regime,
        "components": {
            "price_momentum_12m1m": price_mom,
            "ema_trend_regime": ema_regime,
            "macd_signal": macd_sig,
            "volume_trend_obv": vol_trend,
        },
    }
