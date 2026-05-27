import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pillars.growth import compute_peg_ratio, compute_eps_revision, compute_revenue_growth, compute

def test_compute_peg_ratio():
    data = {
        "peg_ratio": 1.5,
        "trailing_pe": 30.0
    }
    result = compute_peg_ratio(data)
    assert result["peg"] == 1.5
    assert result["pe"] == 30.0
    assert result["growth_pct"] == 20.0
    assert result["score"] <= 65

def test_compute_peg_ratio_fallback():
    data = {
        "trailing_pe": 20.0,
        "earnings_growth": 0.25
    }
    result = compute_peg_ratio(data)
    assert result["peg"] == 0.8
    assert result["pe"] == 20.0
    assert result["score"] > 80

def test_compute_eps_revision():
    data = {
        "forward_eps": 5.0,
        "trailing_eps": 4.0
    }
    # Create upgrades/downgrades df for last 90 days
    today = pd.Timestamp(datetime.now())
    upg_dg = pd.DataFrame({
        "Action": ["up", "down", "up", "maintains"],
        "To Grade": ["Buy", "Sell", "Buy", "Hold"]
    }, index=[today, today, today - timedelta(days=100), today])
    data["upgrades_downgrades"] = upg_dg

    eh = pd.DataFrame({"surprisePercent": [0.05, 0.02, -0.01, 0.04]})
    data["earnings_history"] = eh

    result = compute_eps_revision(data)
    assert result["forward_eps"] == 5.0
    assert result["eps_revision_pct"] == 25.0
    assert result["recent_upgrades"] == 1
    assert result["recent_downgrades"] == 1
    assert result["avg_surprise_pct"] == 0.0
    assert result["score"] > 60

def test_compute_revenue_growth():
    IS = pd.DataFrame({
        "Total Revenue": [13000, 12000, 11000, 10000]
    }, index=["2023", "2022", "2021", "2020"]).T
    
    data = {
        "income_stmt": IS,
        "revenue_growth": 0.08
    }
    result = compute_revenue_growth(data)
    assert result["cagr_3yr_pct"] == 9.1
    assert result["score"] > 50

def test_growth_compute_overall():
    data = {
        "peg_ratio": 1.0,
        "trailing_pe": 20.0,
        "forward_eps": 5.0,
        "trailing_eps": 4.0,
        "revenue_growth": 0.15
    }
    result = compute(data)
    assert result["pillar"] == "Growth"
    assert "components" in result
    assert result["score"] >= 0 and result["score"] <= 100
