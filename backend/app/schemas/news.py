from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EconomicEventOut(BaseModel):
    event: str
    country: str
    impact: str  # "low" | "medium" | "high"
    time: datetime
    actual: float | None
    estimate: float | None
    prev: float | None
    unit: str | None
    affects_symbols: list[str]


class NewsCalendarOut(BaseModel):
    available: bool
    today: list[EconomicEventOut]
    upcoming_high_impact: list[EconomicEventOut]
