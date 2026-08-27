"""
SQLAlchemy models, split by concern rather than one giant file (spec
section 27: "Do not put everything into one table" / one file).

This milestone defines the tables the current analysis pipeline actually
writes to: instruments, candles, swing_points, market_structure_events,
sessions, daily_levels. Order blocks, fair value gaps, liquidity levels,
news, trade setups, backtests and journal entries are deliberately NOT
modeled yet — they belong to later milestones, and an empty table with a
guessed-at schema is worse than no table (it invites drift between the
schema and the code that will eventually fill it).
"""
from app.models.candle import Candle
from app.models.instrument import Instrument
from app.models.session import DailyLevels, SessionRecord
from app.models.smc import MarketStructureEvent, SwingPoint

__all__ = [
    "Instrument",
    "Candle",
    "SwingPoint",
    "MarketStructureEvent",
    "SessionRecord",
    "DailyLevels",
]
