"""
Renders one annotated candlestick chart from the exact same analysis
pipeline the /smc and /liquidity API routes run - swings, BOS/CHoCH,
order blocks, fair value gaps, liquidity levels/sweeps, and the active
premium/discount range, all drawn on top of real candles.

WHY THIS EXISTS
----------------
Comparing raw JSON timestamps against a TradingView chart by hand is slow
and error-prone. This script is the faster path: point it at a symbol and
timeframe, it calls the same functions app/api/routes.py calls, and
renders one picture that shows whether the detection logic actually lines
up with what's on the chart.

Not part of the running app - a standalone dev tool. Needs matplotlib,
which isn't in the API's own requirements.txt (see requirements-dev.txt).

USAGE
------
    cd backend
    pip install -r requirements-dev.txt
    python scripts/plot_analysis.py --symbol EURUSD --timeframe H1
    python scripts/plot_analysis.py --symbol V75 --timeframe H1 --provider deriv
    python scripts/plot_analysis.py --symbol EURUSD --timeframe H1 --show

Add --show to open an interactive window; otherwise it just saves a PNG
under scripts/output/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter

from app.config import settings
from app.instruments import INSTRUMENT_PROFILES
from app.market_data.deriv_provider import DerivMarketDataProvider
from app.market_data.mock_provider import MockMarketDataProvider
from app.smc.fvg import apply_mitigation as apply_fvg_mitigation
from app.smc.fvg import detect_fair_value_gaps
from app.smc.liquidity import detect_sweep, find_equal_levels
from app.smc.order_blocks import apply_mitigation as apply_ob_mitigation
from app.smc.order_blocks import detect_order_blocks
from app.smc.premium_discount import classify_premium_discount, determine_active_dealing_range
from app.smc.structure import detect_structure_events
from app.smc.swings import label_swing_sequence

_BULLISH_COLOR = "#1a8754"
_BEARISH_COLOR = "#c62828"


def _build_provider(name: str):
    if name == "deriv":
        return DerivMarketDataProvider(settings.deriv_app_id, timeout=settings.deriv_request_timeout)
    return MockMarketDataProvider(symbols=list(INSTRUMENT_PROFILES.keys()))


def _index_of(df: pd.DataFrame, timestamp: pd.Timestamp) -> int:
    """Position of `timestamp` in df's index, clamped to the chart's bounds."""
    try:
        pos = df.index.get_loc(timestamp)
        return int(pos) if isinstance(pos, (int,)) else int(pos.start)
    except KeyError:
        return len(df) - 1


def plot_analysis(symbol: str, timeframe: str, provider_name: str, count: int) -> tuple[plt.Figure, plt.Axes]:
    provider = _build_provider(provider_name)
    df = provider.get_candles(symbol, timeframe, count=count)

    swings = label_swing_sequence(df, lookback=settings.swing_lookback)
    events, bias = detect_structure_events(df, swing_lookback=settings.swing_lookback)

    order_blocks = detect_order_blocks(df, events, min_displacement_atr_multiple=settings.min_displacement_atr_mult)
    apply_ob_mitigation(df, order_blocks)

    gaps = detect_fair_value_gaps(df)
    apply_fvg_mitigation(df, gaps)

    levels = find_equal_levels(swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="high")
    levels += find_equal_levels(swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="low")
    sweeps = [(level, detect_sweep(df, level)) for level in levels]

    dealing_range = determine_active_dealing_range(swings)
    current_price = float(df["close"].iloc[-1])
    pd_status = classify_premium_discount(current_price, dealing_range) if dealing_range else None

    fig, ax = plt.subplots(figsize=(16, 9))
    n = len(df)

    # --- candlesticks (integer x-positions so weekend/session gaps don't
    # stretch the chart) ---------------------------------------------------
    for i, (_, row) in enumerate(df.iterrows()):
        color = _BULLISH_COLOR if row["close"] >= row["open"] else _BEARISH_COLOR
        ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=1, zorder=2)
        ax.add_patch(
            Rectangle(
                (i - 0.3, min(row["open"], row["close"])), 0.6, abs(row["close"] - row["open"]) or 1e-9,
                facecolor=color, edgecolor=color, zorder=3,
            )
        )

    # Cap how much gets drawn - the API truncates the same way ([-20:] in
    # app/api/routes.py) so the chart isn't just noise once a symbol has
    # accumulated dozens of events. A zone extends a bounded number of
    # candles past its creation rather than all the way to the chart's
    # edge, so old order blocks/FVGs don't stack into a solid blob.
    _EXTENSION = 30

    # --- swing points: color by label (HH/HL = bullish structure, LH/LL =
    # bearish), shape by kind - no text needed, keeps this layer legible. --
    for s in swings[-25:]:
        i = _index_of(df, s["timestamp"])
        marker = "v" if s["kind"] == "high" else "^"
        color = _BULLISH_COLOR if s["label"] in ("HH", "HL") else _BEARISH_COLOR
        offset = (df["high"].max() - df["low"].min()) * 0.012
        y = s["price"] + offset if s["kind"] == "high" else s["price"] - offset
        ax.scatter(i, y, marker=marker, color=color, s=35, zorder=4, edgecolors="white", linewidths=0.5)

    # --- BOS / CHoCH ------------------------------------------------------
    for e in events[-12:]:
        i = _index_of(df, e.timestamp)
        color = _BULLISH_COLOR if e.direction == "bullish" else _BEARISH_COLOR
        style = "-" if e.event_type == "BOS" else "--"
        ax.axvline(i, color=color, linestyle=style, linewidth=1, alpha=0.6, zorder=1)
        ax.annotate(e.event_type, (i, e.price), fontsize=8, color=color, fontweight="bold",
                    xytext=(3, 3), textcoords="offset points")

    # --- order blocks -------------------------------------------------
    for ob in order_blocks[-8:]:
        start = _index_of(df, ob.created_at)
        end = _index_of(df, ob.mitigated_at) if ob.mitigated_at is not None else min(start + _EXTENSION, n - 1)
        color = _BULLISH_COLOR if ob.direction == "bullish" else _BEARISH_COLOR
        ax.add_patch(
            Rectangle(
                (start, ob.zone_low), max(end - start, 1), ob.zone_high - ob.zone_low,
                facecolor=color, alpha=0.15, edgecolor=color, linewidth=0.5,
                hatch="//" if ob.mitigated else None, zorder=0,
            )
        )

    # --- fair value gaps ----------------------------------------------
    for g in gaps[-8:]:
        start = _index_of(df, g.created_at)
        end = min(start + _EXTENSION, n - 1)
        color = _BULLISH_COLOR if g.direction == "bullish" else _BEARISH_COLOR
        alpha = 0.20 * (1 - g.mitigated_pct / 100.0) + 0.03
        ax.add_patch(
            Rectangle(
                (start, g.lower), max(end - start, 1), g.upper - g.lower,
                facecolor=color, alpha=alpha, edgecolor="none", zorder=0,
            )
        )

    # --- liquidity levels + sweeps ---------------------------------------
    # Most recently formed levels only, and no per-line text (with several
    # close-together levels the labels just overlap into noise) - color
    # alone distinguishes swept from unswept, backed by the legend.
    for level, sweep in sorted(sweeps, key=lambda pair: pair[0].formed_at)[-8:]:
        color = "#9e9e9e" if sweep is None else "#d81b60"
        ax.axhline(level.price, color=color, linestyle=":", linewidth=1, alpha=0.7, zorder=1)
        if sweep is not None:
            ax.scatter(_index_of(df, sweep.swept_at), sweep.sweep_extreme, marker="x", color=color, s=60, zorder=5)

    # --- premium / discount dealing range -------------------------------
    if dealing_range is not None:
        ax.axhspan(dealing_range.equilibrium, dealing_range.range_high, color=_BEARISH_COLOR, alpha=0.05, zorder=0)
        ax.axhspan(dealing_range.range_low, dealing_range.equilibrium, color=_BULLISH_COLOR, alpha=0.05, zorder=0)
        ax.axhline(dealing_range.equilibrium, color="#666666", linestyle="-.", linewidth=1, alpha=0.5)

    # --- legend -------------------------------------------------------
    legend_handles = [
        Line2D([0], [0], marker="^", color="none", markerfacecolor=_BULLISH_COLOR, markersize=8, label="swing (bullish structure)"),
        Line2D([0], [0], marker="v", color="none", markerfacecolor=_BEARISH_COLOR, markersize=8, label="swing (bearish structure)"),
        Line2D([0], [0], color="#555555", linestyle="-", label="BOS"),
        Line2D([0], [0], color="#555555", linestyle="--", label="CHoCH"),
        Patch(facecolor=_BULLISH_COLOR, alpha=0.2, label="order block / FVG (bullish)"),
        Patch(facecolor=_BEARISH_COLOR, alpha=0.2, label="order block / FVG (bearish)"),
        Line2D([0], [0], color="#9e9e9e", linestyle=":", label="liquidity level (unswept)"),
        Line2D([0], [0], color="#d81b60", linestyle=":", marker="x", label="liquidity level (swept)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=8, framealpha=0.9)

    # --- axes/labels -----------------------------------------------------
    def _fmt(x, _pos):
        idx = int(round(x))
        if 0 <= idx < n:
            return df.index[idx].strftime("%m-%d %H:%M")
        return ""

    ax.xaxis.set_major_formatter(FuncFormatter(_fmt))
    ax.set_xlim(-1, n)
    fig.autofmt_xdate(rotation=45)

    subtitle = f"bias: {bias}"
    if pd_status:
        subtitle += f" | price: {pd_status}"
    ax.set_title(f"{symbol} {timeframe}  ({subtitle})")
    ax.set_ylabel("price")
    fig.tight_layout()
    return fig, ax


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="H1")
    parser.add_argument("--provider", choices=["mock", "deriv"], default="mock")
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--output", default=None, help="PNG path (default: scripts/output/<symbol>_<timeframe>.png)")
    parser.add_argument("--show", action="store_true", help="open an interactive window instead of only saving")
    args = parser.parse_args()

    fig, _ = plot_analysis(args.symbol, args.timeframe, args.provider, args.count)

    output = Path(args.output) if args.output else Path(__file__).parent / "output" / f"{args.symbol}_{args.timeframe}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    print(f"Saved {output}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
