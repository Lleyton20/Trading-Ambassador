from app.smc.swings import find_swing_highs, find_swing_lows, label_swing_sequence


def test_swing_highs_at_expected_positions(zigzag_candles):
    swings = find_swing_highs(zigzag_candles, lookback=1)
    confirmed = swings.dropna()
    # Hand-verified positions 1, 5, 10 (see conftest.py docstring).
    expected_index = zigzag_candles.index[[1, 5, 10]]
    assert list(confirmed.index) == list(expected_index)
    assert confirmed.iloc[0] == 1.025
    assert confirmed.iloc[1] == 1.055
    assert confirmed.iloc[2] == 0.975


def test_swing_lows_at_expected_positions(zigzag_candles):
    swings = find_swing_lows(zigzag_candles, lookback=1)
    confirmed = swings.dropna()
    expected_index = zigzag_candles.index[[3, 9]]
    assert list(confirmed.index) == list(expected_index)
    assert confirmed.iloc[0] == 0.995
    assert confirmed.iloc[1] == 0.945


def test_label_swing_sequence_marks_first_swing_of_each_kind_as_extreme(zigzag_candles):
    swings = label_swing_sequence(zigzag_candles, lookback=1)
    kinds_and_labels = [(s["kind"], s["label"]) for s in swings]
    # First high seen has nothing to compare against yet -> HH by convention.
    assert kinds_and_labels[0] == ("high", "HH")
    # First low seen has nothing to compare against yet -> LL by convention.
    assert ("low", "LL") in kinds_and_labels
