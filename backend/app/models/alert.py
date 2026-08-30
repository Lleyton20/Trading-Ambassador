from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    """A price-in-zone alert: price traded into an unmitigated order block
    or FVG (spec: "zones of high interest"), fired once per fresh entry -
    see app/alerts/watcher.py for the entry/exit dedup logic."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    zone_type: Mapped[str] = mapped_column(String(16))   # "order_block" | "fair_value_gap"
    direction: Mapped[str] = mapped_column(String(8))     # "bullish" | "bearish"
    zone_low: Mapped[float] = mapped_column(Float)
    zone_high: Mapped[float] = mapped_column(Float)
    price_at_trigger: Mapped[float] = mapped_column(Float)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    message: Mapped[str] = mapped_column(String(255))
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
