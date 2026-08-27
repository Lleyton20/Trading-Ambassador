from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionRecord(Base):
    """
    One Asian/London/New York session's OHLC range for one trading day
    (spec section 4). Storing these historically is what later lets us
    backtest "does London sweeping the Asian high predict anything?".
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    session_name: Mapped[str] = mapped_column(String(16))   # "asian", "london", "new_york"
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    session_open: Mapped[float] = mapped_column(Float)
    session_high: Mapped[float] = mapped_column(Float)
    session_low: Mapped[float] = mapped_column(Float)
    session_close: Mapped[float] = mapped_column(Float)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DailyLevels(Base):
    """
    Opening Day High/Low for one trading day (spec section 3). Stored
    historically so ODH/ODL can later be backtested rather than only
    ever being visible "live".
    """

    __tablename__ = "daily_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    opening_price: Mapped[float] = mapped_column(Float)
    opening_day_high: Mapped[float] = mapped_column(Float)
    opening_day_low: Mapped[float] = mapped_column(Float)
    previous_day_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_day_low: Mapped[float | None] = mapped_column(Float, nullable=True)
