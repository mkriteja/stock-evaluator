"""
analyze.py — CLI entry point for the Stock Evaluation Framework.

# Windows UTF-8 fix applied at module level (before Rich loads)
import sys, io, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

Usage:
  python analyze.py AAPL
  python analyze.py MSFT --weights value=35 quality=30 growth=15 momentum=20
  python analyze.py NVDA AAPL META           (compare multiple tickers)

Frameworks implemented (evidence-backed):
  VALUE (30%):    Inverse DCF · EV/EBIT Yield · FCF Yield · Composite Multiples
  QUALITY (25%):  Piotroski F-Score · Magic Formula ROC · ROIC Trend
  GROWTH (20%):   PEG Ratio · EPS Revision Momentum · Revenue Growth (3yr)
  MOMENTUM (25%): 12M-1M Price Momentum (vol-scaled) · EMA Regime (20/50/200)
                  MACD Histogram · OBV Volume Trend · SPY Regime Filter
"""

import sys
import argparse
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

import data_fetcher
from pillars import value, quality, growth, momentum
from scorer import compute_composite
from reporter import render_report

console = Console()


def parse_weights(weight_args):
    """Parse --weights value=35 quality=30 ... into a normalized dict."""
    defaults = {"value": 0.30, "quality": 0.25, "growth": 0.20, "momentum": 0.25}
    if not weight_args:
        return defaults
    parsed = {}
    for arg in weight_args:
        try:
            k, v = arg.split("=")
            parsed[k.lower().strip()] = float(v.strip()) / 100
        except ValueError:
            console.print(f"[red]Invalid weight format: {arg!r}. Use key=value (e.g. value=30)[/red]")
            sys.exit(1)
    # Merge with defaults for any missing pillar
    for k in defaults:
        if k not in parsed:
            parsed[k] = defaults[k]
    return parsed


def analyze_ticker(ticker: str, weights: dict) -> dict:
    """Run full 4-pillar analysis on one ticker. Returns composite result dict."""
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Fetching data for {ticker.upper()}..."),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("fetch", total=None)
        t0 = time.time()
        data = data_fetcher.fetch_all(ticker)
        elapsed = time.time() - t0

    if data.get("error") and not data.get("info"):
        console.print(f"[red]✗ Failed to fetch data for {ticker}: {data['error']}[/red]")
        return {}

    if not data.get("market_cap"):
        console.print(f"[yellow]⚠ Limited data for {ticker} — some signals may show N/A[/yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Computing pillars..."),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("compute", total=None)
        value_r = value.compute(data)
        quality_r = quality.compute(data)
        growth_r = growth.compute(data)
        momentum_r = momentum.compute(data)
        composite = compute_composite(value_r, quality_r, growth_r, momentum_r, weights)

    render_report(data, value_r, quality_r, growth_r, momentum_r, composite)
    console.print(f"[dim]  Data fetched in {elapsed:.1f}s[/dim]\n")

    return {
        "ticker": ticker.upper(),
        "composite_score": composite["composite_score"],
        "signal": composite["signal"],
        "pillar_scores": composite["pillar_scores"],
    }


def render_comparison_table(results: list):
    """When multiple tickers given, show a ranked comparison table."""
    from rich.table import Table
    from rich import box
    from scorer import score_to_bar, SIGNAL_COLORS

    ranked = sorted(results, key=lambda r: r.get("composite_score", 0), reverse=True)

    table = Table(title="[bold]Multi-Ticker Comparison (Ranked)[/bold]",
                  box=box.DOUBLE_EDGE, header_style="bold cyan")
    table.add_column("Rank", justify="center", width=6)
    table.add_column("Ticker", width=8)
    table.add_column("Composite", justify="center", width=12)
    table.add_column("Signal", width=14)
    table.add_column("Value", justify="center", width=8)
    table.add_column("Quality", justify="center", width=9)
    table.add_column("Growth", justify="center", width=8)
    table.add_column("Momentum", justify="center", width=10)

    from reporter import SCORE_COLOR
    for i, r in enumerate(ranked, 1):
        ps = r.get("pillar_scores", {})
        sig = r.get("signal", "N/A")
        sig_color = SIGNAL_COLORS.get(sig, "white")
        cs = r.get("composite_score", 0)
        table.add_row(
            str(i),
            f"[bold]{r['ticker']}[/bold]",
            f"[{SCORE_COLOR(cs)}]{cs:.0f}/100[/{SCORE_COLOR(cs)}]",
            f"[{sig_color}]{sig}[/{sig_color}]",
            f"[{SCORE_COLOR(ps.get('value',50))}]{ps.get('value',0):.0f}[/{SCORE_COLOR(ps.get('value',50))}]",
            f"[{SCORE_COLOR(ps.get('quality',50))}]{ps.get('quality',0):.0f}[/{SCORE_COLOR(ps.get('quality',50))}]",
            f"[{SCORE_COLOR(ps.get('growth',50))}]{ps.get('growth',0):.0f}[/{SCORE_COLOR(ps.get('growth',50))}]",
            f"[{SCORE_COLOR(ps.get('momentum',50))}]{ps.get('momentum',0):.0f}[/{SCORE_COLOR(ps.get('momentum',50))}]",
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Stock Evaluation Framework — 4-pillar terminal analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze.py AAPL
  python analyze.py MSFT --weights value=35 quality=30 growth=15 momentum=20
  python analyze.py AAPL MSFT NVDA GOOG META
        """
    )
    parser.add_argument("tickers", nargs="+", help="Stock ticker symbol(s) (e.g. AAPL MSFT)")
    parser.add_argument(
        "--weights", nargs="+", metavar="PILLAR=PCT",
        help="Override pillar weights, e.g. --weights value=40 quality=30 growth=10 momentum=20"
    )
    args = parser.parse_args()

    weights = parse_weights(args.weights)
    total_w = sum(weights.values())
    console.print(
        f"\n[dim]Weights: Value {weights['value']*100:.0f}% · "
        f"Quality {weights['quality']*100:.0f}% · "
        f"Growth {weights['growth']*100:.0f}% · "
        f"Momentum {weights['momentum']*100:.0f}% "
        f"(total: {total_w*100:.0f}%)[/dim]\n"
    )

    tickers = [t.upper() for t in args.tickers]
    results = []

    for ticker in tickers:
        if len(tickers) > 1:
            console.rule(f"[bold cyan]{ticker}[/bold cyan]")
        result = analyze_ticker(ticker, weights)
        if result:
            results.append(result)

    if len(results) > 1:
        console.rule("[bold]Comparison[/bold]")
        render_comparison_table(results)


if __name__ == "__main__":
    main()
