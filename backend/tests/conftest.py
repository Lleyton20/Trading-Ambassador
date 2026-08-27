"""
Shared, hand-crafted deterministic test data.

Financial calculations should not depend only on manual visual inspection
(spec section 38) — every value in this fixture was chosen and verified
by hand (see the module docstrings in test_swings.py / test_structure.py
for the worked-out expected swing/BOS/CHOCH positions), not generated
randomly.
"""
from __future__ import annotations

import pandas as pd
import pytest

# 14 candles designed to produce exactly:
#   - swing highs at positions 1, 5, 10
#   - swing lows at positions 3, 9
#   (with swing_lookback=1)
# and, when run through structure detection with swing_lookback=1:
#   - a BOS (bullish) at position 4
#   - a CHOCH (bearish) at position 8
#   - a BOS (bearish) at position 11
CLOSES = [1.00, 1.02, 1.01, 1.00, 1.03, 1.05, 1.04, 1.02, 0.98, 0.95, 0.97, 0.94, 0.90, 0.85]


@pytest.fixture
def zigzag_candles() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(CLOSES), freq="1h", tz="UTC")
    close = pd.Series(CLOSES, index=index)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = close + 0.005
    low = close - 0.005
    volume = pd.Series([100.0] * len(CLOSES), index=index)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})
