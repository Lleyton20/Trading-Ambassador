"""
REST API routes (spec section 35).

Every route here is thin: it pulls candles from the injected
MarketDataProvider, hands them to the pure functions in
app/sessions/engine.py, app/smc/*, app/risk/* to do the actual analysis,
and shapes the result into a response schema. No trading decision, no
BUY/SELL signal, is ever emitted — per the spec's core principle, this
platform presents evidence (structure, levels, RR math) and lets the
person decide.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app import persistence
from app.confluence.engine import HTF_MAP, calculate_confluence_score
from app.config import settings
from app.database import get_db
from app.instruments import INSTRUMENT_PROFILES, get_instrument_profile
from app.market_data.base import MarketDataProvider
from app.market_data.validation import validate_candles
from app.risk.position_size import calculate_position_size
from app.risk.risk_reward import calculate_risk_reward
from app.schemas.analysis import (
    CandleOut,
    ConfluenceFactorOut,
    ConfluenceOut,
    DailyLevelsOut,
    FairValueGapOut,
    LiquidityAnalysisOut,
    LiquidityLevelOut,
    MarketOverviewOut,
    MarketSummary,
    OrderBlockOut,
    PositionSizeOut,
    PositionSizeRequest,
    PremiumDiscountOut,
    RiskRewardOut,
    RiskRewardRequest,
    SessionRangeOut,
    SmcAnalysisOut,
    StructureEventOut,
    SwingPointOut,
)
from app.sessions.engine import (
    classify_price_vs_range,
    compute_daily_levels,
    compute_session_ranges,
    is_within_session_hours,
)
from app.smc.fvg import apply_mitigation as apply_fvg_mitigation
from app.smc.fvg import detect_fair_value_gaps
from app.smc.liquidity import LiquidityLevel, detect_sweep, find_equal_levels
from app.smc.order_blocks import apply_mitigation as apply_ob_mitigation
from app.smc.order_blocks import detect_order_blocks
from app.smc.premium_discount import classify_premium_discount, determine_active_dealing_range
from app.smc.structure import detect_structure_events
from app.smc.swings import label_swing_sequence

router = APIRouter()

_SESSION_CONFIGS = {
    "asian": ("asian_session_timezone", "asian_session_start_hour", "asian_session_end_hour"),
    "london": ("london_session_timezone", "london_session_start_hour", "london_session_end_hour"),
    "new_york": ("new_york_session_timezone", "new_york_session_start_hour", "new_york_session_end_hour"),
}


def _get_provider(request: Request) -> MarketDataProvider:
    return request.app.state.provider


def _require_known_symbol(symbol: str) -> None:
    try:
        get_instrument_profile(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _fetch_valid_candles(provider: MarketDataProvider, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
    try:
        df = provider.get_candles(symbol, timeframe, count=count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    check = validate_candles(df)
    if not check.is_valid:
        # Surfaced, never silently swallowed (spec sections 36 & 39).
        kinds = sorted({issue.kind for issue in check.issues})
        raise HTTPException(status_code=502, detail=f"Data quality issues detected: {kinds}")
    return df


@router.get("/markets", response_model=list[MarketSummary])
def list_markets(request: Request):
    provider = _get_provider(request)
    return [
        MarketSummary(
            symbol=symbol,
            display_name=profile.display_name,
            asset_class=profile.asset_class.value,
            current_price=provider.get_latest_price(symbol),
        )
        for symbol, profile in INSTRUMENT_PROFILES.items()
    ]


@router.get("/markets/{symbol}/candles", response_model=list[CandleOut])
def get_candles(symbol: str, request: Request, timeframe: str = Query("H1"), count: int = Query(200, le=2000)):
    _require_known_symbol(symbol)
    df = _fetch_valid_candles(_get_provider(request), symbol, timeframe, count)
    return [
        CandleOut(timestamp=ts, open=row.open, high=row.high, low=row.low, close=row.close, volume=row.volume)
        for ts, row in df.iterrows()
    ]


@router.get("/markets/{symbol}/daily-levels", response_model=DailyLevelsOut)
def get_daily_levels(symbol: str, request: Request, timeframe: str = Query("M15")):
    _require_known_symbol(symbol)
    df = _fetch_valid_candles(_get_provider(request), symbol, timeframe, 500)

    levels_df = compute_daily_levels(
        df,
        trading_day_timezone=settings.trading_day_timezone,
        trading_day_rollover_hour=settings.trading_day_rollover_hour,
    )
    if levels_df.empty:
        raise HTTPException(status_code=404, detail="Not enough candle data to compute daily levels")

    last = levels_df.iloc[-1]
    current_price = float(df["close"].iloc[-1])
    status = classify_price_vs_range(current_price, float(last.opening_day_high), float(last.opening_day_low))

    return DailyLevelsOut(
        symbol=symbol,
        trading_day=str(last.trading_day),
        opening_price=float(last.opening_price),
        opening_day_high=float(last.opening_day_high),
        opening_day_low=float(last.opening_day_low),
        previous_day_high=None if pd.isna(last.previous_day_high) else float(last.previous_day_high),
        previous_day_low=None if pd.isna(last.previous_day_low) else float(last.previous_day_low),
        current_price=current_price,
        price_status=status,
    )


@router.get("/markets/{symbol}/sessions", response_model=list[SessionRangeOut])
def get_sessions(symbol: str, request: Request, timeframe: str = Query("M15")):
    _require_known_symbol(symbol)
    df = _fetch_valid_candles(_get_provider(request), symbol, timeframe, 500)

    output: list[SessionRangeOut] = []
    for name, (tz_key, start_key, end_key) in _SESSION_CONFIGS.items():
        ranges = compute_session_ranges(
            df,
            session_timezone=getattr(settings, tz_key),
            start_hour=getattr(settings, start_key),
            end_hour=getattr(settings, end_key),
        )
        if ranges.empty:
            continue
        last = ranges.iloc[-1]
        output.append(
            SessionRangeOut(
                session_name=name,
                session_date=str(last.session_date),
                session_open=float(last.session_open),
                session_high=float(last.session_high),
                session_low=float(last.session_low),
                session_close=float(last.session_close),
                start_time=last.start_time,
                end_time=last.end_time,
            )
        )
    return output


@router.get("/markets/{symbol}/smc", response_model=SmcAnalysisOut)
def get_smc_analysis(symbol: str, request: Request, timeframe: str = Query("H1"), db: Session = Depends(get_db)):
    """
    The full "SMC ANALYSIS" panel: structure/bias, order blocks, fair
    value gaps, and premium/discount — all derived from the same
    validated swing points and structure events (spec section 29).
    """
    _require_known_symbol(symbol)
    df = _fetch_valid_candles(_get_provider(request), symbol, timeframe, 500)

    swings = label_swing_sequence(df, lookback=settings.swing_lookback)
    events, bias = detect_structure_events(df, swing_lookback=settings.swing_lookback)

    order_blocks = detect_order_blocks(
        df, events,
        min_displacement_atr_multiple=settings.min_displacement_atr_mult,
    )
    apply_ob_mitigation(df, order_blocks)

    gaps = detect_fair_value_gaps(df)
    apply_fvg_mitigation(df, gaps)

    # Side effect: record this analysis to its DB tables (audit trail for
    # a future backtester/journal) — the response above is still always
    # computed fresh from live candles, never read back from these rows.
    persistence.seed_instruments(db)
    persistence.persist_swing_points(db, symbol, timeframe, swings)
    persistence.persist_structure_events(db, symbol, timeframe, events)
    persistence.persist_order_blocks(db, symbol, timeframe, order_blocks)
    persistence.persist_fair_value_gaps(db, symbol, timeframe, gaps)

    premium_discount_out: PremiumDiscountOut | None = None
    dealing_range = determine_active_dealing_range(swings)
    if dealing_range is not None:
        current_price = float(df["close"].iloc[-1])
        status = classify_premium_discount(current_price, dealing_range)
        premium_discount_out = PremiumDiscountOut(
            range_high=dealing_range.range_high, range_low=dealing_range.range_low,
            equilibrium=dealing_range.equilibrium, status=status,
        )

    return SmcAnalysisOut(
        symbol=symbol,
        timeframe=timeframe,
        bias=bias,
        swing_points=[SwingPointOut(**s) for s in swings[-20:]],
        structure_events=[
            StructureEventOut(
                timestamp=e.timestamp, event_type=e.event_type, direction=e.direction,
                price=e.price, broken_level=e.broken_level,
            )
            for e in events[-20:]
        ],
        order_blocks=[
            OrderBlockOut(
                direction=ob.direction, zone_low=ob.zone_low, zone_high=ob.zone_high,
                created_at=ob.created_at, structure_event_type=ob.structure_event_type,
                mitigated=ob.mitigated, mitigated_at=ob.mitigated_at, retest_count=ob.retest_count,
            )
            for ob in order_blocks[-20:]
        ],
        fair_value_gaps=[
            FairValueGapOut(
                direction=g.direction, upper=g.upper, lower=g.lower,
                created_at=g.created_at, mitigated_pct=g.mitigated_pct,
            )
            for g in gaps[-20:]
        ],
        premium_discount=premium_discount_out,
    )


@router.get("/markets/{symbol}/liquidity", response_model=LiquidityAnalysisOut)
def get_liquidity_analysis(symbol: str, request: Request, timeframe: str = Query("H1"), db: Session = Depends(get_db)):
    """
    Liquidity levels (swing-based equal highs/lows plus previous-day
    high/low) with each level's sweep status (spec sections 5, 6, 11, 12).
    """
    _require_known_symbol(symbol)
    provider = _get_provider(request)
    df = _fetch_valid_candles(provider, symbol, timeframe, 500)

    swings = label_swing_sequence(df, lookback=settings.swing_lookback)
    levels: list[LiquidityLevel] = find_equal_levels(
        swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="high"
    ) + find_equal_levels(swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="low")

    # Previous Day High/Low, once known, are liquidity levels too.
    daily_df = _fetch_valid_candles(provider, symbol, "M15", 500)
    daily_levels_df = compute_daily_levels(
        daily_df,
        trading_day_timezone=settings.trading_day_timezone,
        trading_day_rollover_hour=settings.trading_day_rollover_hour,
    )
    if not daily_levels_df.empty:
        last = daily_levels_df.iloc[-1]
        current_day_rows = daily_levels_df[daily_levels_df["trading_day"] == last.trading_day]
        known_since = current_day_rows.index.min()  # PDH/PDL become known at today's open
        if pd.notna(last.previous_day_high):
            levels.append(LiquidityLevel(label="previous_day_high", kind="high", price=float(last.previous_day_high), formed_at=known_since))
        if pd.notna(last.previous_day_low):
            levels.append(LiquidityLevel(label="previous_day_low", kind="low", price=float(last.previous_day_low), formed_at=known_since))

    levels_out: list[LiquidityLevelOut] = []
    sweep_pairs: list[tuple] = []
    for level in levels:
        sweep = detect_sweep(df, level)
        sweep_pairs.append((level, sweep))
        levels_out.append(
            LiquidityLevelOut(
                label=level.label, kind=level.kind, price=level.price, formed_at=level.formed_at,
                swept=sweep is not None, swept_at=sweep.swept_at if sweep else None,
            )
        )

    persistence.seed_instruments(db)
    level_ids = persistence.persist_liquidity_levels(db, symbol, timeframe, levels)
    persistence.persist_liquidity_sweeps(db, level_ids, sweep_pairs)

    return LiquidityAnalysisOut(symbol=symbol, timeframe=timeframe, levels=levels_out)


@router.get("/markets/{symbol}/analysis", response_model=MarketOverviewOut)
def get_market_overview(symbol: str, request: Request):
    """
    The "Market Overview" the dashboard's top card needs: current price,
    higher-timeframe bias, and today's key levels, in one call.
    """
    _require_known_symbol(symbol)
    provider = _get_provider(request)

    h1_df = _fetch_valid_candles(provider, symbol, "H1", 500)
    _, bias = detect_structure_events(h1_df, swing_lookback=settings.swing_lookback)

    daily_levels_out: DailyLevelsOut | None = None
    m15_df = _fetch_valid_candles(provider, symbol, "M15", 500)
    levels_df = compute_daily_levels(
        m15_df,
        trading_day_timezone=settings.trading_day_timezone,
        trading_day_rollover_hour=settings.trading_day_rollover_hour,
    )
    current_price = provider.get_latest_price(symbol)
    if not levels_df.empty:
        last = levels_df.iloc[-1]
        status = classify_price_vs_range(current_price, float(last.opening_day_high), float(last.opening_day_low))
        daily_levels_out = DailyLevelsOut(
            symbol=symbol,
            trading_day=str(last.trading_day),
            opening_price=float(last.opening_price),
            opening_day_high=float(last.opening_day_high),
            opening_day_low=float(last.opening_day_low),
            previous_day_high=None if pd.isna(last.previous_day_high) else float(last.previous_day_high),
            previous_day_low=None if pd.isna(last.previous_day_low) else float(last.previous_day_low),
            current_price=current_price,
            price_status=status,
        )

    sessions_out: list[SessionRangeOut] = []
    for name, (tz_key, start_key, end_key) in _SESSION_CONFIGS.items():
        ranges = compute_session_ranges(
            m15_df,
            session_timezone=getattr(settings, tz_key),
            start_hour=getattr(settings, start_key),
            end_hour=getattr(settings, end_key),
        )
        if ranges.empty:
            continue
        last = ranges.iloc[-1]
        sessions_out.append(
            SessionRangeOut(
                session_name=name,
                session_date=str(last.session_date),
                session_open=float(last.session_open),
                session_high=float(last.session_high),
                session_low=float(last.session_low),
                session_close=float(last.session_close),
                start_time=last.start_time,
                end_time=last.end_time,
            )
        )

    return MarketOverviewOut(
        symbol=symbol, current_price=current_price, bias=bias,
        daily_levels=daily_levels_out, sessions=sessions_out,
    )


@router.post("/risk/risk-reward", response_model=RiskRewardOut)
def post_risk_reward(payload: RiskRewardRequest):
    try:
        result = calculate_risk_reward(
            payload.entry, payload.stop_loss, payload.take_profit,
            min_acceptable_rr=payload.min_acceptable_rr or settings.min_acceptable_rr,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RiskRewardOut(**result.__dict__)


@router.post("/risk/position-size", response_model=PositionSizeOut)
def post_position_size(payload: PositionSizeRequest):
    try:
        instrument = get_instrument_profile(payload.symbol)
        result = calculate_position_size(
            payload.account_balance, payload.risk_pct, payload.entry_price, payload.stop_loss_price, instrument,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PositionSizeOut(**result.__dict__)


@router.get("/markets/{symbol}/confluence", response_model=ConfluenceOut)
def get_confluence(symbol: str, request: Request, timeframe: str = Query("H1")):
    """
    Combines the same evidence the /smc and /liquidity endpoints already
    expose into one weighted confluence score (spec Milestone 3) —
    evidence, not a BUY/SELL signal (see app/confluence/engine.py).
    """
    _require_known_symbol(symbol)
    provider = _get_provider(request)

    df = _fetch_valid_candles(provider, symbol, timeframe, 500)
    swings = label_swing_sequence(df, lookback=settings.swing_lookback)
    events, bias = detect_structure_events(df, swing_lookback=settings.swing_lookback)

    htf_timeframe = HTF_MAP.get(timeframe, timeframe)
    htf_df = _fetch_valid_candles(provider, symbol, htf_timeframe, 500)
    _, htf_bias = detect_structure_events(htf_df, swing_lookback=settings.swing_lookback)

    order_blocks = detect_order_blocks(df, events, min_displacement_atr_multiple=settings.min_displacement_atr_mult)
    apply_ob_mitigation(df, order_blocks)
    gaps = detect_fair_value_gaps(df)
    apply_fvg_mitigation(df, gaps)

    price_favors_bias = False
    dealing_range = determine_active_dealing_range(swings)
    if dealing_range is not None:
        current_price = float(df["close"].iloc[-1])
        status = classify_premium_discount(current_price, dealing_range)
        # SMC convention: look to buy in a discount, sell in a premium.
        price_favors_bias = (bias == "bullish" and status == "discount") or (bias == "bearish" and status == "premium")

    has_recent_choch = any(e.event_type == "CHOCH" for e in events[-20:])
    has_unmitigated_fvg = any(g.direction == bias and g.mitigated_pct < 100.0 for g in gaps)
    has_unmitigated_ob = any(ob.direction == bias and not ob.mitigated for ob in order_blocks)

    levels: list[LiquidityLevel] = find_equal_levels(
        swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="high"
    ) + find_equal_levels(swings, tolerance_pct=settings.liquidity_tolerance_pct, kind="low")
    has_recent_sweep = any(detect_sweep(df, level) is not None for level in levels)

    latest_ts = df.index[-1]
    session_active = any(
        is_within_session_hours(
            latest_ts,
            session_timezone=getattr(settings, tz_key),
            start_hour=getattr(settings, start_key),
            end_hour=getattr(settings, end_key),
        )
        for tz_key, start_key, end_key in _SESSION_CONFIGS.values()
    )

    result = calculate_confluence_score(
        bias=bias,
        htf_bias=htf_bias,
        has_recent_liquidity_sweep=has_recent_sweep,
        has_recent_choch=has_recent_choch,
        has_unmitigated_fvg_with_bias=has_unmitigated_fvg,
        has_unmitigated_order_block_with_bias=has_unmitigated_ob,
        price_favors_bias=price_favors_bias,
        session_active=session_active,
        weight_htf_bias=settings.confluence_weight_htf_bias,
        weight_liquidity_sweep=settings.confluence_weight_liquidity_sweep,
        weight_choch=settings.confluence_weight_choch,
        weight_fvg=settings.confluence_weight_fvg,
        weight_order_block=settings.confluence_weight_order_block,
        weight_premium_discount=settings.confluence_weight_premium_discount,
        weight_session=settings.confluence_weight_session,
    )

    return ConfluenceOut(
        symbol=symbol,
        timeframe=timeframe,
        htf_timeframe=htf_timeframe,
        bias=bias,
        htf_bias=htf_bias,
        score=result.score,
        max_score=result.max_score,
        score_pct=result.score_pct,
        factors=[ConfluenceFactorOut(name=f.name, weight=f.weight, met=f.met) for f in result.factors],
    )
