import pandas as pd

from app.smc.premium_discount import classify_premium_discount, determine_active_dealing_range


def _ts(hours: int) -> pd.Timestamp:
    return pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(hours=hours)


def test_dealing_range_uses_most_recent_swing_of_each_kind():
    swings = [
        {"timestamp": _ts(0), "price": 1.10, "kind": "high"},
        {"timestamp": _ts(1), "price": 1.00, "kind": "low"},
        {"timestamp": _ts(2), "price": 1.20, "kind": "high"},  # most recent high
        {"timestamp": _ts(3), "price": 1.05, "kind": "low"},   # most recent low
    ]
    dealing_range = determine_active_dealing_range(swings)

    assert dealing_range is not None
    assert dealing_range.range_high == 1.20
    assert dealing_range.range_low == 1.05
    assert dealing_range.equilibrium == (1.20 + 1.05) / 2


def test_dealing_range_none_without_both_kinds():
    assert determine_active_dealing_range([{"timestamp": _ts(0), "price": 1.10, "kind": "high"}]) is None
    assert determine_active_dealing_range([]) is None


def test_classify_premium_discount_and_equilibrium():
    swings = [
        {"timestamp": _ts(0), "price": 1.20, "kind": "high"},
        {"timestamp": _ts(1), "price": 1.00, "kind": "low"},
    ]
    dealing_range = determine_active_dealing_range(swings)  # equilibrium = 1.10

    assert classify_premium_discount(1.15, dealing_range) == "premium"
    assert classify_premium_discount(1.05, dealing_range) == "discount"
    assert classify_premium_discount(1.10, dealing_range) == "equilibrium"
