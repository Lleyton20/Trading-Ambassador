from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Instrument(Base):
    """
    Persisted record of a tradeable instrument.

    This mirrors (a subset of) `app.instruments.InstrumentProfile`. The
    Python-level profile is the source of truth for trading logic (pip
    size, contract size, etc.); this table exists so candles/events can
    have a proper foreign key instead of a bare string, and so the DB is
    self-describing if queried directly.
    """

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64))
    asset_class: Mapped[str] = mapped_column(String(32))
