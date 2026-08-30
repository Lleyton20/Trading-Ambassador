"""
Thin client for Finnhub's economic calendar endpoint.

RESPONSE SHAPE
---------------
Verified against Finnhub's own official Go client source (finnhub-go's
model_economic_calendar.go / model_economic_event.go), not guessed:

    {"economicCalendar": [
        {"event": str, "country": str, "impact": "low"|"medium"|"high",
         "actual": float|None, "estimate": float|None, "prev": float|None,
         "unit": str|None, "time": str},
        ...
    ]}

`time` is documented by Finnhub as UTC; treated as such here.

KNOWN RISK
-----------
Finnhub has historically gated `/calendar/economic` behind a paid plan for
some accounts, so a free-tier key isn't guaranteed access. This client
raises `FinnhubUnavailableError` on any request failure (missing key,
403, network error) rather than letting an exception from a third-party
outage take down the news endpoint - see app/news/engine.py, which turns
that into a graceful "unavailable" response instead of a 500.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

_BASE_URL = "https://finnhub.io/api/v1/calendar/economic"


class FinnhubUnavailableError(Exception):
    """Raised when the economic calendar can't be fetched (no key, 403, network error, ...)."""


@dataclass
class EconomicEvent:
    event: str
    country: str
    impact: str  # "low" | "medium" | "high"
    time: datetime
    actual: float | None = None
    estimate: float | None = None
    prev: float | None = None
    unit: str | None = None


def fetch_economic_calendar(
    api_key: str, *, start: date, end: date, timeout: float = 10.0
) -> list[EconomicEvent]:
    if not api_key:
        raise FinnhubUnavailableError("FINNHUB_API_KEY is not configured")

    try:
        response = httpx.get(
            _BASE_URL,
            params={"from": start.isoformat(), "to": end.isoformat(), "token": api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise FinnhubUnavailableError(f"Finnhub request failed: {exc}") from exc

    raw_events = payload.get("economicCalendar") or []
    events: list[EconomicEvent] = []
    for raw in raw_events:
        impact = (raw.get("impact") or "low").lower()
        try:
            event_time = datetime.strptime(raw["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue  # a malformed row shouldn't take down the whole calendar
        events.append(
            EconomicEvent(
                event=raw.get("event", "Unknown event"),
                country=raw.get("country", ""),
                impact=impact,
                time=event_time,
                actual=raw.get("actual"),
                estimate=raw.get("estimate"),
                prev=raw.get("prev"),
                unit=raw.get("unit"),
            )
        )
    return events
