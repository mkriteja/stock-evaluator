import pytest
from scorer import score_to_signal, score_to_bar, compute_composite

def test_score_to_signal():
    label, icon = score_to_signal(90)
    assert label == "Strong Buy"
    assert icon == "🟢"
    
    label, icon = score_to_signal(30)
    assert label == "Strong Sell"
    assert icon == "🔴"

def test_score_to_bar():
    bar = score_to_bar(50, width=10)
    assert "█" * 5 in bar
    assert "░" * 5 in bar

def test_compute_composite():
    v = {"score": 80, "pillar": "Value"}
    q = {"score": 90, "pillar": "Quality"}
    g = {"score": 70, "pillar": "Growth"}
    m = {"score": 60, "pillar": "Momentum"}
    
    weights = {"value": 0.25, "quality": 0.25, "growth": 0.25, "momentum": 0.25}
    
    result = compute_composite(v, q, g, m, weights)
    
    assert result["composite_score"] == 75.0
    assert result["signal"] == "Buy"
    assert len(result["pillar_summary"]) == 4
    assert result["insight"] is not None

def test_compute_composite_default_weights():
    v = {"score": 100}
    q = {"score": 100}
    g = {"score": 100}
    m = {"score": 100}
    
    result = compute_composite(v, q, g, m)
    assert result["composite_score"] == 100.0
