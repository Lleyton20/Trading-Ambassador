import pytest

from app.instruments import get_instrument_profile
from app.risk.position_size import calculate_position_size
from app.risk.risk_reward import calculate_risk_reward


def test_risk_reward_matches_spec_worked_example():
    # Spec section 18's worked example: entry 1.1700, stop 1.1680, target 1.1760
    result = calculate_risk_reward(entry=1.1700, stop_loss=1.1680, take_profit=1.1760, min_acceptable_rr=2.0)
    assert result.risk == pytest.approx(0.0020)
    assert result.reward == pytest.approx(0.0060)
    assert result.risk_reward_ratio == pytest.approx(3.0)
    assert result.meets_minimum is True
    assert result.quality_label == "ACCEPTABLE RISK/REWARD"


def test_risk_reward_below_minimum_is_flagged_low_quality():
    result = calculate_risk_reward(entry=1.1700, stop_loss=1.1680, take_profit=1.1720, min_acceptable_rr=2.0)
    assert result.risk_reward_ratio == pytest.approx(1.0)
    assert result.meets_minimum is False
    assert result.quality_label == "LOW RISK/REWARD QUALITY"


def test_risk_reward_rejects_zero_risk():
    with pytest.raises(ValueError):
        calculate_risk_reward(entry=1.0, stop_loss=1.0, take_profit=1.1)


def test_position_size_uses_instrument_contract_size():
    eurusd = get_instrument_profile("EURUSD")
    # $10,000 balance, 1% risk => $100 risk. Stop distance 0.0025.
    # contract_size 100,000 => value_per_price_unit=100,000.
    # raw = 100 / (0.0025 * 100000) = 100/250 = 0.4 lots
    result = calculate_position_size(
        account_balance=10_000, risk_pct=1.0, entry_price=1.1000, stop_loss_price=1.0975, instrument=eurusd
    )
    assert result.risk_amount == pytest.approx(100.0)
    assert result.raw_position_size == pytest.approx(0.4)
    assert result.position_size == pytest.approx(0.4)


def test_position_size_clamps_to_instrument_min_lot():
    eurusd = get_instrument_profile("EURUSD")
    result = calculate_position_size(
        account_balance=100, risk_pct=0.1, entry_price=1.1000, stop_loss_price=1.0000, instrument=eurusd
    )
    assert result.position_size >= eurusd.min_lot
