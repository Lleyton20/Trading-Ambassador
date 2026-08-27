import pandas as pd

from app.smc.liquidity import LiquidityLevel, detect_sweep, find_equal_levels


def _ts(hours: int) -> pd.Timestamp:
    return pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(hours=hours)


def test_find_equal_highs_groups_within_tolerance_and_ignores_lone_swings():
    swings = [
        {"timestamp": _ts(0), "price": 1.1000, "kind": "high"},
        {"timestamp": _ts(1), "price": 1.1003, "kind": "high"},  # within tolerance of the first
        {"timestamp": _ts(2), "price": 1.1050, "kind": "high"},  # far away -> lone swing, excluded
    ]
    levels = find_equal_levels(swings, tolerance_pct=0.0005, kind="high")

    assert len(levels) == 1
    assert levels[0].label == "equal_highs"
    assert levels[0].price == (1.1000 + 1.1003) / 2
    assert levels[0].formed_at == _ts(1)


def test_find_equal_lows_groups_within_tolerance():
    swings = [
        {"timestamp": _ts(0), "price": 1.0500, "kind": "low"},
        {"timestamp": _ts(1), "price": 1.0498, "kind": "low"},
    ]
    levels = find_equal_levels(swings, tolerance_pct=0.0005, kind="low")

    assert len(levels) == 1
    assert levels[0].label == "equal_lows"


def test_no_group_below_two_members():
    swings = [{"timestamp": _ts(0), "price": 1.10, "kind": "high"}]
    assert find_equal_levels(swings, tolerance_pct=0.0005, kind="high") == []


def _sweep_df():
    index = pd.date_range("2024-01-02", periods=2, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.101, 1.103],
            "high": [1.105, 1.103],
            "low": [1.100, 1.098],
            "close": [1.102, 1.098],
        },
        index=index,
    )


def test_detect_sweep_of_high_requires_wick_beyond_then_close_back_through():
    level = LiquidityLevel(label="swing_high", kind="high", price=1.10, formed_at=pd.Timestamp("2024-01-01T00:00:00Z"))
    df = _sweep_df()

    event = detect_sweep(df, level)

    assert event is not None
    assert event.swept_at == df.index[1]     # the candle whose close confirms the reversal
    assert event.sweep_extreme == 1.105       # furthest wick reached during the sweep


def test_no_sweep_when_level_never_breached():
    level = LiquidityLevel(label="swing_high", kind="high", price=2.00, formed_at=pd.Timestamp("2024-01-01T00:00:00Z"))
    df = _sweep_df()
    assert detect_sweep(df, level) is None


def test_no_sweep_when_no_candles_after_level_formed():
    level = LiquidityLevel(label="swing_high", kind="high", price=1.10, formed_at=pd.Timestamp("2030-01-01T00:00:00Z"))
    df = _sweep_df()
    assert detect_sweep(df, level) is None
