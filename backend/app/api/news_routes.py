"""
Economic calendar route. Kept separate from app/api/routes.py, which is
already large - this is its own concern (news, not market analysis).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.news.engine import affected_symbols, get_news_calendar
from app.schemas.news import EconomicEventOut, NewsCalendarOut

router = APIRouter()


def _to_out(event) -> EconomicEventOut:
    return EconomicEventOut(
        event=event.event,
        country=event.country,
        impact=event.impact,
        time=event.time,
        actual=event.actual,
        estimate=event.estimate,
        prev=event.prev,
        unit=event.unit,
        affects_symbols=affected_symbols(event.country),
    )


@router.get("/news/calendar", response_model=NewsCalendarOut)
def get_news_calendar_route():
    """
    Today's economic releases (high->low impact) plus upcoming high-impact
    releases. `available: false` (with empty lists) means Finnhub isn't
    reachable right now - no API key configured, or the calendar endpoint
    isn't included in the current plan - not an error.
    """
    calendar = get_news_calendar(settings.finnhub_api_key, lookahead_days=settings.news_lookahead_days)
    return NewsCalendarOut(
        available=calendar.available,
        today=[_to_out(e) for e in calendar.today],
        upcoming_high_impact=[_to_out(e) for e in calendar.upcoming_high_impact],
    )
