import pytest
from unittest.mock import patch, MagicMock
from data_fetcher import fetch_all, _safe_val
import pandas as pd
import numpy as np

def test_safe_val():
    df = pd.DataFrame({
        '2024': [100, 200],
        '2025': [150, 250]
    }, index=['Revenue', 'Net Income'])
    
    # Test valid extraction (default offset -1)
    assert _safe_val(df, 'Revenue') == 150.0
    
    # Test offset extraction (-2)
    assert _safe_val(df, 'Revenue', -2) == 100.0
    
    # Test missing row
    assert _safe_val(df, 'FakeRow') is None
    
    # Test None dataframe
    assert _safe_val(None, 'Revenue') is None

@patch("data_fetcher.FMP_API_KEY", None)
def test_fetch_all_no_api_key():
    # If no API key is found, it should return an error immediately
    data = fetch_all("AAPL")
    assert data["error"] == "No FMP_API_KEY found in .env"

@patch("data_fetcher.yf.Ticker")
@patch("data_fetcher.Toolkit")
@patch("data_fetcher.FMP_API_KEY", "fake_key")
def test_fetch_all_success(mock_toolkit, mock_ticker):
    # Mock yfinance
    mock_yf_instance = MagicMock()
    mock_yf_instance.info = {"currentPrice": 150.0, "marketCap": 2000000}
    mock_ticker.return_value = mock_yf_instance
    
    # Mock FinanceToolkit
    mock_tk_instance = MagicMock()
    
    mock_is = pd.DataFrame({'2025': [1000]}, index=['Operating Income'])
    mock_bs = pd.DataFrame({'2025': [5000]}, index=['Total Assets'])
    mock_cf = pd.DataFrame({'2025': [300]}, index=['Free Cash Flow'])
    
    mock_tk_instance.get_income_statement.return_value = mock_is
    mock_tk_instance.get_balance_sheet_statement.return_value = mock_bs
    mock_tk_instance.get_cash_flow_statement.return_value = mock_cf
    mock_toolkit.return_value = mock_tk_instance
    
    data = fetch_all("AAPL")
    
    assert data["error"] is None
    assert data["current_price"] == 150.0
    assert data["ebit"] == 1000.0
    assert data["total_assets"] == 5000.0
    assert data["fcf"] == 300.0
