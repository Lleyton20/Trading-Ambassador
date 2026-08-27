from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Candle(Base):
    """
    Normalized OHLCV candle, matching the schema the spec lays out in
    section 26: timestamp, symbol, timeframe, OHLCV, source.

    `source` records which MarketDataProvider produced this candle (e.g.
    "mock_dev_fixture", "mt5", "deriv_api"). Keeping that on every row
    means the rest of the app never has to depend on a single vendor.
    """

    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)  # M1, M5, M15, M30, H1, H4, D1, W1
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(64))
