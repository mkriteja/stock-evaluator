import pytest
import pandas as pd
import numpy as np
from pillars.value import compute_inverse_dcf, compute_fcf_yield, compute_ev_ebit_yield, compute_composite_multiples, compute

def test_compute_inverse_dcf():
    data = {
        "market_cap": 100000,
        "fcf": 5000,
    }
    # To get historical growth, we need cashflow statement
    cf = pd.DataFrame({"Free Cash Flow": [5000, 4800, 4500]}, index=["2023", "2022", "2021"]).T
    data["cashflow"] = cf

    result = compute_inverse_dcf(data)
    assert result["implied_growth_pct"] is not None
    assert result["historical_growth_pct"] > 0
    assert result["score"] >= 0 and result["score"] <= 100

def test_compute_inverse_dcf_missing_data():
    data = {}
    result = compute_inverse_dcf(data)
    assert result["implied_growth_pct"] is None
    assert result["label"] == "N/A"
    assert result["score"] == 50.0

def test_compute_fcf_yield():
    data = {
        "fcf": 10000,
        "market_cap": 100000
    }
    result = compute_fcf_yield(data)
    assert result["fcf_yield_pct"] == 10.0
    assert result["spread_pp"] == 5.7  # 10.0 - 4.3
    assert result["score"] > 50

def test_compute_fcf_yield_negative_fcf():
    data = {
        "fcf": -10000,
        "market_cap": 100000
    }
    result = compute_fcf_yield(data)
    assert result["score"] < 50
    assert "below bonds" in result["label"].lower()

def test_compute_ev_ebit_yield():
    data = {
        "enterprise_value": 50000,
        "ebitda": 6000,
        "ebit": 5000,
        "sector_ev_ebit": 15.0
    }
    result = compute_ev_ebit_yield(data)
    assert result["ev_ebit"] == 10.0
    assert result["earnings_yield_pct"] == 10.0
    assert result["score"] > 50

def test_compute_composite_multiples():
    data = {
        "trailing_pe": 15.0,
        "forward_pe": 12.0,
        "price_to_sales": 2.0,
        "ev_to_ebitda": 10.0,
        "market_cap": 100000,
        "fcf": 5000
    }
    result = compute_composite_multiples(data)
    assert "P/E" in result["details"]
    assert "EV/EBITDA" in result["details"]
    assert result["score"] > 0

def test_value_compute_overall():
    data = {
        "fcf": 5000,
        "market_cap": 100000,
        "enterprise_value": 50000,
        "ebit": 5000,
        "trailing_pe": 15.0,
        "ev_to_ebitda": 10.0,
        "price_to_sales": 2.0
    }
    result = compute(data)
    assert result["pillar"] == "Value"
    assert "components" in result
    assert result["score"] >= 0 and result["score"] <= 100
