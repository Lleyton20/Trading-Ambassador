"""
Verifies the BOS-vs-CHOCH distinction against a hand-worked-out example.

The expected sequence (worked out by hand against `zigzag_candles`,
swing_lookback=1) is:
  1. BOS  bullish at index 4  (close 1.03 breaks confirmed swing high 1.025;
     bias was neutral, so the first break is a BOS, not a reversal)
  2. CHOCH bearish at index 8 (close 0.98 breaks confirmed swing low 0.995;
     this is AGAINST the prevailing bullish bias, so it's a CHOCH)
  3. BOS  bearish at index 11 (close 0.94 breaks confirmed swing low 0.945;
     bias is already bearish, so this is a continuation BOS, not a CHOCH)
"""
from app.smc.structure import detect_structure_events


def test_bos_and_choch_sequence(zigzag_candles):
    events, final_bias = detect_structure_events(zigzag_candles, swing_lookback=1)

    assert len(events) == 3

    first, second, third = events

    assert first.event_type == "BOS"
    assert first.direction == "bullish"
    assert first.timestamp == zigzag_candles.index[4]
    assert first.broken_level == 1.025

    assert second.event_type == "CHOCH"
    assert second.direction == "bearish"
    assert second.timestamp == zigzag_candles.index[8]
    assert second.broken_level == 0.995

    assert third.event_type == "BOS"
    assert third.direction == "bearish"
    assert third.timestamp == zigzag_candles.index[11]
    assert third.broken_level == 0.945

    assert final_bias == "bearish"


def test_no_events_when_price_never_breaks_a_confirmed_swing(zigzag_candles):
    # A huge min_displacement means nothing ever clears a level.
    events, bias = detect_structure_events(zigzag_candles, swing_lookback=1, min_displacement=10.0)
    assert events == []
    assert bias == "neutral"
