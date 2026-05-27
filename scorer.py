"""
scorer.py — Composite 4-pillar weighted scoring engine.

Default weights (adjustable via CLI):
  Value    30%
  Quality  25%
  Growth   20%
  Momentum 25%
"""

from typing import Dict, Any


SIGNAL_THRESHOLDS = [
    (80, "Strong Buy",  "🟢"),
    (65, "Buy",         "🟢"),
    (55, "Watch / Hold","🟡"),
    (40, "Sell",        "🔴"),
    (0,  "Strong Sell", "🔴"),
]


def score_to_signal(score: float):
    for threshold, label, icon in SIGNAL_THRESHOLDS:
        if score >= threshold:
            return label, icon
    return "Strong Sell", "🔴"


def score_to_bar(score: float, width: int = 30) -> str:
    """ASCII progress bar."""
    filled = int(round(score / 100 * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.0f}/100"


def compute_composite(
    value_result: Dict,
    quality_result: Dict,
    growth_result: Dict,
    momentum_result: Dict,
    weights: Dict[str, float] = None,
) -> Dict[str, Any]:
    """
    Combine 4 pillar scores into a single composite with custom weights.
    weights: dict with keys 'value', 'quality', 'growth', 'momentum' summing to 1.0
    """
    if weights is None:
        weights = {"value": 0.30, "quality": 0.25, "growth": 0.20, "momentum": 0.25}

    # Normalize weights to sum to 1.0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    scores = {
        "value": value_result.get("score", 50.0),
        "quality": quality_result.get("score", 50.0),
        "growth": growth_result.get("score", 50.0),
        "momentum": momentum_result.get("score", 50.0),
    }

    composite = sum(scores[k] * weights[k] for k in weights)
    composite = round(composite, 1)

    signal, icon = score_to_signal(composite)

    # Build pillar summary rows
    pillar_summary = []
    for key, result in [
        ("value", value_result),
        ("quality", quality_result),
        ("growth", growth_result),
        ("momentum", momentum_result),
    ]:
        s = scores[key]
        sig, ic = score_to_signal(s)
        pillar_summary.append({
            "pillar": result.get("pillar", key.title()),
            "score": s,
            "weight_pct": round(weights[key] * 100),
            "signal": sig,
            "icon": ic,
            "bar": score_to_bar(s, width=20),
        })

    # Key insight string
    strong_pillars = [p["pillar"] for p in pillar_summary if p["score"] >= 65]
    weak_pillars = [p["pillar"] for p in pillar_summary if p["score"] <= 40]

    if strong_pillars and weak_pillars:
        insight = f"Strong {', '.join(strong_pillars)} offset by weak {', '.join(weak_pillars)}."
    elif strong_pillars:
        insight = f"Broadly positive across {', '.join(strong_pillars)}."
    elif weak_pillars:
        insight = f"Weakness across {', '.join(weak_pillars)}."
    else:
        insight = "Mixed signals across all pillars."

    return {
        "composite_score": composite,
        "signal": signal,
        "icon": icon,
        "bar": score_to_bar(composite, width=30),
        "weights": weights,
        "pillar_scores": scores,
        "pillar_summary": pillar_summary,
        "insight": insight,
    }
