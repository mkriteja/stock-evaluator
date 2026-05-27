"""
data_fetcher.py — FinanceToolkit (FMP) + yfinance data layer with robust error handling.
Fetches all data needed by the 4 pillars in one pass to minimize API calls.
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from financetoolkit import Toolkit

# Load the API key from the local .env file securely
load_dotenv()
FMP_API_KEY = os.environ.get("FMP_API_KEY")


def _safe_val(df: pd.DataFrame, row: str, offset: int = -1) -> Optional[float]:
    """Safely pull a scalar from an FMP DataFrame (rows=items, cols=dates).
    offset=-1 means the most recent year. offset=-2 means the prior year.
    """
    try:
        if df is None or df.empty:
            return None
        v = df.loc[row].iloc[offset]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)
    except (KeyError, IndexError, TypeError):
        return None


def fetch_all(ticker: str) -> Dict[str, Any]:
    """
    Fetch all data needed for the 4-pillar analysis.
    Returns a dict with info, history, financial statements, and derived fields.
    """
    ticker = ticker.upper()
    data: Dict[str, Any] = {"ticker": ticker, "error": None}

    # ── 1. yfinance (Market Data, Price History, Analyst Estimates) ───────────
    stock = yf.Ticker(ticker)
    
    try:
        info = stock.info
        data["info"] = info
        data["name"] = info.get("longName") or info.get("shortName", ticker)
        data["sector"] = info.get("sector", "Unknown")
        data["industry"] = info.get("industry", "Unknown")
        data["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        data["market_cap"] = info.get("marketCap")
        data["enterprise_value"] = info.get("enterpriseValue")
        data["trailing_eps"] = info.get("trailingEps")
        data["forward_eps"] = info.get("forwardEps")
        data["trailing_pe"] = info.get("trailingPE")
        data["forward_pe"] = info.get("forwardPE")
        data["peg_ratio"] = info.get("pegRatio")
        data["price_to_book"] = info.get("priceToBook")
        data["ev_to_ebitda"] = info.get("enterpriseToEbitda")
        data["ev_to_revenue"] = info.get("enterpriseToRevenue")
        data["earnings_growth"] = info.get("earningsGrowth")
        data["revenue_growth"] = info.get("revenueGrowth")
        data["return_on_equity"] = info.get("returnOnEquity")
        data["beta"] = info.get("beta", 1.0) or 1.0
        data["analyst_target"] = info.get("targetMeanPrice")
        data["recommendation"] = info.get("recommendationKey", "")
        data["num_analyst_opinions"] = info.get("numberOfAnalystOpinions", 0) or 0
    except Exception as e:
        data["info"] = {}
        data["error"] = f"YF Info fetch failed: {e}"

    # Price history (2 years for all momentum calcs)
    try:
        data["history"] = stock.history(period="2y", auto_adjust=True)
    except Exception:
        data["history"] = pd.DataFrame()

    # S&P 500 history for market regime filter
    try:
        data["spy_history"] = yf.Ticker("SPY").history(period="1y", auto_adjust=True)
    except Exception:
        data["spy_history"] = pd.DataFrame()

    # Analyst / earnings revision data
    try:
        data["earnings_history"] = stock.earnings_history
    except Exception:
        data["earnings_history"] = pd.DataFrame()

    try:
        data["upgrades_downgrades"] = stock.upgrades_downgrades
    except Exception:
        data["upgrades_downgrades"] = pd.DataFrame()


    # ── 2. FinanceToolkit / FMP (Fundamental Financial Statements) ────────────
    if not FMP_API_KEY:
        data["error"] = "No FMP_API_KEY found in .env"
        return data

    try:
        # Initialize the Toolkit
        tk = Toolkit([ticker], api_key=FMP_API_KEY)
        
        # Fetch the core statements
        IS = tk.get_income_statement()
        BS = tk.get_balance_sheet_statement()
        CF = tk.get_cash_flow_statement()
        
        # ── Derived fields (Current Year)
        data["ebit"] = _safe_val(IS, "Operating Income")
        data["ebitda"] = _safe_val(IS, "EBITDA")
        data["revenue"] = _safe_val(IS, "Revenue")
        data["gross_profit"] = _safe_val(IS, "Gross Profit")
        data["net_income"] = _safe_val(IS, "Net Income")
        data["ocf"] = _safe_val(CF, "Operating Cash Flow")
        data["capex"] = _safe_val(CF, "Capital Expenditure")
        data["fcf"] = _safe_val(CF, "Free Cash Flow")
        
        data["total_assets"] = _safe_val(BS, "Total Assets")
        data["current_assets"] = _safe_val(BS, "Total Current Assets")
        data["current_liabilities"] = _safe_val(BS, "Total Current Liabilities")
        data["long_term_debt"] = _safe_val(BS, "Long Term Debt")
        data["shares_bs"] = _safe_val(IS, "Weighted Average Shares Outstanding") # FMP puts shares in IS
        data["net_ppe"] = _safe_val(BS, "Property, Plant and Equipment")
        
        if data["current_assets"] and data["current_liabilities"]:
            data["net_working_capital"] = data["current_assets"] - data["current_liabilities"]
        else:
            data["net_working_capital"] = None

        # ── Derived fields (Prior Year, offset = -2)
        data["revenue_prior"] = _safe_val(IS, "Revenue", -2)
        data["gross_profit_prior"] = _safe_val(IS, "Gross Profit", -2)
        data["net_income_prior"] = _safe_val(IS, "Net Income", -2)
        data["fcf_prior"] = _safe_val(CF, "Free Cash Flow", -2)
        
        data["total_assets_prior"] = _safe_val(BS, "Total Assets", -2)
        data["current_assets_prior"] = _safe_val(BS, "Total Current Assets", -2)
        data["current_liabilities_prior"] = _safe_val(BS, "Total Current Liabilities", -2)
        data["long_term_debt_prior"] = _safe_val(BS, "Long Term Debt", -2)
        data["shares_bs_prior"] = _safe_val(IS, "Weighted Average Shares Outstanding", -2)

        # To prevent pillar crashes if expected DF structures are queried, 
        # we will provide empty dummies since the pillars have been fully 
        # mapped to use our derived fields above!
        data["income_stmt"] = IS
        data["balance_sheet"] = BS
        data["cashflow"] = CF
        data["income_stmt_q"] = pd.DataFrame()
        data["balance_sheet_q"] = pd.DataFrame()
        data["cashflow_q"] = pd.DataFrame()

    except Exception as e:
        data["error"] = f"FinanceToolkit fetch failed: {e}"

    return data
