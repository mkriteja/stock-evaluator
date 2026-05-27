"""
pillars/value.py — VALUE pillar (30% weight)

Three signals consolidated into one pillar score:
  1. Inverse DCF      — implied FCF growth vs. historical (market expectations test)
  2. EV/EBIT Yield    — capital-structure-neutral earnings yield vs. sector
  3. FCF Yield        — FCF/MarketCap vs. 10-yr Treasury (strongest single data point)
  4. Composite Multiples — P/E, EV/EBITDA, P/S, P/FCF collapsed into one z-score
"""

import numpy as np
from scipy.optimize import brentq
from typing import Any, Dict, Optional

# Sector median P/E benchmarks (approximate, used for relative scoring)
SECTOR_PE_MEDIANS = {
    "Technology": 28, "Communication Services": 22, "Consumer Cyclical": 20,
    "Consumer Defensive": 22, "Healthcare": 24, "Financials": 14,
    "Financial Services": 14, "Industrials": 20, "Energy": 12,
    "Basic Materials": 15, "Real Estate": 35, "Utilities": 18, "Unknown": 20,
}
SECTOR_EV_EBITDA_MEDIANS = {
    "Technology": 22, "Communication Services": 16, "Consumer Cyclical": 14,
    "Consumer Defensive": 15, "Healthcare": 18, "Financials": 12,
    "Financial Services": 12, "Industrials": 14, "Energy": 8,
    "Basic Materials": 10, "Real Estate": 20, "Utilities": 12, "Unknown": 15,
}


def _pct_rank_to_score(value, cheap_end, expensive_end) -> float:
    """Linear map: cheap_end → 100, expensive_end → 0."""
    if value is None:
        return 50.0
    score = 100 * (expensive_end - value) / (expensive_end - cheap_end)
    return float(np.clip(score, 0, 100))


def compute_inverse_dcf(data: Dict[str, Any]) -> Dict:
    """
    Reverse DCF: given current market cap, solve for the FCF growth rate
    the market is implying. Compare to company's historical FCF CAGR.
    """
    out = {
        "implied_growth_pct": None,
        "historical_growth_pct": None,
        "gap_pp": None,
        "score": 50.0,
        "label": "N/A",
        "note": "",
    }

    market_cap = data.get("market_cap")
    fcf = data.get("fcf")
    if not market_cap or not fcf or fcf <= 0:
        out["note"] = "Insufficient FCF data"
        return out

    r = 0.10   # required return (discount rate)
    tg = 0.03  # terminal growth rate
    n = 5      # projection years

    def dcf_equity(g: float) -> float:
        """Return NPV of 2-stage DCF minus market_cap."""
        if g >= r - 0.001:
            return 1e12
        pv = sum(fcf * (1 + g) ** t / (1 + r) ** t for t in range(1, n + 1))
        terminal_fcf = fcf * (1 + g) ** n
        tv = terminal_fcf * (1 + tg) / (r - tg)
        pv += tv / (1 + r) ** n
        return pv - market_cap

    try:
        implied_g = brentq(dcf_equity, -0.40, 0.80, xtol=1e-6, maxiter=200)
    except ValueError:
        # Market cap may be far outside reasonable range
        implied_g = 0.25 if dcf_equity(0.25) < 0 else -0.10
        out["note"] = "Implied growth at bound"

    out["implied_growth_pct"] = round(implied_g * 100, 1)

    # Historical FCF CAGR from cash flow statement
    CF = data.get("cashflow", None)
    hist_g = None
    if CF is not None and not CF.empty:
        try:
            for row in ["Free Cash Flow", "Operating Cash Flow"]:
                if row in CF.index:
                    series = CF.loc[row].dropna()
                    pos = series[series > 0]
                    if len(pos) >= 3:
                        first, last = float(pos.iloc[-1]), float(pos.iloc[0])
                        yrs = len(pos) - 1
                        if first > 0:
                            hist_g = (last / first) ** (1 / yrs) - 1
                        break
        except Exception:
            pass

    out["historical_growth_pct"] = round(hist_g * 100, 1) if hist_g is not None else None

    if hist_g is not None:
        gap = implied_g - hist_g  # positive = market expects more than history → overvalued
        out["gap_pp"] = round(gap * 100, 1)
        # Score: gap of +10pp → score 20 (overvalued); gap of -10pp → score 80 (undervalued)
        score = np.clip(50 - gap * 350, 0, 100)
        out["score"] = round(float(score), 1)
        if gap > 0.12:
            out["label"] = "Priced for perfection"
        elif gap > 0.05:
            out["label"] = "Slightly overvalued"
        elif gap > -0.05:
            out["label"] = "Fair value"
        elif gap > -0.12:
            out["label"] = "Undervalued"
        else:
            out["label"] = "Significantly undervalued"
    else:
        # Fall back: score based on absolute implied growth
        score = np.clip(50 - implied_g * 200, 0, 100)
        out["score"] = round(float(score), 1)
        out["label"] = "Fair value" if 0.05 < implied_g < 0.15 else (
            "Expensive" if implied_g >= 0.15 else "Cheap"
        )
    return out


def compute_fcf_yield(data: Dict[str, Any]) -> Dict:
    """
    FCF Yield = FCF / Market Cap, benchmarked against 10-yr Treasury yield.
    Spread > 2pp above Treasury → attractive; below → unattractive.
    """
    out = {"fcf_yield_pct": None, "treasury_yield_pct": 4.3,  # hardcoded 10yr approx
           "spread_pp": None, "score": 50.0, "label": "N/A"}

    fcf = data.get("fcf")
    market_cap = data.get("market_cap")
    if not fcf or not market_cap or market_cap <= 0:
        out["label"] = "No FCF data"
        return out

    fcf_yield = fcf / market_cap
    treasury = out["treasury_yield_pct"] / 100
    spread = fcf_yield - treasury

    out["fcf_yield_pct"] = round(fcf_yield * 100, 2)
    out["spread_pp"] = round(spread * 100, 2)

    # Score: spread of +4pp → 90; spread of -2pp → 20
    score = np.clip(50 + spread * 1000, 0, 100)
    out["score"] = round(float(score), 1)

    if spread > 0.03:
        out["label"] = "Attractive vs. bonds"
    elif spread > 0.01:
        out["label"] = "Slightly attractive"
    elif spread > -0.01:
        out["label"] = "Neutral"
    elif spread > -0.03:
        out["label"] = "Below risk-free rate"
    else:
        out["label"] = "Significantly below bonds"
    return out


def compute_ev_ebit_yield(data: Dict[str, Any]) -> Dict:
    """
    EV/EBIT Earnings Yield = EBIT / EV.
    Capital-structure neutral; harder to manipulate than P/E.
    """
    out = {"ev_ebit": None, "earnings_yield_pct": None,
           "sector_ev_ebit": None, "score": 50.0, "label": "N/A"}

    ebit = data.get("ebit")
    ev = data.get("enterprise_value")
    sector = data.get("sector", "Unknown")

    if not ebit or not ev or ev <= 0:
        out["label"] = "No EBIT/EV data"
        return out

    ev_ebit = ev / ebit
    ey = ebit / ev  # earnings yield

    out["ev_ebit"] = round(ev_ebit, 1)
    out["earnings_yield_pct"] = round(ey * 100, 2)

    sector_median = SECTOR_EV_EBITDA_MEDIANS.get(sector, 15)
    out["sector_ev_ebit"] = sector_median

    # Score relative to sector: EV/EBIT << sector median → cheap → high score
    ratio = ev_ebit / sector_median
    score = np.clip(100 - ratio * 50, 0, 100)
    out["score"] = round(float(score), 1)

    if ratio < 0.75:
        out["label"] = "Cheap vs. sector"
    elif ratio < 0.95:
        out["label"] = "Slightly cheap"
    elif ratio < 1.15:
        out["label"] = "In-line with sector"
    elif ratio < 1.40:
        out["label"] = "Expensive"
    else:
        out["label"] = "Very expensive"
    return out


def compute_composite_multiples(data: Dict[str, Any]) -> Dict:
    """
    Collapse P/E, EV/EBITDA, P/S, P/FCF into a single composite value score.
    Each is scored vs. sector median; average = composite.
    """
    sector = data.get("sector", "Unknown")
    sector_pe = SECTOR_PE_MEDIANS.get(sector, 20)
    sector_ev_ebitda = SECTOR_EV_EBITDA_MEDIANS.get(sector, 15)

    scores = []
    details = {}

    # P/E
    pe = data.get("trailing_pe") or data.get("forward_pe")
    if pe and pe > 0:
        s = np.clip(100 - (pe / sector_pe) * 50, 0, 100)
        scores.append(float(s))
        details["P/E"] = {"value": round(pe, 1), "sector_median": sector_pe,
                          "signal": "Cheap" if pe < sector_pe * 0.85 else
                                    ("Fair" if pe < sector_pe * 1.15 else "Expensive")}

    # EV/EBITDA
    ev_ebitda = data.get("ev_to_ebitda")
    if ev_ebitda and ev_ebitda > 0:
        s = np.clip(100 - (ev_ebitda / sector_ev_ebitda) * 50, 0, 100)
        scores.append(float(s))
        details["EV/EBITDA"] = {"value": round(ev_ebitda, 1),
                                 "sector_median": sector_ev_ebitda,
                                 "signal": "Cheap" if ev_ebitda < sector_ev_ebitda * 0.85 else
                                           ("Fair" if ev_ebitda < sector_ev_ebitda * 1.15 else "Expensive")}

    # P/S
    ps = data.get("price_to_sales")
    sector_ps = {"Technology": 5, "Healthcare": 4, "Consumer Cyclical": 1.5,
                 "Consumer Defensive": 1.2, "Financials": 2.5,
                 "Financial Services": 2.5, "Industrials": 1.5,
                 "Energy": 1.0, "Utilities": 2.0, "Unknown": 2.0}.get(sector, 2.0)
    if ps and ps > 0:
        s = np.clip(100 - (ps / sector_ps) * 50, 0, 100)
        scores.append(float(s))
        details["P/S"] = {"value": round(ps, 2), "sector_median": sector_ps,
                          "signal": "Cheap" if ps < sector_ps * 0.85 else
                                    ("Fair" if ps < sector_ps * 1.15 else "Expensive")}

    # P/FCF
    fcf = data.get("fcf")
    market_cap = data.get("market_cap")
    if fcf and fcf > 0 and market_cap:
        p_fcf = market_cap / fcf
        s = np.clip(100 - (p_fcf / 20) * 50, 0, 100)  # 20x FCF ≈ fair
        scores.append(float(s))
        details["P/FCF"] = {"value": round(p_fcf, 1), "sector_median": 20,
                             "signal": "Cheap" if p_fcf < 15 else
                                       ("Fair" if p_fcf < 25 else "Expensive")}

    composite_score = float(np.mean(scores)) if scores else 50.0
    signals = [d["signal"] for d in details.values()]
    n_exp = signals.count("Expensive")
    n_cheap = signals.count("Cheap")

    label = ("Very expensive" if n_exp >= 3 else
             "Expensive" if n_exp >= 2 else
             "Slightly expensive" if n_exp == 1 else
             "Cheap" if n_cheap >= 2 else "Fair value")

    return {"score": round(composite_score, 1), "label": label, "details": details}


def compute(data: Dict[str, Any]) -> Dict:
    """Compute the consolidated VALUE pillar score (0–100)."""
    inv_dcf = compute_inverse_dcf(data)
    fcf_y = compute_fcf_yield(data)
    ev_ebit = compute_ev_ebit_yield(data)
    multiples = compute_composite_multiples(data)

    # Weighted average within pillar
    weights = {"inv_dcf": 0.30, "fcf_yield": 0.30, "ev_ebit": 0.20, "multiples": 0.20}
    pillar_score = (
        inv_dcf["score"] * weights["inv_dcf"]
        + fcf_y["score"] * weights["fcf_yield"]
        + ev_ebit["score"] * weights["ev_ebit"]
        + multiples["score"] * weights["multiples"]
    )

    return {
        "pillar": "Value",
        "score": round(pillar_score, 1),
        "weight": 0.30,
        "components": {
            "inverse_dcf": inv_dcf,
            "fcf_yield": fcf_y,
            "ev_ebit_yield": ev_ebit,
            "composite_multiples": multiples,
        },
    }
