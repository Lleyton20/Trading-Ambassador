"""
Session engine: Opening Day High/Low, Asian/London/New York session
ranges, and Previous Day High/Low (spec sections 3-5).

WHY THIS FILE EXISTS
--------------------
The spec is emphatic about two things: (1) "never hard-code session
calculations in multiple places — create one centralized session
configuration", and (2) "make timezone configuration explicit rather than
hiding it inside calculations." Concretely, that means:

  - Every function here takes its timezone/hours as EXPLICIT arguments
    (sourced from `app.config.Settings` by the caller) — nothing in this
    file assumes a timezone silently.
  - We use IANA zone names (e.g. "America/New_York") via Python's
    `zoneinfo`, not fixed UTC offsets. A fixed offset (e.g. "UTC-5") is
    wrong half the year once the US or UK switches for daylight saving —
    zoneinfo looks up the real rule for the date in question, so DST is
    handled correctly for free.
  - All timestamps in and out are tz-aware UTC. Session/day boundaries
    are computed by converting to the *session's* local timezone only
    long enough to find the boundary, then working in UTC again.

NON-LOOKAHEAD BY CONSTRUCTION
------------------------------
"Opening Day High" as of a given candle means the running high from the
start of that trading day THROUGH that candle — not the eventual high for
the whole day (which would leak future information). We use pandas
`cummax`/`cummin` within each trading-day group specifically so every row
only reflects data available up to that row. This matters beyond just
"today's dashboard" — it's what makes these same functions safe to reuse
later inside the backtesting engine without introducing lookahead bias.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd


def _trading_day_key(index: pd.DatetimeIndex, tz_name: str, rollover_hour: int) -> pd.Series:
    """
    Assigns each UTC timestamp to a "trading day" date, where the day
    rolls over at `rollover_hour` local time in `tz_name`.

    Example: rollover_hour=17 in America/New_York means a candle at
    16:59 NY time belongs to "today", and one at 17:01 NY time already
    belongs to "tomorrow's" trading day.
    """
    local = index.tz_convert(ZoneInfo(tz_name))
    shifted = local - pd.Timedelta(hours=rollover_hour)
    return pd.Series(shifted.date, index=index)


def compute_daily_levels(
    df: pd.DataFrame,
    *,
    trading_day_timezone: str,
    trading_day_rollover_hour: int,
) -> pd.DataFrame:
    """
    Returns a DataFrame aligned with `df.index` containing, for every
    candle:
      - trading_day: the trading-day date it belongs to
      - opening_price: that day's first open
      - opening_day_high / opening_day_low: the RUNNING high/low so far
        that day (see module docstring — not the eventual full-day value)
      - previous_day_high / previous_day_low: the prior *completed*
        trading day's final high/low (constant across the current day)
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "trading_day", "opening_price", "opening_day_high", "opening_day_low",
                "previous_day_high", "previous_day_low",
            ]
        )

    trading_day = _trading_day_key(df.index, trading_day_timezone, trading_day_rollover_hour)
    grouped = df.groupby(trading_day)

    opening_price = grouped["open"].transform("first")
    opening_day_high = grouped["high"].cummax()
    opening_day_low = grouped["low"].cummin()

    # Final (completed) high/low per day, then shifted forward one day so
    # "today" sees "yesterday's" finished range, never its own in-progress one.
    day_final_high = grouped["high"].max()
    day_final_low = grouped["low"].min()
    prev_high_by_day = day_final_high.shift(1)
    prev_low_by_day = day_final_low.shift(1)

    previous_day_high = trading_day.map(prev_high_by_day)
    previous_day_low = trading_day.map(prev_low_by_day)

    return pd.DataFrame(
        {
            "trading_day": trading_day,
            "opening_price": opening_price,
            "opening_day_high": opening_day_high,
            "opening_day_low": opening_day_low,
            "previous_day_high": previous_day_high,
            "previous_day_low": previous_day_low,
        },
        index=df.index,
    )


def classify_price_vs_range(
    price: float, level_high: float, level_low: float, *, testing_tolerance_pct: float = 0.0005
) -> str:
    """
    Classifies price relative to a high/low range as one of:
    "above", "below", "between", "testing_high", "testing_low".

    `testing_tolerance_pct` defines how close price must be to a level to
    count as "testing" it rather than simply being "between".
    """
    span = max(level_high - level_low, 1e-9)
    tolerance = span * testing_tolerance_pct * 100  # tolerance scaled relative to range

    if price > level_high:
        return "above"
    if price < level_low:
        return "below"
    if abs(price - level_high) <= tolerance:
        return "testing_high"
    if abs(price - level_low) <= tolerance:
        return "testing_low"
    return "between"


def is_within_session_hours(
    timestamp: pd.Timestamp, *, session_timezone: str, start_hour: int, end_hour: int
) -> bool:
    """
    Whether `timestamp` falls within this session's local start/end hour
    window (same rule `compute_session_ranges` groups candles by, factored
    out so a single timestamp - e.g. "is the latest candle in London
    hours?" - can be checked without generating a full session range).
    """
    local_hour = timestamp.tz_convert(ZoneInfo(session_timezone)).hour
    return start_hour <= local_hour < end_hour


def compute_session_ranges(
    df: pd.DataFrame,
    *,
    session_timezone: str,
    start_hour: int,
    end_hour: int,
) -> pd.DataFrame:
    """
    Computes one row per session instance (per calendar date in the
    session's own timezone): open/high/low/close and start/end time (UTC).

    LIMITATION (documented, not hidden): this milestone assumes
    start_hour < end_hour, i.e. the session does not cross local
    midnight. All three default sessions (Asian/London/New York) satisfy
    this. Supporting a wrapping session window is a small, isolated
    follow-up if a future session config needs it.
    """
    if start_hour >= end_hour:
        raise ValueError(
            "compute_session_ranges requires start_hour < end_hour "
            "(overnight-wrapping sessions are not supported yet)"
        )

    if df.empty:
        return pd.DataFrame(
            columns=["session_date", "start_time", "end_time", "session_open", "session_high", "session_low", "session_close"]
        )

    local_index = df.index.tz_convert(ZoneInfo(session_timezone))
    in_session = (local_index.hour >= start_hour) & (local_index.hour < end_hour)
    session_df = df[in_session]
    if session_df.empty:
        return pd.DataFrame(
            columns=["session_date", "start_time", "end_time", "session_open", "session_high", "session_low", "session_close"]
        )

    session_local_dates = local_index[in_session].date
    grouped = session_df.groupby(session_local_dates)

    result = grouped.agg(
        session_open=("open", "first"),
        session_high=("high", "max"),
        session_low=("low", "min"),
        session_close=("close", "last"),
    )
    result["start_time"] = grouped.apply(lambda g: g.index.min())
    result["end_time"] = grouped.apply(lambda g: g.index.max())
    result.index.name = "session_date"
    return result.reset_index()


def detect_session_sweep(session_a_high: float, session_a_low: float, session_b_high: float, session_b_low: float) -> dict:
    """
    Checks whether session B swept session A's high and/or low — e.g.
    "did London sweep the Asian high/low?" (spec section 4).
    """
    return {
        "swept_high": session_b_high > session_a_high,
        "swept_low": session_b_low < session_a_low,
    }
