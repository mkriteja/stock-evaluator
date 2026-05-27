import pytest
import pandas as pd
import numpy as np
from pillars.quality import compute_piotroski, compute_magic_formula_roc, compute_roic_trend, compute

def test_compute_piotroski_f_score():
    financials = pd.DataFrame({
        "Net Income": [1000, 1200],
        "Operating Cash Flow": [1500, 1600],
        "Total Assets": [10000, 11000],
        "Long Term Debt": [2000, 1800],
        "Current Assets": [3000, 3500],
        "Current Liabilities": [1500, 1600],
        "Ordinary Shares Number": [1000, 1000],
        "Gross Profit": [4000, 4800],
        "Total Revenue": [10000, 12000]
    }, index=["2022-12-31", "2023-12-31"]).T

    data = {"financials": financials}
    result = compute_piotroski(data)
    assert result["raw_score"] is not None
    assert "F1 ROA > 0" in result["checks"]
    assert result["score"] >= 0 and result["score"] <= 100

def test_compute_piotroski_empty():
    result = compute_piotroski({"financials": pd.DataFrame()})
    assert result["raw_score"] == 0
    assert result["score"] == 0.0

def test_compute_magic_formula_roc():
    data = {
        "ebit": 1000,
        "net_working_capital": 2000,
        "net_ppe": 3000
    }
    result = compute_magic_formula_roc(data)
    assert result["roc_pct"] == 20.0
    assert result["score"] > 50

def test_compute_magic_formula_roc_fallback():
    data = {
        "ebit": 1500,
        "total_assets": 15000,
        "total_debt": 5000
    }
    result = compute_magic_formula_roc(data)
    assert result["roc_pct"] == 15.0

def test_compute_roic_trend():
    data = {
        "net_income": 150,
        "total_assets": 1200,
        "current_liabilities": 200,
        "net_income_prior": 120,
        "total_assets_prior": 1100,
        "current_liabilities_prior": 100
    }
    result = compute_roic_trend(data)
    assert result["roic_current_pct"] == 15.0
    assert result["roic_prior_pct"] == 12.0
    assert "Improving" in result["label"]
    assert result["score"] > 50

def test_quality_compute_overall():
    financials = pd.DataFrame({
        "Net Income": [1000, 1200],
        "Operating Cash Flow": [1500, 1600],
        "Total Assets": [10000, 11000],
        "Long Term Debt": [2000, 1800],
        "Current Assets": [3000, 3500],
        "Current Liabilities": [1500, 1600],
        "Ordinary Shares Number": [1000, 1000],
        "Gross Profit": [4000, 4800],
        "Total Revenue": [10000, 12000]
    }, index=["2022-12-31", "2023-12-31"]).T

    data = {
        "financials": financials,
        "ebit": 1000,
        "net_working_capital": 2000,
        "net_ppe": 3000,
        "net_income": 150,
        "total_assets": 1200,
        "current_liabilities": 200,
        "net_income_prior": 120,
        "total_assets_prior": 1100,
        "current_liabilities_prior": 100
    }
    result = compute(data)
    assert result["pillar"] == "Quality"
    assert "components" in result
    assert result["score"] >= 0 and result["score"] <= 100
