"""
Liquidity levels and liquidity sweeps (spec sections 5, 6, 11, 12).

A "liquidity level" is any price level where stop-losses/pending orders
are assumed to cluster: a swing high/low, a session high/low, a previous
day's high/low, or a cluster of "equal" highs/lows (a level several swings
have failed to close beyond, which the spec says makes it a stronger
liquidity magnet — section 12).

A "sweep" is: price trades BEYOND the level (a wick, not necessarily a
close) and then a later candle CLOSES back on the other side of it. That
close-back-through is what distinguishes a genuine sweep-and-reverse from
an ordinary breakout that keeps going (spec section 11's worked examples).

EQUAL HIGHS/LOWS TOLERANCE
---------------------------
Two swing highs are never bit-for-bit identical in real price data, so
"equal" always needs a tolerance (spec section 12: "never require exact
floating-point equality"). We use a percentage of price rather than a
fixed pip count, again because this platform spans instruments with very
different price scales (a EURUSD quote near 1.10 vs a Crash index near
10,000) — a fixed absolute tolerance would be meaningless on one or the
other.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class LiquidityLevel:
    label: str            # e.g. "swing_high", "equal_highs", "previous_day_high", "asian_high"
    kind: str              # "high" or "low"
    price: float
    formed_at: pd.Timestamp


@dataclass
class LiquiditySweepEvent:
    level: LiquidityLevel
    swept_at: pd.Timestamp
    sweep_extreme: float       # the furthest price reached beyond the level during the sweep


def find_equal_levels(swings: list[dict], *, tolerance_pct: float, kind: str) -> list[LiquidityLevel]:
    """
    Groups swing points of the given `kind` ("high" or "low") that fall
    within `tolerance_pct` of each other into "equal highs"/"equal lows"
    liquidity levels. A group must have at least 2 members to count.
    """
    label = "equal_highs" if kind == "high" else "equal_lows"
    points = [s for s in swings if s["kind"] == kind]

    levels: list[LiquidityLevel] = []
    used: set[int] = set()
    for i, anchor in enumerate(points):
        if i in used:
            continue
        group = [anchor]
        tolerance = abs(anchor["price"]) * tolerance_pct
        for j in range(i + 1, len(points)):
            if j in used:
                continue
            if abs(points[j]["price"] - anchor["price"]) <= tolerance:
                group.append(points[j])
                used.add(j)
        if len(group) >= 2:
            used.add(i)
            avg_price = sum(g["price"] for g in group) / len(group)
            latest_timestamp = max(g["timestamp"] for g in group)
            levels.append(LiquidityLevel(label=label, kind=kind, price=avg_price, formed_at=latest_timestamp))

    return levels


def detect_sweep(df: pd.DataFrame, level: LiquidityLevel) -> LiquiditySweepEvent | None:
    """
    Scans candles strictly after `level.formed_at` for a sweep: a wick
    beyond the level followed by a later close back on the other side.
    Returns the FIRST such event (a level is treated as "used up" once
    swept once), or None if it hasn't been swept.
    """
    candles_after = df[df.index > level.formed_at]
    if candles_after.empty:
        return None

    breached = False
    extreme = level.price

    for ts, row in candles_after.iterrows():
        if level.kind == "high":
            if row["high"] > level.price:
                breached = True
                extreme = max(extreme, row["high"])
            if breached and row["close"] < level.price:
                return LiquiditySweepEvent(level=level, swept_at=ts, sweep_extreme=extreme)
        else:  # "low"
            if row["low"] < level.price:
                breached = True
                extreme = min(extreme, row["low"])
            if breached and row["close"] > level.price:
                return LiquiditySweepEvent(level=level, swept_at=ts, sweep_extreme=extreme)

    return None
