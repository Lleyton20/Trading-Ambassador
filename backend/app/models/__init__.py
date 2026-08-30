"""
SQLAlchemy models, split by concern rather than one giant file (spec
section 27: "Do not put everything into one table" / one file).

These tables cover the analysis pipeline through Milestone 3, plus
price-in-zone alerts: instruments, candles, swing_points,
market_structure_events, order_blocks, fair_value_gaps, liquidity_levels,
liquidity_sweeps, sessions, daily_levels, alerts. Trade setups, backtests,
and journal entries are deliberately NOT modeled yet — they belong to
later milestones, and an empty table with a guessed-at schema is worse
than no table (it invites drift between the schema and the code that
will eventually fill it).
"""
from app.models.alert import Alert
from app.models.candle import Candle
from app.models.instrument import Instrument
from app.models.liquidity import LiquidityLevel, LiquiditySweep
from app.models.session import DailyLevels, SessionRecord
from app.models.smc import FairValueGap, MarketStructureEvent, OrderBlock, SwingPoint

__all__ = [
    "Instrument",
    "Candle",
    "SwingPoint",
    "MarketStructureEvent",
    "OrderBlock",
    "FairValueGap",
    "SessionRecord",
    "DailyLevels",
    "LiquidityLevel",
    "LiquiditySweep",
    "Alert",
]
