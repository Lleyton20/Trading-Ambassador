"""
Shared technical indicators used by the SMC engine.

Kept tiny and dependency-free (just pandas) on purpose — this is the one
place `calculate_atr` is defined, so displacement, order-block evidence,
and (later) volatility-based filters all agree on what "ATR" means.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range: the rolling mean of each candle's true range."""
    high_low = df["high"] - df["low"]
    high_prev_close = (df["high"] - df["close"].shift()).abs()
    low_prev_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()
