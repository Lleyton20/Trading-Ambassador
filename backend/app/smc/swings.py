"""
Swing point detection (spec section 7).

A swing high at position i is a high strictly greater than the highs of
the `lookback` candles immediately before AND after it (swing low is the
mirror image). This is the "fractal" definition SMC analysis is built on,
and every higher-level concept (structure, BOS, CHoCH, order blocks) in
this codebase is required to use ONLY these validated swing points rather
than re-deriving its own notion of "significant high/low" — the spec is
explicit about this (section 7: "Every structure calculation should use
these validated swing points").

CONFIRMATION LAG (read this before using swings anywhere else)
-----------------------------------------------------------------
A swing at position i cannot be known until position i + lookback, because
we need the candles AFTER it to exist to confirm it's a local extreme.
Any code that walks forward through time (structure detection now, the
backtester later) must only treat a swing as "known" once it has reached
that confirmation position — never earlier. See `structure.py` for how
this is respected in practice.
"""
from __future__ import annotations

import pandas as pd


def find_swing_highs(df: pd.DataFrame, lookback: int = 2) -> pd.Series:
    highs = df["high"]
    n = len(df)
    result = pd.Series(index=df.index, dtype=float)
    for i in range(lookback, n - lookback):
        current = highs.iloc[i]
        left_max = highs.iloc[i - lookback:i].max()
        right_max = highs.iloc[i + 1:i + lookback + 1].max()
        if current > left_max and current > right_max:
            result.iloc[i] = current
    return result


def find_swing_lows(df: pd.DataFrame, lookback: int = 2) -> pd.Series:
    lows = df["low"]
    n = len(df)
    result = pd.Series(index=df.index, dtype=float)
    for i in range(lookback, n - lookback):
        current = lows.iloc[i]
        left_min = lows.iloc[i - lookback:i].min()
        right_min = lows.iloc[i + 1:i + lookback + 1].min()
        if current < left_min and current < right_min:
            result.iloc[i] = current
    return result


def get_swing_points(df: pd.DataFrame, lookback: int = 2) -> pd.DataFrame:
    """Combined swing-high/swing-low view, used by the API and tests."""
    return pd.DataFrame(
        {
            "swing_high": find_swing_highs(df, lookback),
            "swing_low": find_swing_lows(df, lookback),
        }
    )


def label_swing_sequence(df: pd.DataFrame, lookback: int = 2) -> list[dict]:
    """
    Returns confirmed swings in chronological order, each labeled HH/HL/
    LH/LL relative to the previous swing of the same kind (spec section 7).
    """
    highs = find_swing_highs(df, lookback)
    lows = find_swing_lows(df, lookback)

    swings: list[dict] = []
    for ts in df.index:
        if pd.notna(highs.loc[ts]):
            swings.append({"timestamp": ts, "price": float(highs.loc[ts]), "kind": "high"})
        if pd.notna(lows.loc[ts]):
            swings.append({"timestamp": ts, "price": float(lows.loc[ts]), "kind": "low"})
    swings.sort(key=lambda s: s["timestamp"])

    last_high: float | None = None
    last_low: float | None = None
    for swing in swings:
        if swing["kind"] == "high":
            swing["label"] = "HH" if (last_high is None or swing["price"] > last_high) else "LH"
            last_high = swing["price"]
        else:
            swing["label"] = "LL" if (last_low is None or swing["price"] < last_low) else "HL"
            last_low = swing["price"]
    return swings
