import pytest
import pandas as pd
import numpy as np
from pillars.momentum import compute_price_momentum, compute_ema_regime, compute_macd_signal, compute_volume_trend, compute_market_regime, compute

def test_compute_price_momentum():
    np.random.seed(42)
    # create 260 days of mock price data with an upward trend
    prices = np.linspace(100, 150, 260) + np.random.normal(0, 1, 260)
    hist = pd.DataFrame({"Close": prices})
    
    result = compute_price_momentum(hist)
    assert result["ret_1m"] is not None
    assert result["ret_12m1m"] > 0
    assert result["score"] > 50

def test_compute_ema_regime():
    np.random.seed(42)
    prices = np.linspace(100, 150, 260) + np.random.normal(0, 1, 260)
    hist = pd.DataFrame({"Close": prices})
    
    result = compute_ema_regime(hist, week52_high=160, current_price=150)
    assert result["ema20"] is not None
    assert result["ema50"] is not None
    assert result["ema200"] is not None
    assert result["score"] > 50
    assert result["regime"] == "Golden Cross (Bull)"

def test_compute_macd_signal():
    np.random.seed(42)
    prices = np.linspace(100, 120, 100) + np.random.normal(0, 1, 100)
    hist = pd.DataFrame({"Close": prices})
    
    result = compute_macd_signal(hist)
    assert result["macd"] is not None
    assert result["signal"] is not None
    assert result["histogram"] is not None

def test_compute_volume_trend():
    np.random.seed(42)
    prices = np.linspace(100, 120, 100) + np.random.normal(0, 1, 100)
    volumes = np.random.randint(1000, 5000, 100)
    hist = pd.DataFrame({"Close": prices, "Volume": volumes})
    
    result = compute_volume_trend(hist)
    assert result["vol_20d_vs_90d"] is not None
    assert result["score"] is not None

def test_compute_market_regime():
    np.random.seed(42)
    prices = np.linspace(400, 500, 260) + np.random.normal(0, 5, 260)
    spy_hist = pd.DataFrame({"Close": prices})
    
    result = compute_market_regime(spy_hist)
    assert result["spy_above_200ema"] == True
    assert result["score"] > 50

def test_momentum_compute_overall():
    np.random.seed(42)
    prices = np.linspace(100, 150, 260) + np.random.normal(0, 1, 260)
    volumes = np.random.randint(1000, 5000, 260)
    hist = pd.DataFrame({"Close": prices, "Volume": volumes})
    spy_hist = pd.DataFrame({"Close": np.linspace(400, 500, 260)})
    
    data = {
        "history": hist,
        "spy_history": spy_hist,
        "week52_high": 155,
        "current_price": 150
    }
    result = compute(data)
    assert result["pillar"] == "Momentum"
    assert "components" in result
    assert result["score"] >= 0 and result["score"] <= 100
