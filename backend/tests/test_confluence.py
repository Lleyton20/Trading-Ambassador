"""
Tests for the confluence scoring engine (app/confluence/engine.py).

`calculate_confluence_score` is a pure function over plain booleans/weights
- no candle fixtures needed, every case here is hand-picked to exercise
one factor at a time.
"""
from __future__ import annotations

from app.confluence.engine import HTF_MAP, calculate_confluence_score

_WEIGHTS = dict(
    weight_htf_bias=2,
    weight_liquidity_sweep=2,
    weight_choch=2,
    weight_fvg=1,
    weight_order_block=1,
    weight_premium_discount=1,
    weight_session=1,
)
_MAX_SCORE = sum(_WEIGHTS.values())  # 10


def _score(**overrides):
    base = dict(
        bias="bullish",
        htf_bias="bearish",  # opposed by default, so htf_bias_aligned starts unmet
        has_recent_liquidity_sweep=False,
        has_recent_choch=False,
        has_unmitigated_fvg_with_bias=False,
        has_unmitigated_order_block_with_bias=False,
        price_favors_bias=False,
        session_active=False,
    )
    base.update(overrides)
    return calculate_confluence_score(**base, **_WEIGHTS)


def test_no_factors_met_scores_zero():
    result = _score()
    assert result.score == 0
    assert result.max_score == _MAX_SCORE
    assert result.score_pct == 0.0
    assert all(not f.met for f in result.factors)


def test_all_factors_met_scores_max():
    result = _score(
        htf_bias="bullish",
        has_recent_liquidity_sweep=True,
        has_recent_choch=True,
        has_unmitigated_fvg_with_bias=True,
        has_unmitigated_order_block_with_bias=True,
        price_favors_bias=True,
        session_active=True,
    )
    assert result.score == _MAX_SCORE
    assert result.score_pct == 100.0


def test_htf_bias_must_match_and_not_be_neutral():
    # Same non-neutral bias on both timeframes -> met.
    aligned = next(f for f in _score(bias="bullish", htf_bias="bullish").factors if f.name == "htf_bias_aligned")
    assert aligned.met is True

    # Opposing bias -> not met.
    opposed = next(f for f in _score(bias="bullish", htf_bias="bearish").factors if f.name == "htf_bias_aligned")
    assert opposed.met is False

    # Neutral bias never counts as "aligned", even if htf_bias also neutral.
    neutral = next(f for f in _score(bias="neutral", htf_bias="neutral").factors if f.name == "htf_bias_aligned")
    assert neutral.met is False


def test_weights_are_summed_not_counted():
    # liquidity_sweep + choch = 2 + 2 = 4, not "2 factors met".
    result = _score(has_recent_liquidity_sweep=True, has_recent_choch=True)
    assert result.score == 4


def test_htf_map_covers_every_supported_timeframe():
    for tf in ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]:
        assert tf in HTF_MAP
