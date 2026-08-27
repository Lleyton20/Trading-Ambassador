"""
Verifies order-block detection against a hand-worked-out example.

Candle 3 (index 3) is the last BEARISH candle before candle 4, a large
bullish displacement candle. A bullish BOS "confirmed" at candle 4 should
therefore produce an order block zoned to candle 3's high/low — but only
because candle 4 clears the displacement threshold; a break confirmed on
an ordinary small candle should NOT produce an order block at all.

ATR math (period=3), worked by hand:
  true_range: [0.010, 0.010, 0.012, 0.011, 0.065, 0.012]
  ATR(3) at pos 2 = mean(tr0,tr1,tr2) = 0.010667
  ATR(3) at pos 3 = mean(tr1,tr2,tr3) = 0.011
  ATR(3) at pos 4 = mean(tr2,tr3,tr4) = 0.029333
  ATR(3) at pos 5 = mean(tr3,tr4,tr5) = 0.029333

  Candle 4 body = |1.055 - 0.997| = 0.058 >= 0.029333 * 1.5 (0.044) -> displacement: YES
  Candle 5 body = |1.058 - 1.055| = 0.003 <  0.029333 * 1.5 (0.044) -> displacement: NO
"""
import pandas as pd

from app.smc.order_blocks import apply_mitigation, detect_order_blocks
from app.smc.structure import StructureEvent


def _df():
    index = pd.date_range("2024-01-01", periods=7, freq="1h", tz="UTC")
    open_ = [1.000, 1.002, 1.000, 1.003, 0.997, 1.055, 1.058]
    high = [1.005, 1.007, 1.006, 1.006, 1.060, 1.062, 1.065]
    low = [0.995, 0.997, 0.994, 0.995, 0.995, 1.050, 1.052]
    close = [1.002, 1.000, 1.003, 0.997, 1.055, 1.058, 1.060]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def test_order_block_created_from_displacement_confirmed_bos():
    df = _df()
    event = StructureEvent(timestamp=df.index[4], event_type="BOS", direction="bullish", price=1.055, broken_level=1.006)

    obs = detect_order_blocks(df, [event], lookback_candles=10, min_displacement_atr_multiple=1.5, atr_period=3)

    assert len(obs) == 1
    ob = obs[0]
    assert ob.direction == "bullish"
    assert ob.structure_event_type == "BOS"
    assert ob.created_at == df.index[3]  # the last bearish candle before the displacement
    assert ob.zone_low == 0.995
    assert ob.zone_high == 1.006


def test_no_order_block_when_confirming_candle_lacks_displacement():
    df = _df()
    # Candle at position 5 has a tiny body -> fails the displacement check.
    event = StructureEvent(timestamp=df.index[5], event_type="BOS", direction="bearish", price=1.058, broken_level=1.060)

    obs = detect_order_blocks(df, [event], lookback_candles=10, min_displacement_atr_multiple=1.5, atr_period=3)

    assert obs == []


def test_mitigation_marks_first_touch_and_counts_retests():
    df = _df()
    event = StructureEvent(timestamp=df.index[4], event_type="BOS", direction="bullish", price=1.055, broken_level=1.006)
    obs = detect_order_blocks(df, [event], atr_period=3)
    apply_mitigation(df, obs)

    ob = obs[0]
    assert ob.mitigated is True
    assert ob.mitigated_at == df.index[4]  # candle 4's low (0.995) dips back into the zone
    assert ob.retest_count == 1
