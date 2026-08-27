import pandas as pd

from app.smc.displacement import detect_displacement, is_displacement_candle
from app.smc.indicators import calculate_atr


def _df():
    index = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    # Small, steady candles except position 3, which is a large displacement move.
    open_ = [1.000, 1.002, 1.000, 0.997, 1.055, 1.058]
    close = [1.002, 1.000, 1.003, 1.055, 1.058, 1.060]
    high = [1.005, 1.007, 1.006, 1.060, 1.062, 1.065]
    low = [0.995, 0.997, 0.994, 0.995, 1.050, 1.052]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def test_detect_displacement_flags_only_the_large_body_candle():
    df = _df()
    flags = detect_displacement(df, min_atr_multiple=1.5, atr_period=3)
    # ATR needs 3 true-range values to warm up, so positions 0-1 are NaN/False.
    assert flags.iloc[3] == True  # noqa: E712  (large body relative to preceding ATR)
    assert flags.iloc[0] == False  # noqa: E712


def test_is_displacement_candle_matches_series_result():
    df = _df()
    atr = calculate_atr(df, period=3)
    assert is_displacement_candle(df, 3, atr, min_atr_multiple=1.5)
    assert not is_displacement_candle(df, 5, atr, min_atr_multiple=1.5)


def test_is_displacement_candle_false_when_atr_not_yet_available():
    df = _df()
    atr = calculate_atr(df, period=3)
    assert not is_displacement_candle(df, 0, atr, min_atr_multiple=1.5)
