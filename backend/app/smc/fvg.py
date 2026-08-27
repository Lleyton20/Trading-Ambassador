"""
Fair Value Gap (FVG) detection (spec section 14).

The classic three-candle definition: candle 2 is a strong displacement
candle that leaves a gap between candle 1's wick and candle 3's wick.
  - Bullish FVG: candle 3's low is above candle 1's high (an untouched
    gap of "fair value" below the current price).
  - Bearish FVG: candle 3's high is below candle 1's low.

Mitigation percentage tracks how much of the gap has since been "filled"
by price trading back into it — 0% means untouched, 100% means fully
filled. This is what lets the API answer "partially filled FVG" per
spec section 14, rather than a binary filled/unfilled flag.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class FairValueGap:
    direction: str          # "bullish" or "bearish"
    upper: float
    lower: float
    created_at: pd.Timestamp
    mitigated_pct: float = 0.0

    @property
    def midpoint(self) -> float:
        return (self.upper + self.lower) / 2


def detect_fair_value_gaps(df: pd.DataFrame) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    n = len(df)
    for i in range(1, n - 1):
        prev_high = df["high"].iloc[i - 1]
        prev_low = df["low"].iloc[i - 1]
        next_high = df["high"].iloc[i + 1]
        next_low = df["low"].iloc[i + 1]

        if next_low > prev_high:
            gaps.append(FairValueGap(direction="bullish", upper=next_low, lower=prev_high, created_at=df.index[i + 1]))
        elif next_high < prev_low:
            gaps.append(FairValueGap(direction="bearish", upper=prev_low, lower=next_high, created_at=df.index[i + 1]))
    return gaps


def apply_mitigation(df: pd.DataFrame, gaps: list[FairValueGap]) -> None:
    """
    Mutates each gap's `mitigated_pct` in place based on how deep price has
    traded back into the gap since it formed. Only candles AFTER the gap's
    `created_at` are considered — a gap can't be mitigated by the candles
    that created it.
    """
    for gap in gaps:
        span = gap.upper - gap.lower
        if span <= 0:
            continue

        after = df[df.index > gap.created_at]
        deepest_fill = 0.0
        for _, row in after.iterrows():
            overlap_low = max(row["low"], gap.lower)
            overlap_high = min(row["high"], gap.upper)
            if overlap_high <= overlap_low:
                continue  # candle didn't reach into the gap at all

            if gap.direction == "bullish":
                # Bullish FVG sits below current price; it's filled by
                # price trading DOWN into it, i.e. from the top down.
                filled_from_top = gap.upper - overlap_low
                deepest_fill = max(deepest_fill, filled_from_top)
            else:
                # Bearish FVG sits above current price; filled from the
                # bottom up.
                filled_from_bottom = overlap_high - gap.lower
                deepest_fill = max(deepest_fill, filled_from_bottom)

        gap.mitigated_pct = min(1.0, deepest_fill / span)
