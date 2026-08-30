from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    symbol: str
    timeframe: str
    zone_type: str
    direction: str
    zone_low: float
    zone_high: float
    price_at_trigger: float
    triggered_at: datetime
    message: str
    telegram_sent: bool
