"""
Tests for app/news/engine.py. `fetch_economic_calendar` is monkeypatched
so nothing here touches the real Finnhub API - same approach as
tests/test_deriv_provider.py.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.news import engine
from app.news.finnhub_client import EconomicEvent, FinnhubUnavailableError


def _event(event: str, country: str, impact: str, day: date, hour: int = 12) -> EconomicEvent:
    return EconomicEvent(
        event=event, country=country, impact=impact,
        time=datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc),
    )


def test_affected_symbols_maps_forex_countries():
    assert engine.affected_symbols("US") == ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    assert engine.affected_symbols("eu") == ["EURUSD"]  # case-insensitive
    assert engine.affected_symbols("GB") == ["GBPUSD"]
    assert engine.affected_symbols("JP") == ["USDJPY"]


def test_affected_symbols_unmapped_country_returns_empty():
    assert engine.affected_symbols("ZZ") == []


def test_todays_events_sorted_high_to_low_impact(monkeypatch):
    today = date(2026, 8, 30)
    events = [
        _event("CPI", "US", "low", today, hour=9),
        _event("NFP", "US", "high", today, hour=14),
        _event("Retail Sales", "GB", "medium", today, hour=10),
    ]
    monkeypatch.setattr(engine, "fetch_economic_calendar", lambda *a, **kw: events)

    calendar = engine.get_news_calendar("fake-key", lookahead_days=7, today=today)

    assert calendar.available is True
    assert [e.event for e in calendar.today] == ["NFP", "Retail Sales", "CPI"]


def test_upcoming_high_impact_excludes_today_and_low_medium_impact(monkeypatch):
    today = date(2026, 8, 30)
    events = [
        _event("NFP today", "US", "high", today),
        _event("Rate decision", "GB", "high", date(2026, 9, 2)),
        _event("Minor release", "US", "low", date(2026, 9, 1)),
    ]
    monkeypatch.setattr(engine, "fetch_economic_calendar", lambda *a, **kw: events)

    calendar = engine.get_news_calendar("fake-key", lookahead_days=7, today=today)

    assert [e.event for e in calendar.upcoming_high_impact] == ["Rate decision"]


def test_unavailable_provider_degrades_gracefully(monkeypatch):
    def _raise(*args, **kwargs):
        raise FinnhubUnavailableError("no access on this plan")

    monkeypatch.setattr(engine, "fetch_economic_calendar", _raise)

    calendar = engine.get_news_calendar("fake-key", lookahead_days=7, today=date(2026, 8, 30))

    assert calendar.available is False
    assert calendar.today == []
    assert calendar.upcoming_high_impact == []


def test_missing_api_key_is_unavailable_not_a_crash():
    calendar = engine.get_news_calendar("", lookahead_days=7, today=date(2026, 8, 30))
    assert calendar.available is False
