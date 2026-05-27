"""
reporter.py — Rich terminal output renderer.
Formats all pillar results into a structured, color-coded terminal report.
"""

import sys
import io

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import Any, Dict

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True, legacy_windows=False, highlight=False)

# Color map for signals
SIGNAL_COLORS = {
    "Strong Buy":   "bold green",
    "Buy":          "green",
    "Watch / Hold": "yellow",
    "Hold":         "yellow",
    "Sell":         "red",
    "Strong Sell":  "bold red",
}
SCORE_COLOR = lambda s: "green" if s >= 65 else ("yellow" if s >= 45 else "red")


def _fmt_pct(val, decimals=1) -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    return f"{val:+.{decimals}f}%"


def _fmt_num(val, decimals=1, suffix="") -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    return f"{val:.{decimals}f}{suffix}"


def _signal_badge(label: str) -> str:
    color = SIGNAL_COLORS.get(label, "white")
    return f"[{color}]{label}[/{color}]"


def _score_str(score) -> str:
    if score is None:
        return "[dim]N/A[/dim]"
    color = SCORE_COLOR(score)
    return f"[{color}]{score:.0f}/100[/{color}]"


# ── Header ────────────────────────────────────────────────────────────────────

def render_header(data: Dict, composite: Dict):
    price = data.get("current_price")
    mkt_cap = data.get("market_cap")
    w52h = data.get("week52_high")
    w52l = data.get("week52_low")
    sector = data.get("sector", "Unknown")
    name = data.get("name", data.get("ticker"))
    ticker = data.get("ticker", "")

    mkt_str = f"${mkt_cap/1e12:.2f}T" if mkt_cap and mkt_cap > 1e12 else \
              f"${mkt_cap/1e9:.1f}B" if mkt_cap else "N/A"
    price_str = f"${price:.2f}" if price else "N/A"
    range_str = f"${w52l:.2f} – ${w52h:.2f}" if w52h and w52l else "N/A"

    sig_color = SIGNAL_COLORS.get(composite["signal"], "white")
    composite_line = (
        f"  Composite: [{sig_color}]{composite['signal']}[/{sig_color}]  "
        f"[bold]{composite['bar']}[/bold]"
    )

    header_text = (
        f"[bold white]{name}[/bold white]  [dim]({ticker})[/dim]\n"
        f"  Price: [bold cyan]{price_str}[/bold cyan]  │  "
        f"Market Cap: [cyan]{mkt_str}[/cyan]  │  "
        f"Sector: [cyan]{sector}[/cyan]\n"
        f"  52W Range: [dim]{range_str}[/dim]\n"
        f"{composite_line}"
    )
    console.print(Panel(header_text, title="[bold]Stock Evaluation Report[/bold]",
                        border_style="cyan", box=box.SIMPLE_HEAD))


# ── Pillar summary table ──────────────────────────────────────────────────────

def render_pillar_summary(composite: Dict):
    table = Table(title="4-Pillar Summary", box=box.SIMPLE,
                  show_header=True, header_style="bold cyan")
    table.add_column("Pillar", style="bold", width=12)
    table.add_column("Weight", justify="center", width=8)
    table.add_column("Score", justify="center", width=10)
    table.add_column("Signal", width=14)
    table.add_column("Bar", width=26)

    for row in composite["pillar_summary"]:
        color = SCORE_COLOR(row["score"])
        table.add_row(
            row["pillar"],
            f"{row['weight_pct']}%",
            f"[{color}]{row['score']:.0f}/100[/{color}]",
            _signal_badge(row["signal"]),
            f"[{color}]{row['bar']}[/{color}]",
        )

    console.print(table)
    console.print(f"  [italic dim]💡 {composite['insight']}[/italic dim]\n")


# ── Value pillar ──────────────────────────────────────────────────────────────

def render_value(result: Dict):
    comps = result.get("components", {})
    table = Table(title=f"[bold cyan]PILLAR 1 - VALUE[/bold cyan]  "
                        f"{_score_str(result['score'])}  (weight: 30%)",
                  box=box.SIMPLE, show_header=True, header_style="cyan")
    table.add_column("Signal", width=22)
    table.add_column("Key Metric", width=28)
    table.add_column("Score", justify="center", width=10)
    table.add_column("Verdict", width=30)

    # Inverse DCF
    dcf = comps.get("inverse_dcf", {})
    imp = dcf.get("implied_growth_pct")
    his = dcf.get("historical_growth_pct")
    gap = dcf.get("gap_pp")
    dcf_metric = (f"Implied {_fmt_pct(imp)} vs. Hist {_fmt_pct(his)}"
                  + (f" (gap: {_fmt_pct(gap)})" if gap else ""))
    table.add_row("Inverse DCF", dcf_metric, _score_str(dcf.get("score")),
                  _signal_badge(dcf.get("label", "N/A")))

    # FCF Yield
    fcf = comps.get("fcf_yield", {})
    fcf_metric = (f"FCF Yield {_fmt_pct(fcf.get('fcf_yield_pct'))}  "
                  f"vs Treasury {_fmt_pct(fcf.get('treasury_yield_pct'))}  "
                  f"(spread {_fmt_pct(fcf.get('spread_pp'))})")
    table.add_row("FCF Yield vs. Risk-Free", fcf_metric,
                  _score_str(fcf.get("score")), _signal_badge(fcf.get("label", "N/A")))

    # EV/EBIT Yield
    evebit = comps.get("ev_ebit_yield", {})
    ev_metric = (f"EV/EBIT {_fmt_num(evebit.get('ev_ebit'))}x  "
                 f"(sector med: {_fmt_num(evebit.get('sector_ev_ebit'))}x)  "
                 f"EY: {_fmt_pct(evebit.get('earnings_yield_pct'))}")
    table.add_row("EV/EBIT Earnings Yield", ev_metric,
                  _score_str(evebit.get("score")), _signal_badge(evebit.get("label", "N/A")))

    # Composite multiples
    mult = comps.get("composite_multiples", {})
    details = mult.get("details", {})
    mult_parts = []
    for k, v in details.items():
        sig = v.get("signal", "")
        color = "green" if sig == "Cheap" else ("red" if sig == "Expensive" else "yellow")
        mult_parts.append(f"[{color}]{k}:{v.get('value')}[/{color}]")
    mult_metric = "  ".join(mult_parts) if mult_parts else "N/A"
    table.add_row("Composite Multiples", mult_metric,
                  _score_str(mult.get("score")), _signal_badge(mult.get("label", "N/A")))

    console.print(table)


# ── Quality pillar ────────────────────────────────────────────────────────────

def render_quality(result: Dict):
    comps = result.get("components", {})
    console.print(f"\n[bold cyan]PILLAR 2 - QUALITY[/bold cyan]  {_score_str(result['score'])}  (weight: 25%)")

    # Piotroski F-Score — show individual checks
    pio = comps.get("piotroski_f_score", {})
    pio_table = Table(title=f"Piotroski F-Score: {pio.get('raw_score', '?')}/9  "
                            f"— {pio.get('label', '')}",
                      box=box.MINIMAL, show_header=True, header_style="dim")
    pio_table.add_column("Criterion", width=30)
    pio_table.add_column("Pass/Fail", justify="center", width=10)
    pio_table.add_column("Detail", width=35)

    for criterion, (pf, detail) in pio.get("checks", {}).items():
        color = "green" if pf == "✓" else "red"
        pio_table.add_row(criterion, f"[{color}]{pf}[/{color}]", f"[dim]{detail}[/dim]")
    console.print(pio_table)

    # ROC & ROIC
    roc = comps.get("magic_formula_roc", {})
    roic = comps.get("roic_trend", {})

    roc_table = Table(box=box.MINIMAL, show_header=True, header_style="dim")
    roc_table.add_column("Quality Signal", width=22)
    roc_table.add_column("Value", width=20)
    roc_table.add_column("Score", justify="center", width=10)
    roc_table.add_column("Label", width=30)

    roc_table.add_row(
        "Magic Formula ROC",
        f"{_fmt_pct(roc.get('roc_pct'))}",
        _score_str(roc.get("score")),
        _signal_badge(roc.get("label", "N/A")),
    )
    roic_curr = roic.get("roic_current_pct")
    roic_prior = roic.get("roic_prior_pct")
    roic_val = (f"{_fmt_pct(roic_prior)} → {_fmt_pct(roic_curr)}"
                if roic_prior else _fmt_pct(roic_curr))
    roc_table.add_row(
        "ROIC Trend",
        roic_val,
        _score_str(roic.get("score")),
        _signal_badge(roic.get("label", "N/A")),
    )
    console.print(roc_table)


# ── Growth pillar ─────────────────────────────────────────────────────────────

def render_growth(result: Dict):
    comps = result.get("components", {})
    table = Table(
        title=f"[bold cyan]PILLAR 3 - GROWTH[/bold cyan]  "
              f"{_score_str(result['score'])}  (weight: 20%)",
        box=box.SIMPLE, show_header=True, header_style="cyan"
    )
    table.add_column("Signal", width=22)
    table.add_column("Key Metric", width=38)
    table.add_column("Score", justify="center", width=10)
    table.add_column("Verdict", width=30)

    # PEG
    peg = comps.get("peg_ratio", {})
    peg_metric = (f"PEG {_fmt_num(peg.get('peg'), 2)}x  "
                  f"(P/E {_fmt_num(peg.get('pe'), 1)},  "
                  f"EPS growth {_fmt_pct(peg.get('growth_pct'))})")
    table.add_row("PEG Ratio", peg_metric, _score_str(peg.get("score")),
                  _signal_badge(peg.get("label", "N/A")))

    # EPS Revision
    eps = comps.get("eps_revision", {})
    upg = eps.get("recent_upgrades", 0)
    dwg = eps.get("recent_downgrades", 0)
    surp = eps.get("avg_surprise_pct")
    rev_pct = eps.get("eps_revision_pct")
    eps_metric = (f"Fwd EPS revision: {_fmt_pct(rev_pct)}  │  "
                  f"Upgrades/Downgrades: {upg}/{dwg}  │  "
                  f"Avg surprise: {_fmt_pct(surp)}")
    table.add_row("EPS Revision Momentum", eps_metric,
                  _score_str(eps.get("score")), _signal_badge(eps.get("label", "N/A")))

    # Revenue growth
    rev = comps.get("revenue_growth", {})
    rev_metric = (f"3yr CAGR: {_fmt_pct(rev.get('cagr_3yr_pct'))}  │  "
                  f"YoY: {_fmt_pct(rev.get('yoy_pct'))}")
    table.add_row("Revenue Growth", rev_metric, _score_str(rev.get("score")),
                  _signal_badge(rev.get("label", "N/A")))

    console.print(table)


# ── Momentum pillar ───────────────────────────────────────────────────────────

def render_momentum(result: Dict):
    comps = result.get("components", {})
    mkt = result.get("market_regime", {})
    regime_color = "green" if mkt.get("spy_above_200ema") else "red"

    table = Table(
        title=f"[bold cyan]PILLAR 4 - MOMENTUM[/bold cyan]  "
              f"{_score_str(result['score'])}  (weight: 25%)  |  "
              f"Market Regime: [{regime_color}]{mkt.get('regime', 'N/A')}[/{regime_color}]",
        box=box.SIMPLE, show_header=True, header_style="cyan"
    )
    table.add_column("Signal", width=26)
    table.add_column("Key Metrics", width=42)
    table.add_column("Score", justify="center", width=10)
    table.add_column("Verdict", width=30)

    # Price momentum
    pm = comps.get("price_momentum_12m1m", {})
    pm_metric = (f"1M:{_fmt_pct(pm.get('ret_1m'), 1)}  "
                 f"3M:{_fmt_pct(pm.get('ret_3m'), 1)}  "
                 f"6M:{_fmt_pct(pm.get('ret_6m'), 1)}  "
                 f"12M-1M:{_fmt_pct(pm.get('ret_12m1m'), 1)}")
    vol_note = f"  [dim](vol: {pm.get('realized_vol_pct', '')}% → scaled: {pm.get('vol_scaled_score', '')})[/dim]"
    table.add_row("Price Momentum 12M-1M", pm_metric + vol_note,
                  _score_str(pm.get("vol_scaled_score") or pm.get("score")),
                  _signal_badge(pm.get("label", "N/A")))

    # EMA Regime
    ema = comps.get("ema_trend_regime", {})
    prox = ema.get("week52_prox_pct")
    ema_metric = (f"EMA 20:{_fmt_num(ema.get('ema20'), 2)}  "
                  f"50:{_fmt_num(ema.get('ema50'), 2)}  "
                  f"200:{_fmt_num(ema.get('ema200'), 2)}  │  "
                  f"52W High: {_fmt_num(prox, 1)}%")
    table.add_row(f"EMA Regime ({ema.get('regime', 'N/A')})", ema_metric,
                  _score_str(ema.get("score")), _signal_badge(ema.get("label", "N/A")))

    # MACD
    macd = comps.get("macd_signal", {})
    macd_metric = (f"MACD {_fmt_num(macd.get('macd'), 4)}  "
                   f"Signal {_fmt_num(macd.get('signal'), 4)}  "
                   f"Hist {_fmt_num(macd.get('histogram'), 4)}  "
                   f"[dim]({macd.get('hist_direction', '')})[/dim]")
    table.add_row(f"MACD  {macd.get('crossover', '')}", macd_metric,
                  _score_str(macd.get("score")), _signal_badge(macd.get("label", "N/A")))

    # Volume / OBV
    vol = comps.get("volume_trend_obv", {})
    vol_metric = (f"OBV trend: {vol.get('obv_trend', 'N/A')}  │  "
                  f"Avg vol 20d/90d: {_fmt_num(vol.get('vol_20d_vs_90d'), 2)}x")
    table.add_row("Volume / OBV Trend", vol_metric,
                  _score_str(vol.get("score")), _signal_badge(vol.get("label", "N/A")))

    console.print(table)


# ── Full report ───────────────────────────────────────────────────────────────

def render_report(data: Dict, value_r: Dict, quality_r: Dict,
                  growth_r: Dict, momentum_r: Dict, composite: Dict):
    console.rule("[bold cyan]STOCK EVALUATOR[/bold cyan]")
    render_header(data, composite)
    console.print()
    render_pillar_summary(composite)
    render_value(value_r)
    console.print()
    render_quality(quality_r)
    console.print()
    render_growth(growth_r)
    console.print()
    render_momentum(momentum_r)
    console.print()
    console.print("[dim]" + "-" * 80 + "[/dim]")
    console.print("[dim]Research: Piotroski (2000) | Jegadeesh-Titman (1993) | Greenblatt (2006) | "
                 "George-Hwang (2004) | S&P DJI Multi-Factor | CFA Institute (2025)[/dim]")
