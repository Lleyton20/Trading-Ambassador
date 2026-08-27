"""
Market structure: Break of Structure (BOS) and Change of Character
(CHoCH) detection (spec sections 8-10).

BOS vs CHOCH — the distinction this module enforces
-----------------------------------------------------
It's easy to blur these two concepts together by inferring both purely
from comparing swing points to each other. The spec calls for an explicit
algorithmic definition instead (section 46), so here it is:

  - BOS (Break of Structure): a candle CLOSES beyond the most recent
    confirmed swing level IN THE DIRECTION OF THE CURRENT BIAS. It means
    the existing trend is continuing.
  - CHoCH (Change of Character): a candle CLOSES beyond the most recent
    confirmed swing level AGAINST the current bias. It's the first sign
    of a reversal, and it's what flips `bias`.

Both require a CANDLE CLOSE beyond the level — not just a wick touching
it — and both accept an optional `min_displacement` so a break has to
clear the level by a meaningful amount, not by one tick (spec: "do not
simply count wick touches as BOS unless configured").

NO LOOKAHEAD: a swing is only usable once its confirmation position has
been reached (see swings.py). We walk candle-by-candle and only "learn
about" a swing at the exact position where it becomes knowable, which is
what makes this function safe to reuse inside the backtester later
without silently peeking into the future.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.smc.swings import find_swing_highs, find_swing_lows


@dataclass
class StructureEvent:
    timestamp: pd.Timestamp
    event_type: str   # "BOS" or "CHOCH"
    direction: str    # "bullish" or "bearish"
    price: float      # the candle close that confirmed the break
    broken_level: float


def detect_structure_events(
    df: pd.DataFrame,
    *,
    swing_lookback: int = 2,
    min_displacement: float = 0.0,
) -> tuple[list[StructureEvent], str]:
    """
    Walks candles in chronological order and emits BOS/CHOCH events.
    Returns (events, final_bias); final_bias is "bullish", "bearish", or
    "neutral" if no break has occurred yet.
    """
    highs = find_swing_highs(df, swing_lookback)
    lows = find_swing_lows(df, swing_lookback)
    n = len(df)

    events: list[StructureEvent] = []
    bias = "neutral"
    last_confirmed_high: float | None = None
    last_confirmed_low: float | None = None

    for j in range(n):
        ts = df.index[j]
        close = float(df["close"].iloc[j])

        # A swing found at position i becomes knowable at i + swing_lookback.
        confirm_pos = j - swing_lookback
        if 0 <= confirm_pos < n:
            confirm_ts = df.index[confirm_pos]
            if pd.notna(highs.loc[confirm_ts]):
                last_confirmed_high = float(highs.loc[confirm_ts])
            if pd.notna(lows.loc[confirm_ts]):
                last_confirmed_low = float(lows.loc[confirm_ts])

        # A single candle is checked against the bullish break first; in
        # practice a candle rarely qualifies for both directions at once,
        # since breaking the recent high and the recent low simultaneously
        # would require an implausibly wide candle.
        if last_confirmed_high is not None and close > last_confirmed_high + min_displacement:
            event_type = "BOS" if bias in ("bullish", "neutral") else "CHOCH"
            events.append(StructureEvent(ts, event_type, "bullish", close, last_confirmed_high))
            bias = "bullish"
            last_confirmed_high = None  # level is broken; don't refire on it
        elif last_confirmed_low is not None and close < last_confirmed_low - min_displacement:
            event_type = "BOS" if bias in ("bearish", "neutral") else "CHOCH"
            events.append(StructureEvent(ts, event_type, "bearish", close, last_confirmed_low))
            bias = "bearish"
            last_confirmed_low = None

    return events, bias
