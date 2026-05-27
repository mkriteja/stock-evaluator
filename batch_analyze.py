import subprocess
import pandas as pd
import sys
import io

# Force stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_trending_tickers():
    print("Fetching Most Active list from Yahoo Finance...")
    try:
        storage_options = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        # Yahoo Finance most active table
        tables = pd.read_html("https://finance.yahoo.com/most-active", storage_options=storage_options)
        df = tables[0]  # The first table on the page
        tickers = df['Symbol'].dropna().astype(str).tolist()
        return [t for t in tickers if t.strip() and t != 'nan']
    except Exception as e:
        print(f"Error fetching from Yahoo Finance: {e}")
        # Fallback to S&P 100
        print("Falling back to S&P 100...")
        try:
            tables = pd.read_html("https://en.wikipedia.org/wiki/S%26P_100", storage_options={'User-Agent': 'Mozilla/5.0'})
            return [t.replace(".", "-") for t in tables[2]['Symbol'].tolist()]
        except:
            return ["NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "META", "GOOGL", "PLTR", "INTC"]

def main():
    limit = 5
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        
    tickers = get_trending_tickers()
    print(f"\nFound {len(tickers)} tickers. Running evaluator on the first {limit}...\n")
    
    for i, ticker in enumerate(tickers[:limit]):
        print(f"{'='*80}")
        print(f"Running analysis for: {ticker} ({i+1}/{limit})")
        print(f"{'='*80}")
        
        # Run the existing analyze.py script
        # Ensure the subprocess also uses utf-8
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(["python", "analyze.py", ticker], capture_output=True, text=True, encoding="utf-8", env=env)
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Failed to analyze {ticker}:\n{result.stderr}")
            
if __name__ == "__main__":
    main()
