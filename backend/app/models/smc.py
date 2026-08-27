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


class OrderBlock(Base):
    """An evidence-linked order block zone (spec section 13)."""

    __tablename__ = "order_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    direction: Mapped[str] = mapped_column(String(8))               # "bullish" or "bearish"
    zone_low: Mapped[float] = mapped_column(Float)
    zone_high: Mapped[float] = mapped_column(Float)
    structure_event_type: Mapped[str] = mapped_column(String(8))    # "BOS" or "CHOCH" that created it
    mitigated: Mapped[bool] = mapped_column(default=False)
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retest_count: Mapped[int] = mapped_column(default=0)


class FairValueGap(Base):
    """A three-candle Fair Value Gap (spec section 14)."""

    __tablename__ = "fair_value_gaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    direction: Mapped[str] = mapped_column(String(8))       # "bullish" or "bearish"
    upper: Mapped[float] = mapped_column(Float)
    lower: Mapped[float] = mapped_column(Float)
    mitigated_pct: Mapped[float] = mapped_column(Float, default=0.0)
