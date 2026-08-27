"""
Pydantic response/request models for the API layer.

Kept separate from the SQLAlchemy models in `app/models/` on purpose: an
API schema and a DB table are different concerns that happen to look
similar (spec's broader principle of not mixing layers). A DB model
changing its storage details shouldn't force the API's JSON shape to
change, and vice versa.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class MarketSummary(BaseModel):
    symbol: str
    display_name: str
    asset_class: str
    current_price: float


class CandleOut(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class SwingPointOut(BaseModel):
    timestamp: datetime
    price: float
    kind: str
    label: str


class StructureEventOut(BaseModel):
    timestamp: datetime
    event_type: str
    direction: str
    price: float
    broken_level: float


class SmcAnalysisOut(BaseModel):
    symbol: str
    timeframe: str
    bias: str
    swing_points: list[SwingPointOut]
    structure_events: list[StructureEventOut]


class DailyLevelsOut(BaseModel):
    symbol: str
    trading_day: str
    opening_price: float
    opening_day_high: float
    opening_day_low: float
    previous_day_high: float | None
    previous_day_low: float | None
    current_price: float
    price_status: str  # "above" | "below" | "between" | "testing_high" | "testing_low"


class SessionRangeOut(BaseModel):
    session_name: str
    session_date: str
    session_open: float
    session_high: float
    session_low: float
    session_close: float
    start_time: datetime
    end_time: datetime


class MarketOverviewOut(BaseModel):
    symbol: str
    current_price: float
    bias: str
    daily_levels: DailyLevelsOut | None
    sessions: list[SessionRangeOut]


class RiskRewardRequest(BaseModel):
    entry: float
    stop_loss: float
    take_profit: float
    min_acceptable_rr: float | None = None


class RiskRewardOut(BaseModel):
    risk: float
    reward: float
    risk_reward_ratio: float
    meets_minimum: bool
    quality_label: str


class PositionSizeRequest(BaseModel):
    symbol: str
    account_balance: float
    risk_pct: float
    entry_price: float
    stop_loss_price: float


class PositionSizeOut(BaseModel):
    risk_amount: float
    stop_distance: float
    raw_position_size: float
    position_size: float
