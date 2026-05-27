"""
data_fetcher.py — yfinance data layer with robust error handling.
Fetches all data needed by the 4 pillars in one pass to minimize API calls.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Any, Dict, Optional


def _safe_val(df: pd.DataFrame, row: str, col: int = 0) -> Optional[float]:
    """Safely pull a scalar from a statement DataFrame (rows=items, cols=dates)."""
    try:
        v = df.loc[row].iloc[col]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)
    except (KeyError, IndexError, TypeError):
        return None


def _safe_val_multi(df: pd.DataFrame, candidates: list, col: int = 0) -> Optional[float]:
    """Try multiple row name candidates; return first match."""
    for name in candidates:
        v = _safe_val(df, name, col)
        if v is not None:
            return v
    return None


def fetch_all(ticker: str) -> Dict[str, Any]:
    """
    Fetch all data needed for the 4-pillar analysis.
    Returns a dict with info, history, financial statements, and derived fields.
    """
    stock = yf.Ticker(ticker)
    data: Dict[str, Any] = {"ticker": ticker.upper(), "error": None}

    # ── Company info ──────────────────────────────────────────────────────────
    try:
        info = stock.info
        data["info"] = info
        data["name"] = info.get("longName") or info.get("shortName", ticker.upper())
        data["sector"] = info.get("sector", "Unknown")
        data["industry"] = info.get("industry", "Unknown")
        data["exchange"] = info.get("exchange", "")
        data["currency"] = info.get("currency", "USD")
        data["current_price"] = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        data["market_cap"] = info.get("marketCap")
        data["enterprise_value"] = info.get("enterpriseValue")
        data["week52_high"] = info.get("fiftyTwoWeekHigh")
        data["week52_low"] = info.get("fiftyTwoWeekLow")
        data["shares_outstanding"] = info.get("sharesOutstanding")
        data["total_debt"] = info.get("totalDebt", 0) or 0
        data["total_cash"] = info.get("totalCash", 0) or 0
        data["trailing_eps"] = info.get("trailingEps")
        data["forward_eps"] = info.get("forwardEps")
        data["trailing_pe"] = info.get("trailingPE")
        data["forward_pe"] = info.get("forwardPE")
        data["peg_ratio"] = info.get("pegRatio")
        data["price_to_book"] = info.get("priceToBook")
        data["price_to_sales"] = info.get("priceToSalesTrailingTwelveMonths")
        data["ev_to_ebitda"] = info.get("enterpriseToEbitda")
        data["ev_to_revenue"] = info.get("enterpriseToRevenue")
        data["earnings_growth"] = info.get("earningsGrowth")   # yoy
        data["revenue_growth"] = info.get("revenueGrowth")     # yoy
        data["return_on_equity"] = info.get("returnOnEquity")
        data["return_on_assets"] = info.get("returnOnAssets")
        data["free_cashflow"] = info.get("freeCashflow")
        data["operating_cashflow"] = info.get("operatingCashflow")
        data["beta"] = info.get("beta", 1.0) or 1.0
        data["analyst_target"] = info.get("targetMeanPrice")
        data["recommendation"] = info.get("recommendationKey", "")
        data["num_analyst_opinions"] = info.get("numberOfAnalystOpinions", 0) or 0
    except Exception as e:
        data["info"] = {}
        data["error"] = f"Info fetch failed: {e}"

    # ── Price history (2 years for all momentum calcs) ────────────────────────
    try:
        hist = stock.history(period="2y", auto_adjust=True)
        data["history"] = hist
    except Exception as e:
        data["history"] = pd.DataFrame()

    # ── S&P 500 history for market regime filter ──────────────────────────────
    try:
        spy = yf.Ticker("SPY").history(period="1y", auto_adjust=True)
        data["spy_history"] = spy
    except Exception:
        data["spy_history"] = pd.DataFrame()

    # ── Annual financial statements ───────────────────────────────────────────
    try:
        data["income_stmt"] = stock.income_stmt          # cols = dates (newest first)
    except Exception:
        data["income_stmt"] = pd.DataFrame()

    try:
        data["balance_sheet"] = stock.balance_sheet
    except Exception:
        data["balance_sheet"] = pd.DataFrame()

    try:
        data["cashflow"] = stock.cashflow
    except Exception:
        data["cashflow"] = pd.DataFrame()

    # ── Quarterly statements (for Piotroski & earnings surprise) ─────────────
    try:
        data["income_stmt_q"] = stock.quarterly_income_stmt
    except Exception:
        data["income_stmt_q"] = pd.DataFrame()

    try:
        data["balance_sheet_q"] = stock.quarterly_balance_sheet
    except Exception:
        data["balance_sheet_q"] = pd.DataFrame()

    try:
        data["cashflow_q"] = stock.quarterly_cashflow
    except Exception:
        data["cashflow_q"] = pd.DataFrame()

    # ── Analyst / earnings revision data ─────────────────────────────────────
    try:
        data["earnings_history"] = stock.earnings_history
    except Exception:
        data["earnings_history"] = pd.DataFrame()

    try:
        data["analyst_price_targets"] = stock.analyst_price_targets
    except Exception:
        data["analyst_price_targets"] = pd.DataFrame()

    try:
        data["upgrades_downgrades"] = stock.upgrades_downgrades
    except Exception:
        data["upgrades_downgrades"] = pd.DataFrame()

    # ── Derived convenience fields ────────────────────────────────────────────
    IS = data["income_stmt"]
    BS = data["balance_sheet"]
    CF = data["cashflow"]

    # EBIT
    data["ebit"] = _safe_val_multi(IS, ["EBIT", "Operating Income", "Ebit"])
    # EBITDA
    data["ebitda"] = _safe_val_multi(IS, ["EBITDA", "Normalized EBITDA"])
    # Revenue (current + prior year)
    data["revenue"] = _safe_val_multi(IS, ["Total Revenue", "Revenue"])
    data["revenue_prior"] = _safe_val_multi(IS, ["Total Revenue", "Revenue"], col=1)
    # Gross Profit
    data["gross_profit"] = _safe_val_multi(IS, ["Gross Profit"])
    data["gross_profit_prior"] = _safe_val_multi(IS, ["Gross Profit"], col=1)
    # Net Income
    data["net_income"] = _safe_val_multi(IS, ["Net Income", "Net Income Common Stockholders"])
    data["net_income_prior"] = _safe_val_multi(IS, ["Net Income", "Net Income Common Stockholders"], col=1)
    # Operating Cash Flow + CapEx → FCF
    data["ocf"] = _safe_val_multi(CF, ["Operating Cash Flow", "Cash Flow From Operations"])
    data["capex"] = _safe_val_multi(CF, ["Capital Expenditure", "Purchase Of PPE"])
    if data["ocf"] and data["capex"]:
        # capex is typically negative in yfinance
        data["fcf"] = data["ocf"] + data["capex"]
    else:
        data["fcf"] = data.get("free_cashflow")
    # Prior year FCF
    ocf_p = _safe_val_multi(CF, ["Operating Cash Flow", "Cash Flow From Operations"], col=1)
    capex_p = _safe_val_multi(CF, ["Capital Expenditure", "Purchase Of PPE"], col=1)
    if ocf_p and capex_p:
        data["fcf_prior"] = ocf_p + capex_p
    else:
        data["fcf_prior"] = None

    # Total Assets
    data["total_assets"] = _safe_val_multi(BS, ["Total Assets"])
    data["total_assets_prior"] = _safe_val_multi(BS, ["Total Assets"], col=1)
    # Current Assets / Liabilities
    data["current_assets"] = _safe_val_multi(BS, ["Current Assets"])
    data["current_assets_prior"] = _safe_val_multi(BS, ["Current Assets"], col=1)
    data["current_liabilities"] = _safe_val_multi(BS, ["Current Liabilities"])
    data["current_liabilities_prior"] = _safe_val_multi(BS, ["Current Liabilities"], col=1)
    # Long-term debt
    data["long_term_debt"] = _safe_val_multi(BS, ["Long Term Debt", "Long-Term Debt"])
    data["long_term_debt_prior"] = _safe_val_multi(BS, ["Long Term Debt", "Long-Term Debt"], col=1)
    # Shares outstanding (from balance sheet for dilution check)
    data["shares_bs"] = _safe_val_multi(BS, [
        "Ordinary Shares Number", "Share Issued", "Common Stock"
    ])
    data["shares_bs_prior"] = _safe_val_multi(BS, [
        "Ordinary Shares Number", "Share Issued", "Common Stock"
    ], col=1)
    # Net PPE + Net Working Capital (for ROIC)
    data["net_ppe"] = _safe_val_multi(BS, ["Net PPE", "Net Property Plant And Equipment"])
    data["net_working_capital"] = None
    if data["current_assets"] and data["current_liabilities"]:
        data["net_working_capital"] = data["current_assets"] - data["current_liabilities"]

    return data
