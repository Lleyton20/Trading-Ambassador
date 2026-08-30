"""
Tests for app/alerts/watcher.py's zone-entry/exit dedup logic, against an
isolated in-memory DB (never the real dev database) and a fake provider
that always returns the same hand-worked candle set from test_fvg.py -
a bullish FVG at (1.00, 1.02), 75% mitigated, with the last close (1.01)
sitting inside it. Telegram is never actually configured in tests, so
`send_telegram_message` no-ops - see app/alerts/telegram_notifier.py.
"""
from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.alerts.watcher import ZoneAlertWatcher
from app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class _FakeProvider:
    """Always returns the same fixed candle set - see module docstring."""

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        index = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
        return pd.DataFrame(
            {
                "open": [1.00, 1.00, 1.04, 0.99, 1.01],
                "high": [1.00, 1.05, 1.06, 0.99, 1.025],
                "low": [0.99, 0.995, 1.02, 0.95, 1.005],
                "close": [1.00, 1.04, 1.03, 0.96, 1.01],
                "volume": [100.0] * 5,
            },
            index=index,
        )


def test_fires_alert_for_every_instrument_sitting_in_the_zone(db_session):
    watcher = ZoneAlertWatcher()

    fired = watcher.check_all_instruments(db_session, _FakeProvider(), "H1")

    assert len(fired) == 9  # every instrument gets the same fixed df
    first = fired[0]
    assert first.zone_type == "fair_value_gap"
    assert first.direction == "bullish"
    assert first.zone_low == pytest.approx(1.00)
    assert first.zone_high == pytest.approx(1.02)
    assert first.price_at_trigger == pytest.approx(1.01)
    assert first.telegram_sent is False  # not configured in tests


def test_does_not_refire_while_price_stays_in_the_same_zone(db_session):
    watcher = ZoneAlertWatcher()
    watcher.check_all_instruments(db_session, _FakeProvider(), "H1")

    second_pass = watcher.check_all_instruments(db_session, _FakeProvider(), "H1")

    assert second_pass == []


def test_refires_after_price_leaves_and_reenters_the_zone(db_session, monkeypatch):
    watcher = ZoneAlertWatcher()
    watcher.check_all_instruments(db_session, _FakeProvider(), "H1")

    class _EmptyZoneProvider:
        def get_candles(self, symbol, timeframe, count=500):
            index = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
            return pd.DataFrame(
                {"open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1], "close": [1, 1, 1], "volume": [1, 1, 1]},
                index=index,
            )

    away_pass = watcher.check_all_instruments(db_session, _EmptyZoneProvider(), "H1")
    assert away_pass == []  # no FVG at all in this flat data, zone considered "left"

    back_pass = watcher.check_all_instruments(db_session, _FakeProvider(), "H1")
    assert len(back_pass) == 9  # re-entering the same zone fires again
