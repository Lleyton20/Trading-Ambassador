"""
Displacement detection (spec section 16).

A "displacement" candle is one whose body (the distance from open to
close) is unusually large relative to recent volatility. It's the
evidence that separates an ordinary candle from a genuinely committed,
institutional-looking move — and per the spec, order blocks and FVGs are
supposed to be *linked to* that kind of evidence rather than created from
any arbitrary candle (section 13: "do not label every opposite candle as
an order block").

We measure "unusually large" relative to ATR rather than a fixed price
amount, specifically because this platform covers both Forex (small,
steady price moves) and Deriv synthetic indices (large, spiky moves) —
a fixed threshold that works for EURUSD would be meaningless for a Crash
index. Comparing against the instrument's OWN recent ATR keeps the
definition meaningful across very different volatility regimes.
"""
from __future__ import annotations

import pandas as pd

from app.smc.indicators import calculate_atr


def detect_displacement(df: pd.DataFrame, *, min_atr_multiple: float = 1.5, atr_period: int = 14) -> pd.Series:
    """
    Returns a boolean Series: True where the candle's body exceeds
    `min_atr_multiple` times the ATR at that point.
    """
    atr = calculate_atr(df, atr_period)
    body = (df["close"] - df["open"]).abs()
    return body >= (atr * min_atr_multiple)


def is_displacement_candle(df: pd.DataFrame, position: int, atr: pd.Series, *, min_atr_multiple: float = 1.5) -> bool:
    """Single-candle check, used by order_blocks.py when evaluating one specific candle."""
    atr_value = atr.iloc[position]
    if pd.isna(atr_value) or atr_value == 0:
        return False
    body = abs(df["close"].iloc[position] - df["open"].iloc[position])
    return body >= atr_value * min_atr_multiple
