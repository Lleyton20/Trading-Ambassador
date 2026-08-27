from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LiquidityLevel(Base):
    """
    A level where liquidity is assumed to rest: a swing high/low, a
    session high/low, a previous-day high/low, or an equal-highs/lows
    cluster (spec sections 5, 6, 11, 12).
    """

    __tablename__ = "liquidity_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    label: Mapped[str] = mapped_column(String(32))     # "swing_high", "equal_highs", "previous_day_high", ...
    kind: Mapped[str] = mapped_column(String(4))        # "high" or "low"
    price: Mapped[float] = mapped_column(Float)
    formed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LiquiditySweep(Base):
    """A confirmed sweep-and-reverse of a liquidity level (spec section 11)."""

    __tablename__ = "liquidity_sweeps"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidity_level_id: Mapped[int] = mapped_column(ForeignKey("liquidity_levels.id"), index=True)
    swept_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sweep_extreme: Mapped[float] = mapped_column(Float)
