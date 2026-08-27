"""
Hand-worked three-candle FVG example (see module docstring in
app/smc/fvg.py for the general rule).

Candles 0-2 form a bullish gap (candle 2's low, 1.02, is above candle 0's
high, 1.00). Candles 1-3 form a bearish gap (candle 3's high, 0.99, is
below candle 1's low, 0.995). Candle 4 trades partway back into the
bullish gap to exercise mitigation percentage.
"""
import pandas as pd
import pytest

from app.smc.fvg import apply_mitigation, detect_fair_value_gaps


def _df():
    index = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
    open_ = [1.00, 1.00, 1.04, 0.99, 1.01]
    high = [1.00, 1.05, 1.06, 0.99, 1.025]
    low = [0.99, 0.995, 1.02, 0.95, 1.005]
    close = [1.00, 1.04, 1.03, 0.96, 1.01]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def test_detects_bullish_and_bearish_gaps():
    df = _df()
    gaps = detect_fair_value_gaps(df)

    assert len(gaps) == 2
    bullish, bearish = gaps

    assert bullish.direction == "bullish"
    assert bullish.lower == 1.00   # candle 0's high
    assert bullish.upper == 1.02   # candle 2's low
    assert bullish.created_at == df.index[2]

    assert bearish.direction == "bearish"
    assert bearish.upper == 0.995  # candle 1's low
    assert bearish.lower == 0.99   # candle 3's high
    assert bearish.created_at == df.index[3]


def test_mitigation_percentage_reflects_partial_fill():
    df = _df()
    gaps = detect_fair_value_gaps(df)
    apply_mitigation(df, gaps)

    bullish = gaps[0]
    # Candle 4 (low 1.005, high 1.015) reaches 0.015 of the way down into
    # a 0.02-wide gap (1.02 - 1.00): 0.015 / 0.02 = 75%.
    assert bullish.mitigated_pct == pytest.approx(0.75)
