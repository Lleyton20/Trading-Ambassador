"""
Price-in-zone watcher: polls every instrument, checks the latest price
against unmitigated order blocks / FVGs (the "zones of high interest"),
and fires an alert - persisted to the DB and sent to Telegram - the first
time price enters a zone it wasn't already sitting in.

WHY A STATEFUL WATCHER INSTANCE
----------------------------------
Order blocks/FVGs are recomputed fresh from candles on every poll (same
as everywhere else in this app - nothing is read back from the DB as the
source of truth, see app/persistence.py's docstring). Without tracking
which zones were already "active" on the previous poll, a price sitting
inside a zone for an hour would re-alert on every single poll instead of
once per fresh entry. `ZoneAlertWatcher` holds that state; it resets a
zone to "not yet alerted" as soon as a poll shows price has left it, so a
later re-entry fires again.

Each order block / FVG's natural key - (symbol, timeframe, zone_type,
created_at, direction) - is exactly the same identity
app/persistence.py's upsert functions already use, reused here as the
in-memory dedup key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import persistence
from app.alerts.telegram_notifier import send_telegram_message
from app.config import settings
from app.instruments import INSTRUMENT_PROFILES
from app.market_data.base import MarketDataProvider
from app.market_data.validation import validate_candles
from app.models.alert import Alert
from app.smc.fvg import apply_mitigation as apply_fvg_mitigation
from app.smc.fvg import detect_fair_value_gaps
from app.smc.order_blocks import apply_mitigation as apply_ob_mitigation
from app.smc.order_blocks import detect_order_blocks
from app.smc.structure import detect_structure_events

logger = logging.getLogger(__name__)


class ZoneAlertWatcher:
    def __init__(self) -> None:
        self._active_zone_ids: set[tuple] = set()

    def check_all_instruments(self, db: Session, provider: MarketDataProvider, timeframe: str) -> list[Alert]:
        persistence.seed_instruments(db)

        fired: list[Alert] = []
        current_ids: set[tuple] = set()
        for symbol in INSTRUMENT_PROFILES:
            try:
                fired.extend(self._check_symbol(db, provider, symbol, timeframe, current_ids))
            except Exception:
                # One bad symbol (a transient data-provider hiccup, say)
                # shouldn't stop every other instrument from being checked.
                logger.exception("Zone-alert check failed for %s", symbol)

        self._active_zone_ids = current_ids
        return fired

    def _check_symbol(
        self, db: Session, provider: MarketDataProvider, symbol: str, timeframe: str, current_ids: set[tuple]
    ) -> list[Alert]:
        df = provider.get_candles(symbol, timeframe, count=500)
        if not validate_candles(df).is_valid:
            return []

        events, _ = detect_structure_events(df, swing_lookback=settings.swing_lookback)

        order_blocks = detect_order_blocks(df, events, min_displacement_atr_multiple=settings.min_displacement_atr_mult)
        apply_ob_mitigation(df, order_blocks)

        gaps = detect_fair_value_gaps(df)
        apply_fvg_mitigation(df, gaps)

        current_price = float(df["close"].iloc[-1])
        fired: list[Alert] = []

        for ob in order_blocks:
            if ob.mitigated or not (ob.zone_low <= current_price <= ob.zone_high):
                continue
            zone_id = ("order_block", symbol, timeframe, ob.created_at, ob.direction)
            current_ids.add(zone_id)
            if zone_id not in self._active_zone_ids:
                fired.append(
                    self._fire(db, symbol, timeframe, "order_block", ob.direction, ob.zone_low, ob.zone_high, current_price)
                )

        for g in gaps:
            if g.mitigated_pct >= 100.0 or not (g.lower <= current_price <= g.upper):
                continue
            zone_id = ("fair_value_gap", symbol, timeframe, g.created_at, g.direction)
            current_ids.add(zone_id)
            if zone_id not in self._active_zone_ids:
                fired.append(
                    self._fire(db, symbol, timeframe, "fair_value_gap", g.direction, g.lower, g.upper, current_price)
                )

        return fired

    def _fire(
        self, db: Session, symbol: str, timeframe: str, zone_type: str,
        direction: str, zone_low: float, zone_high: float, price: float,
    ) -> Alert:
        message = (
            f"{symbol} {timeframe}: price {price:g} entered a {direction} "
            f"{zone_type.replace('_', ' ')} zone ({zone_low:g} - {zone_high:g})"
        )
        sent = send_telegram_message(settings.telegram_bot_token, settings.telegram_chat_id, message)
        alert = Alert(
            symbol=symbol, timeframe=timeframe, zone_type=zone_type, direction=direction,
            zone_low=zone_low, zone_high=zone_high, price_at_trigger=price,
            triggered_at=datetime.now(timezone.utc), message=message, telegram_sent=sent,
        )
        db.add(alert)
        db.commit()
        return alert


_default_watcher = ZoneAlertWatcher()


def check_all_instruments(db: Session, provider: MarketDataProvider, timeframe: str | None = None) -> list[Alert]:
    """Module-level entry point used by the background loop in app/main.py - keeps
    state across polls via `_default_watcher`. Tests should construct their
    own `ZoneAlertWatcher()` instead, for isolation."""
    return _default_watcher.check_all_instruments(db, provider, timeframe or settings.alerts_timeframe)
