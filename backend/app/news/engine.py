"""
Economic calendar engine: today's events sorted high->low impact, and
upcoming high-impact events - the two views the dashboard's news panel
needs.

WHY SYNTHETIC INDICES ARE NEVER MAPPED TO A NEWS EVENT
---------------------------------------------------------
Deriv's Volatility/Boom/Crash indices are synthetic - algorithmically
generated, not derived from real-world market activity - so no real-world
economic release "affects" them the way an NFP print affects EURUSD. Not
mapping them below is a deliberate choice, not an oversight (same
"no hidden assumptions" rule the rest of this app follows).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.news.finnhub_client import EconomicEvent, FinnhubUnavailableError, fetch_economic_calendar

_IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}

# Which of our instruments a release from this country can move - Forex
# majors only, see module docstring for why synthetic indices are absent.
_COUNTRY_TO_SYMBOLS: dict[str, list[str]] = {
    "US": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
    "EU": ["EURUSD"],
    "GB": ["GBPUSD"],
    "JP": ["USDJPY"],
}


@dataclass
class NewsCalendar:
    available: bool
    today: list[EconomicEvent]
    upcoming_high_impact: list[EconomicEvent]


def affected_symbols(country: str) -> list[str]:
    return _COUNTRY_TO_SYMBOLS.get(country.upper(), [])


def get_news_calendar(
    api_key: str, *, lookahead_days: int, today: date | None = None
) -> NewsCalendar:
    """
    Fetches once and splits into "today, high->low impact" and "upcoming
    high-impact only". Never raises: a Finnhub failure comes back as
    `available=False` with empty lists rather than a 500 (see
    finnhub_client's docstring for why that endpoint can fail).
    """
    today = today or datetime.now(timezone.utc).date()
    end = today + timedelta(days=lookahead_days)

    try:
        events = fetch_economic_calendar(api_key, start=today, end=end)
    except FinnhubUnavailableError:
        return NewsCalendar(available=False, today=[], upcoming_high_impact=[])

    todays_events = sorted(
        (e for e in events if e.time.date() == today),
        key=lambda e: (_IMPACT_RANK.get(e.impact, 3), e.time),
    )
    upcoming_high_impact = sorted(
        (e for e in events if e.time.date() > today and e.impact == "high"),
        key=lambda e: e.time,
    )
    return NewsCalendar(available=True, today=todays_events, upcoming_high_impact=upcoming_high_impact)
