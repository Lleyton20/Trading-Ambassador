from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SwingPoint(Base):
    """A confirmed swing high or swing low (spec section 7)."""

    __tablename__ = "swing_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(4))          # "high" or "low"
    label: Mapped[str] = mapped_column(String(4))          # "HH", "HL", "LH", "LL"


class MarketStructureEvent(Base):
    """A Break of Structure or Change of Character event (spec sections 9-10)."""

    __tablename__ = "market_structure_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(8))     # "BOS" or "CHOCH"
    direction: Mapped[str] = mapped_column(String(8))       # "bullish" or "bearish"
    price: Mapped[float] = mapped_column(Float)             # candle close that confirmed the break
    broken_level: Mapped[float] = mapped_column(Float)       # the swing level that was broken
