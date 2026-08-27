import pandas as pd

from app.market_data.validation import validate_candles


def _good_df():
    index = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
    open_ = pd.Series([1.00, 1.01, 1.02, 1.01, 1.03], index=index)
    close = pd.Series([1.01, 1.02, 1.01, 1.03, 1.035], index=index)
    # Derive high/low FROM open/close so the OHLC relationship is valid by
    # construction, rather than risking a hand-picked value that violates it.
    high = pd.concat([open_, close], axis=1).max(axis=1) + 0.01
    low = pd.concat([open_, close], axis=1).min(axis=1) - 0.01
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def test_valid_candles_pass():
    result = validate_candles(_good_df())
    assert result.is_valid


def test_invalid_ohlc_relationship_is_flagged():
    df = _good_df()
    df.loc[df.index[0], "high"] = 0.5  # high below open/close/low -> invalid
    result = validate_candles(df)
    assert not result.is_valid
    assert any(i.kind == "invalid_ohlc_relationship" for i in result.issues)


def test_duplicate_timestamps_are_flagged():
    df = _good_df()
    duplicated = pd.concat([df, df.iloc[[0]]])
    result = validate_candles(duplicated)
    assert any(i.kind == "duplicate_timestamps" for i in result.issues)


def test_missing_ohlc_value_is_flagged():
    df = _good_df()
    df.loc[df.index[2], "close"] = float("nan")
    result = validate_candles(df)
    assert any(i.kind == "missing_ohlc" for i in result.issues)


def test_extreme_price_jump_is_flagged():
    df = _good_df()
    df.loc[df.index[-1], "close"] = df["close"].iloc[-2] * 5  # 400% jump
    result = validate_candles(df)
    assert any(i.kind == "extreme_price_jump" for i in result.issues)
