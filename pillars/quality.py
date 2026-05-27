"""
pillars/quality.py — QUALITY pillar (25% weight)

Three signals:
  1. Piotroski F-Score  — 9-point academic quality checklist (Piotroski 2000)
  2. Magic Formula ROC  — Return on Capital = EBIT / (Net PPE + NWC)
  3. ROIC trend         — Is return on invested capital improving?
"""

import numpy as np
from typing import Any, Dict, Optional


def _safe(val) -> Optional[float]:
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def compute_piotroski(data: Dict[str, Any]) -> Dict:
    """
    9-point Piotroski F-Score:
      Profitability (4): ROA>0, CFO>0, ΔROA>0, Accruals (CFO>NI/Assets)
      Leverage/Liquidity (3): ΔLeverage<0, ΔLiquidity>0, No dilution
      Efficiency (2): ΔGross Margin>0, ΔAsset Turnover>0
    """
    checks = {}
    score = 0

    total_assets = _safe(data.get("total_assets"))
    total_assets_p = _safe(data.get("total_assets_prior"))
    net_income = _safe(data.get("net_income"))
    ocf = _safe(data.get("ocf"))
    revenue = _safe(data.get("revenue"))
    revenue_p = _safe(data.get("revenue_prior"))
    gross_profit = _safe(data.get("gross_profit"))
    gross_profit_p = _safe(data.get("gross_profit_prior"))
    long_term_debt = _safe(data.get("long_term_debt"))
    long_term_debt_p = _safe(data.get("long_term_debt_prior"))
    cur_assets = _safe(data.get("current_assets"))
    cur_assets_p = _safe(data.get("current_assets_prior"))
    cur_liab = _safe(data.get("current_liabilities"))
    cur_liab_p = _safe(data.get("current_liabilities_prior"))
    shares = _safe(data.get("shares_bs")) or _safe(data.get("shares_outstanding"))
    shares_p = _safe(data.get("shares_bs_prior"))

    # ── Profitability ─────────────────────────────────────────────────────────
    # F1: ROA > 0
    roa = (net_income / total_assets) if net_income and total_assets else None
    f1 = 1 if (roa is not None and roa > 0) else 0
    checks["F1 ROA > 0"] = ("✓" if f1 else "✗", f"{roa*100:.2f}%" if roa else "N/A")
    score += f1

    # F2: Operating CF > 0
    f2 = 1 if (ocf is not None and ocf > 0) else 0
    checks["F2 CFO > 0"] = ("✓" if f2 else "✗", f"${ocf/1e9:.2f}B" if ocf else "N/A")
    score += f2

    # F3: ΔROA > 0 (ROA improving)
    net_income_p = _safe(data.get("net_income_prior"))
    roa_p = (net_income_p / total_assets_p) if net_income_p and total_assets_p else None
    f3 = 1 if (roa and roa_p and roa > roa_p) else 0
    checks["F3 ΔROA > 0"] = ("✓" if f3 else "✗",
                              f"{roa_p*100:.2f}% → {roa*100:.2f}%" if (roa and roa_p) else "N/A")
    score += f3

    # F4: Accruals = CFO/Assets > ROA (cash earnings quality)
    accruals = (ocf / total_assets) if ocf and total_assets else None
    f4 = 1 if (accruals and roa and accruals > roa) else 0
    checks["F4 Accruals (CFO>NI)"] = ("✓" if f4 else "✗",
                                       f"CFO/Assets={accruals*100:.1f}% vs ROA={roa*100:.1f}%"
                                       if (accruals and roa) else "N/A")
    score += f4

    # ── Leverage / Liquidity ──────────────────────────────────────────────────
    # F5: Long-term debt ratio decreasing
    lev = (long_term_debt / total_assets) if long_term_debt and total_assets else None
    lev_p = (long_term_debt_p / total_assets_p) if long_term_debt_p and total_assets_p else None
    f5 = 1 if (lev is not None and lev_p is not None and lev < lev_p) else 0
    checks["F5 ΔLeverage < 0"] = ("✓" if f5 else "✗",
                                   f"{lev_p*100:.1f}% → {lev*100:.1f}%"
                                   if (lev and lev_p) else "N/A")
    score += f5

    # F6: Current ratio improving
    cr = (cur_assets / cur_liab) if cur_assets and cur_liab else None
    cr_p = (cur_assets_p / cur_liab_p) if cur_assets_p and cur_liab_p else None
    f6 = 1 if (cr is not None and cr_p is not None and cr > cr_p) else 0
    checks["F6 ΔLiquidity > 0"] = ("✓" if f6 else "✗",
                                    f"{cr_p:.2f}x → {cr:.2f}x" if (cr and cr_p) else "N/A")
    score += f6

    # F7: No share dilution
    f7 = 1 if (shares is not None and shares_p is not None and shares <= shares_p * 1.01) else 0
    checks["F7 No Dilution"] = ("✓" if f7 else "✗",
                                f"{shares_p/1e9:.2f}B → {shares/1e9:.2f}B"
                                if (shares and shares_p) else "N/A")
    score += f7

    # ── Operating Efficiency ──────────────────────────────────────────────────
    # F8: Gross margin improving
    gm = (gross_profit / revenue) if gross_profit and revenue else None
    gm_p = (gross_profit_p / revenue_p) if gross_profit_p and revenue_p else None
    f8 = 1 if (gm and gm_p and gm > gm_p) else 0
    checks["F8 ΔGross Margin > 0"] = ("✓" if f8 else "✗",
                                       f"{gm_p*100:.1f}% → {gm*100:.1f}%"
                                       if (gm and gm_p) else "N/A")
    score += f8

    # F9: Asset turnover improving
    at_ = (revenue / total_assets) if revenue and total_assets else None
    at_p = (revenue_p / total_assets_p) if revenue_p and total_assets_p else None
    f9 = 1 if (at_ and at_p and at_ > at_p) else 0
    checks["F9 ΔAsset Turnover > 0"] = ("✓" if f9 else "✗",
                                          f"{at_p:.2f}x → {at_:.2f}x"
                                          if (at_ and at_p) else "N/A")
    score += f9

    # Normalized score 0–100
    normalized = round((score / 9) * 100, 1)
    if score >= 8:
        label = "Financially strong"
    elif score >= 6:
        label = "Above average"
    elif score >= 4:
        label = "Average"
    elif score >= 2:
        label = "Weak — value trap risk"
    else:
        label = "Distressed"

    return {"raw_score": score, "max_score": 9, "score": normalized,
            "label": label, "checks": checks}


def compute_magic_formula_roc(data: Dict[str, Any]) -> Dict:
    """
    Return on Capital = EBIT / (Net PPE + Net Working Capital)
    Greenblatt's quality metric — how efficiently does the business use capital?
    """
    out = {"roc_pct": None, "score": 50.0, "label": "N/A", "ebit": None,
           "net_ppe": None, "nwc": None}

    ebit = _safe(data.get("ebit"))
    net_ppe = _safe(data.get("net_ppe"))
    nwc = _safe(data.get("net_working_capital"))

    out["ebit"] = ebit
    out["net_ppe"] = net_ppe
    out["nwc"] = nwc

    if ebit is None:
        out["label"] = "No EBIT data"
        return out

    invested_capital = (net_ppe or 0) + (nwc or 0)
    if invested_capital <= 0:
        # Asset-light businesses can have negative NWC (e.g. retailers, tech)
        # Use total assets as fallback
        total_assets = _safe(data.get("total_assets"))
        total_debt = _safe(data.get("total_debt")) or 0
        if total_assets:
            invested_capital = total_assets - total_debt
        else:
            out["label"] = "Cannot compute invested capital"
            return out

    roc = ebit / abs(invested_capital)
    out["roc_pct"] = round(roc * 100, 1)

    # Score: >25% ROC → excellent (90+); <5% → poor (<30)
    score = np.clip((roc - 0.05) / (0.30 - 0.05) * 80 + 20, 0, 100)
    out["score"] = round(float(score), 1)

    if roc > 0.30:
        out["label"] = "Exceptional capital efficiency"
    elif roc > 0.20:
        out["label"] = "High ROC — strong moat signal"
    elif roc > 0.12:
        out["label"] = "Above average"
    elif roc > 0.06:
        out["label"] = "Average"
    else:
        out["label"] = "Poor capital allocation"

    return out


def compute_roic_trend(data: Dict[str, Any]) -> Dict:
    """
    Is ROIC (Return on Invested Capital) improving year-over-year?
    Uses net income / (total assets - current liabilities) as a proxy.
    """
    out = {"roic_current_pct": None, "roic_prior_pct": None,
           "trend": "N/A", "score": 50.0, "label": "N/A"}

    net_income = _safe(data.get("net_income"))
    total_assets = _safe(data.get("total_assets"))
    cur_liab = _safe(data.get("current_liabilities"))
    net_income_p = _safe(data.get("net_income_prior"))
    total_assets_p = _safe(data.get("total_assets_prior"))
    cur_liab_p = _safe(data.get("current_liabilities_prior"))

    def roic(ni, ta, cl):
        ic = ta - (cl or 0)
        if ic <= 0:
            return None
        return ni / ic

    r_cur = roic(net_income, total_assets, cur_liab)
    r_pri = roic(net_income_p, total_assets_p, cur_liab_p)

    if r_cur is not None:
        out["roic_current_pct"] = round(r_cur * 100, 1)
    if r_pri is not None:
        out["roic_prior_pct"] = round(r_pri * 100, 1)

    if r_cur is None:
        out["label"] = "Insufficient data"
        return out

    # Absolute ROIC score
    abs_score = float(np.clip((r_cur - 0.05) / (0.25 - 0.05) * 70 + 20, 0, 100))

    # Trend bonus/penalty
    trend_bonus = 0.0
    if r_cur is not None and r_pri is not None:
        delta = r_cur - r_pri
        out["trend"] = f"{'+' if delta >= 0 else ''}{delta*100:.1f}pp YoY"
        trend_bonus = float(np.clip(delta * 500, -20, 20))
        out["label"] = ("Improving ↑" if delta > 0.005 else
                        "Stable →" if abs(delta) <= 0.005 else "Declining ↓")
    else:
        out["label"] = f"ROIC: {r_cur*100:.1f}%"

    out["score"] = round(np.clip(abs_score + trend_bonus, 0, 100), 1)
    return out


def compute(data: Dict[str, Any]) -> Dict:
    """Compute the QUALITY pillar score (0–100)."""
    piotroski = compute_piotroski(data)
    roc = compute_magic_formula_roc(data)
    roic = compute_roic_trend(data)

    weights = {"piotroski": 0.50, "roc": 0.30, "roic": 0.20}
    pillar_score = (
        piotroski["score"] * weights["piotroski"]
        + roc["score"] * weights["roc"]
        + roic["score"] * weights["roic"]
    )

    return {
        "pillar": "Quality",
        "score": round(pillar_score, 1),
        "weight": 0.25,
        "components": {
            "piotroski_f_score": piotroski,
            "magic_formula_roc": roc,
            "roic_trend": roic,
        },
    }
