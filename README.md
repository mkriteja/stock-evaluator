# Stock Evaluator

A robust, terminal-based stock evaluation framework that mimics institutional quantitative methodologies. It analyzes equities across four critical pillars: **Value, Quality, Growth, and Momentum**.

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the evaluator for any stock ticker:
   ```bash
   python analyze.py AAPL
   ```

## Architecture

The Stock Evaluator is designed with a **modular, data-driven architecture**. It separates the concerns of data fetching, mathematical scoring, and terminal presentation. 

This decoupling ensures that you can easily swap out the data provider (e.g., moving from Yahoo Finance to a paid API) or the UI (e.g., adding a web frontend) without having to rewrite the core financial logic.

```mermaid
graph TD
    User([User CLI Input]) --> Main[analyze.py]
    
    subgraph Core Application
        Main --> Fetcher[data_fetcher.py]
        Main --> Pillars[pillars/]
        Main --> Scorer[scorer.py]
        Main --> UI[reporter.py]
    end

    subgraph Data Layer
        Fetcher --> YF[(Yahoo Finance / yfinance)]
    end

    subgraph Evaluation Engine
        Pillars --> Val[value.py]
        Pillars --> Qual[quality.py]
        Pillars --> Gro[growth.py]
        Pillars --> Mom[momentum.py]
    end
    
    Fetcher -- Financial Data Dict --> Pillars
    Val -- Value Score --> Scorer
    Qual -- Quality Score --> Scorer
    Gro -- Growth Score --> Scorer
    Mom -- Momentum Score --> Scorer
    
    Scorer -- Composite Signal & Weights --> UI
    UI --> Output([Rich Terminal Output])
```

### Core Components & Evaluation Mechanisms

The application relies on four strict quantitative pillars to evaluate a stock. Each pillar analyzes raw financial data and mathematically bounds the result to a **0-100 score**.

1. **`pillars/value.py` (30% Weight)**: Determines if the stock is trading at a discount.
   - **Inverse DCF**: Solves the Discounted Cash Flow equation backward to find the perpetual growth rate the market expects, and compares it to historical FCF growth.
   - **FCF Yield**: Compares the company's Free Cash Flow yield against the risk-free rate (10-Year US Treasury).
   - **Multiples**: Evaluates EV/EBIT, EV/EBITDA, P/E, and P/FCF against historical and sector medians.

2. **`pillars/quality.py` (25% Weight)**: Evaluates the fundamental health and capital efficiency of the underlying business.
   - **Piotroski F-Score**: A 9-point checklist evaluating profitability, leverage, liquidity, and operating efficiency.
   - **Magic Formula ROC**: Calculates Return on Capital (EBIT / (Net Working Capital + Net Fixed Assets)) to identify companies with strong competitive moats.
   - **ROIC Trends**: Checks if Return on Invested Capital is expanding or contracting.

3. **`pillars/growth.py` (20% Weight)**: Analyzes forward-looking momentum and historical top-line expansion.
   - **PEG Ratio**: Normalizes the P/E ratio against the expected earnings growth rate to identify "growth at a reasonable price".
   - **EPS Revisions**: Tracks Wall Street analyst upgrades/downgrades and forward EPS momentum.
   - **Revenue Growth**: Calculates 3-year CAGRs and YoY top-line expansion.

4. **`pillars/momentum.py` (25% Weight)**: Uses technical indicators to identify current market regimes and institutional buying pressure.
   - **Price Momentum (12M-1M)**: Evaluates 1-year relative strength, excluding the most recent month to avoid mean-reversion traps (based on Jegadeesh-Titman research).
   - **Moving Average Regimes**: Identifies Bull/Bear regimes using 20, 50, and 200-day EMAs (e.g., Golden Crosses, Death Crosses).
   - **MACD & Volume**: Uses MACD histograms and On-Balance Volume (OBV) to detect accumulation or distribution pressure.

### The Scoring System (`scorer.py`)

Once all four pillars calculate their individual 0-100 scores, the **Scorer** aggregates them into a final composite signal using the weights listed above. 

The raw mathematical score is then translated into a definitive qualitative signal:
- **80 – 100**: Strong Buy
- **65 – 79**: Buy
- **50 – 64**: Watch / Hold
- **35 – 49**: Sell
- **0 – 34**: Strong Sell

## Batch Evaluation
You can also run batch processing scripts to evaluate multiple stocks sequentially:
```bash
python batch_analyze.py 10
```
