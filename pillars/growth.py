"""
pillars/growth.py — GROWTH pillar (20% weight)

Three signals:
  1. PEG Ratio         — P/E contextualized by earnings growth (< 1 = value+growth)
  2. EPS Revision      — Analyst EPS estimate trend (forward vs. trailing; upgrades)
  3. Revenue Growth    — 3-year revenue CAGR from income statements
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional
from datetime import datetime, timedelta


def _safe(val) -> Optional[float]:
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def compute_peg_ratio(data: Dict[str, Any]) -> Dict:
    """
    PEG = P/E / EPS Growth Rate (%).
    < 1.0 → potentially undervalued relative to growth
    1.0–2.0 → fair
    > 2.0 → expensive relative to growth
    """
    out = {"peg": None, "pe": None, "growth_pct": None,
           "score": 50.0, "label": "N/A", "source": ""}

    # Prefer yfinance provided PEG first
    peg = _safe(data.get("peg_ratio"))
    pe = _safe(data.get("trailing_pe")) or _safe(data.get("forward_pe"))

    if peg and peg > 0:
        out["peg"] = round(peg, 2)
        out["pe"] = round(pe, 1) if pe else None
        out["source"] = "Analyst consensus"
        # Infer growth from PE / PEG
        if pe and pe > 0:
            out["growth_pct"] = round((pe / peg), 1)
    elif pe and pe > 0:
        # Compute PEG manually from earnings growth
        eg = _safe(data.get("earnings_growth"))  # yoy from yfinance info
        if eg and eg > 0:
            peg = pe / (eg * 100)
            out["peg"] = round(peg, 2)
            out["pe"] = round(pe, 1)
            out["growth_pct"] = round(eg * 100, 1)
            out["source"] = "Computed from yfinance earningsGrowth"
        else:
            out["label"] = "No growth rate available"
            out["pe"] = round(pe, 1)
            return out
    else:
        out["label"] = "No P/E data"
        return out

    # Score: PEG < 0.75 → 90+; PEG = 1 → 60; PEG = 2 → 30; PEG > 3 → 0
    peg_val = out["peg"]
    score = np.clip(100 - (peg_val - 0.5) * 35, 0, 100)
    out["score"] = round(float(score), 1)

    if peg_val < 0.75:
        out["label"] = "Undervalued vs growth (PEG<0.75)"
    elif peg_val < 1.0:
        out["label"] = "Reasonable (PEG<1)"
    elif peg_val < 1.5:
        out["label"] = "Fair (PEG 1–1.5)"
    elif peg_val < 2.0:
        out["label"] = "Slightly expensive (PEG 1.5–2)"
    else:
        out["label"] = f"Expensive vs growth (PEG={peg_val:.1f})"
    return out


def compute_eps_revision(data: Dict[str, Any]) -> Dict:
    """
    Earnings revision momentum:
      - Forward EPS vs. Trailing EPS (analyst estimate direction)
      - Recent analyst upgrades/downgrades (last 90 days)
      - Earnings surprise from most recent quarters
    """
    out = {"forward_eps": None, "trailing_eps": None, "eps_revision_pct": None,
           "recent_upgrades": 0, "recent_downgrades": 0,
           "avg_surprise_pct": None, "score": 50.0, "label": "N/A"}

    fwd_eps = _safe(data.get("forward_eps"))
    trail_eps = _safe(data.get("trailing_eps"))

    # EPS direction signal
    eps_score_components = []

    if fwd_eps and trail_eps and trail_eps > 0:
        revision_pct = (fwd_eps - trail_eps) / abs(trail_eps) * 100
        out["forward_eps"] = round(fwd_eps, 2)
        out["trailing_eps"] = round(trail_eps, 2)
        out["eps_revision_pct"] = round(revision_pct, 1)
        # Score: +20% revision → 85; 0% → 60; -20% → 35
        s = np.clip(60 + revision_pct * 1.25, 0, 100)
        eps_score_components.append(float(s))

    # Analyst upgrades/downgrades in last 90 days
    upg_dg = data.get("upgrades_downgrades", pd.DataFrame())
    if not upg_dg.empty:
        try:
            cutoff = datetime.now() - timedelta(days=90)
            upg_dg = upg_dg.copy()
            upg_dg.index = pd.to_datetime(upg_dg.index, utc=True).tz_localize(None) \
                if upg_dg.index.tzinfo is None else pd.to_datetime(upg_dg.index).dt.tz_localize(None)
            recent = upg_dg[upg_dg.index >= pd.Timestamp(cutoff)]
            if "Action" in recent.columns:
                upgrades = recent["Action"].str.lower().str.contains("up|buy|outperform|overweight", na=False).sum()
                downgrades = recent["Action"].str.lower().str.contains("down|sell|underperform|underweight", na=False).sum()
            elif "To Grade" in recent.columns:
                upgrades = recent["To Grade"].str.lower().str.contains("buy|outperform|overweight|strong", na=False).sum()
                downgrades = recent["To Grade"].str.lower().str.contains("sell|underperform|underweight|reduce", na=False).sum()
            else:
                upgrades = downgrades = 0
            out["recent_upgrades"] = int(upgrades)
            out["recent_downgrades"] = int(downgrades)
            net = int(upgrades) - int(downgrades)
            total = int(upgrades) + int(downgrades)
            if total > 0:
                upgrade_ratio = net / total  # -1 to +1
                s = float(np.clip(50 + upgrade_ratio * 40, 10, 90))
                eps_score_components.append(s)
        except Exception:
            pass

    # Earnings surprise from recent quarters
    eh = data.get("earnings_history", pd.DataFrame())
    if not eh.empty and "surprisePercent" in eh.columns:
        try:
            recent_surprise = eh["surprisePercent"].dropna().head(4)
            if len(recent_surprise) > 0:
                avg_surp = float(recent_surprise.mean())
                out["avg_surprise_pct"] = round(avg_surp, 1)
                # Score: +5% avg surprise → 80; 0% → 60; -5% → 40
                s = np.clip(60 + avg_surp * 4, 0, 100)
                eps_score_components.append(float(s))
        except Exception:
            pass

    if eps_score_components:
        final_score = float(np.mean(eps_score_components))
        out["score"] = round(final_score, 1)
        r = out.get("eps_revision_pct", 0) or 0
        avg_s = out.get("avg_surprise_pct", 0) or 0
        net_upg = out["recent_upgrades"] - out["recent_downgrades"]
        if r > 10 or avg_s > 5 or net_upg > 3:
            out["label"] = "Strong upward revisions"
        elif r > 3 or avg_s > 2:
            out["label"] = "Modest positive revisions"
        elif r < -10 or avg_s < -5:
            out["label"] = "Significant downward revisions"
        elif r < -3:
            out["label"] = "Slight downward pressure"
        else:
            out["label"] = "Stable estimates"
    else:
        out["label"] = "Insufficient analyst data"

    return out


def compute_revenue_growth(data: Dict[str, Any]) -> Dict:
    """
    3-year revenue CAGR from annual income statements.
    Falls back to yfinance info revenueGrowth (1-year YoY) if needed.
    """
    out = {"cagr_3yr_pct": None, "yoy_pct": None, "score": 50.0, "label": "N/A"}

    # Try multi-year CAGR from income statement
    IS = data.get("income_stmt", pd.DataFrame())
    cagr = None
    if IS is not None and not IS.empty:
        try:
            for row in ["Total Revenue", "Revenue"]:
                if row in IS.index:
                    rev_series = IS.loc[row].dropna()
                    if len(rev_series) >= 3:
                        r_now = float(rev_series.iloc[0])
                        r_old = float(rev_series.iloc[min(3, len(rev_series) - 1)])
                        yrs = min(3, len(rev_series) - 1)
                        if r_old > 0 and yrs > 0:
                            cagr = (r_now / r_old) ** (1 / yrs) - 1
                    break
        except Exception:
            pass

    if cagr is not None:
        out["cagr_3yr_pct"] = round(cagr * 100, 1)

    # YoY from yfinance info
    yoy = _safe(data.get("revenue_growth"))
    if yoy is not None:
        out["yoy_pct"] = round(yoy * 100, 1)

    growth = cagr if cagr is not None else yoy

    if growth is None:
        out["label"] = "No revenue data"
        return out

    # Score: >25% CAGR → 90; 10–15% → 65; 0% → 50; negative → <40
    score = np.clip(50 + growth * 200, 0, 100)
    out["score"] = round(float(score), 1)

    if growth > 0.25:
        out["label"] = "Hypergrowth (>25%)"
    elif growth > 0.15:
        out["label"] = "High growth (15–25%)"
    elif growth > 0.08:
        out["label"] = "Solid growth (8–15%)"
    elif growth > 0.02:
        out["label"] = "Modest growth (2–8%)"
    elif growth >= 0:
        out["label"] = "Flat (<2%)"
    else:
        out["label"] = f"Declining ({growth*100:.1f}%)"

    return out


def compute(data: Dict[str, Any]) -> Dict:
    """Compute the GROWTH pillar score (0–100)."""
    peg = compute_peg_ratio(data)
    eps_rev = compute_eps_revision(data)
    rev_growth = compute_revenue_growth(data)

    weights = {"peg": 0.35, "eps_revision": 0.40, "revenue_growth": 0.25}
    pillar_score = (
        peg["score"] * weights["peg"]
        + eps_rev["score"] * weights["eps_revision"]
        + rev_growth["score"] * weights["revenue_growth"]
    )

    return {
        "pillar": "Growth",
        "score": round(pillar_score, 1),
        "weight": 0.20,
        "components": {
            "peg_ratio": peg,
            "eps_revision": eps_rev,
            "revenue_growth": rev_growth,
        },
    }
