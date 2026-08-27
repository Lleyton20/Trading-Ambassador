from datetime import date

import pandas as pd

from app.sessions.engine import (
    classify_price_vs_range,
    compute_daily_levels,
    compute_session_ranges,
    detect_session_sweep,
)


def _hourly_utc_candles(start: str, periods: int, prices: list[float]) -> pd.DataFrame:
    index = pd.date_range(start, periods=periods, freq="1h", tz="UTC")
    close = pd.Series(prices, index=index)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = close + 0.5
    low = close - 0.5
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": [10.0] * periods})


def test_opening_day_levels_reset_each_trading_day():
    # Two REAL calendar days of hourly candles (4 hours each), rollover at
    # 00:00 UTC so trading-day boundaries line up with calendar dates.
    day1 = _hourly_utc_candles("2024-01-01T00:00:00Z", 4, [100, 101, 99, 102])
    day2 = _hourly_utc_candles("2024-01-02T00:00:00Z", 4, [103, 97, 105, 96])
    df = pd.concat([day1, day2])

    levels = compute_daily_levels(df, trading_day_timezone="UTC", trading_day_rollover_hour=0)

    day1 = levels.iloc[:4]
    day2 = levels.iloc[4:]

    # Day 1's running high/low should reflect only day 1's candles.
    assert day1["opening_day_high"].iloc[-1] == df["high"].iloc[:4].max()
    assert day1["opening_day_low"].iloc[-1] == df["low"].iloc[:4].min()
    # Day 1 has no previous day yet.
    assert day1["previous_day_high"].isna().all()

    # Day 2 should see day 1's FINAL high/low as its previous_day_high/low,
    # not day 2's own in-progress range.
    assert day2["previous_day_high"].iloc[0] == df["high"].iloc[:4].max()
    assert day2["previous_day_low"].iloc[0] == df["low"].iloc[:4].min()

    # Day 2's own running high should only grow across day 2's candles
    # (no lookahead into candles that haven't happened yet within the day).
    assert day2["opening_day_high"].iloc[0] == df["high"].iloc[4]
    assert day2["opening_day_high"].iloc[-1] == df["high"].iloc[4:8].max()


def test_classify_price_vs_range():
    assert classify_price_vs_range(105, level_high=104, level_low=100) == "above"
    assert classify_price_vs_range(95, level_high=104, level_low=100) == "below"
    assert classify_price_vs_range(102, level_high=104, level_low=100) == "between"


def test_session_ranges_group_by_local_calendar_day():
    # Asian session window: 00:00-09:00 Asia/Tokyo == 15:00-00:00 UTC (prev day).
    # Build candles that fall inside two consecutive Tokyo-local session windows.
    df = _hourly_utc_candles("2024-01-01T15:00:00Z", 6, [100, 101, 99, 98, 103, 97])
    ranges = compute_session_ranges(df, session_timezone="Asia/Tokyo", start_hour=0, end_hour=9)
    assert not ranges.empty
    assert set(ranges.columns) >= {"session_date", "start_time", "end_time", "session_open", "session_high", "session_low", "session_close"}


def test_detect_session_sweep():
    result = detect_session_sweep(session_a_high=110, session_a_low=100, session_b_high=112, session_b_low=101)
    assert result == {"swept_high": True, "swept_low": False}
