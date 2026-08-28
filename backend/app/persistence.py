"""
Persists computed SMC results to the DB tables reserved for them
(spec Milestone 3 / README "Known gaps").

WHY UPSERT-BY-NATURAL-KEY INSTEAD OF ON CONFLICT
--------------------------------------------------
This app targets both SQLite (dev) and Postgres (production) through the
same SQLAlchemy models, and `ON CONFLICT` syntax isn't portable between
the two dialects. Every function here instead does the plain, explicit
thing: look up the row by its natural key, insert if it isn't there,
update the mutable status fields if it is. Slightly more code, works
identically on both databases.

WHAT'S IMMUTABLE VS MUTABLE
-----------------------------
A swing point, a BOS/CHoCH event, and a liquidity sweep are historical
facts — once recorded they don't change, so those are insert-if-absent
only. An order block's or FVG's mitigation status, by contrast, evolves as
new candles arrive, so those rows are updated in place when the natural
key already exists.

This module is called as a side effect from the API routes (see
app/api/routes.py) — every response is still computed fresh from live
candles on every request; persistence here is an audit trail, not a
cache the routes read back from.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.instruments import INSTRUMENT_PROFILES
from app.models.instrument import Instrument
from app.models.liquidity import LiquidityLevel as LiquidityLevelRow
from app.models.liquidity import LiquiditySweep as LiquiditySweepRow
from app.models.smc import FairValueGap as FairValueGapRow
from app.models.smc import MarketStructureEvent as MarketStructureEventRow
from app.models.smc import OrderBlock as OrderBlockRow
from app.models.smc import SwingPoint as SwingPointRow
from app.smc.fvg import FairValueGap
from app.smc.liquidity import LiquidityLevel, LiquiditySweepEvent
from app.smc.order_blocks import OrderBlock
from app.smc.structure import StructureEvent


def seed_instruments(db: Session) -> None:
    """Upserts every known InstrumentProfile into the `instruments` table.

    Needed once, up front: candles/swing_points/etc. all foreign-key onto
    `instruments.symbol`, and nothing else populates that table.
    """
    existing = set(db.scalars(select(Instrument.symbol)).all())
    for symbol, profile in INSTRUMENT_PROFILES.items():
        if symbol in existing:
            continue
        db.add(Instrument(symbol=symbol, display_name=profile.display_name, asset_class=profile.asset_class.value))
    db.commit()


def persist_swing_points(db: Session, symbol: str, timeframe: str, swings: list[dict]) -> None:
    for s in swings:
        exists = db.scalar(
            select(SwingPointRow.id).where(
                SwingPointRow.symbol == symbol,
                SwingPointRow.timeframe == timeframe,
                SwingPointRow.timestamp == s["timestamp"],
                SwingPointRow.kind == s["kind"],
            )
        )
        if exists is not None:
            continue
        db.add(
            SwingPointRow(
                symbol=symbol, timeframe=timeframe, timestamp=s["timestamp"],
                price=s["price"], kind=s["kind"], label=s["label"],
            )
        )
    db.commit()


def persist_structure_events(db: Session, symbol: str, timeframe: str, events: list[StructureEvent]) -> None:
    for e in events:
        exists = db.scalar(
            select(MarketStructureEventRow.id).where(
                MarketStructureEventRow.symbol == symbol,
                MarketStructureEventRow.timeframe == timeframe,
                MarketStructureEventRow.timestamp == e.timestamp,
                MarketStructureEventRow.event_type == e.event_type,
            )
        )
        if exists is not None:
            continue
        db.add(
            MarketStructureEventRow(
                symbol=symbol, timeframe=timeframe, timestamp=e.timestamp,
                event_type=e.event_type, direction=e.direction,
                price=e.price, broken_level=e.broken_level,
            )
        )
    db.commit()


def persist_order_blocks(db: Session, symbol: str, timeframe: str, order_blocks: list[OrderBlock]) -> None:
    for ob in order_blocks:
        row = db.scalar(
            select(OrderBlockRow).where(
                OrderBlockRow.symbol == symbol,
                OrderBlockRow.timeframe == timeframe,
                OrderBlockRow.created_at == ob.created_at,
                OrderBlockRow.direction == ob.direction,
            )
        )
        if row is None:
            db.add(
                OrderBlockRow(
                    symbol=symbol, timeframe=timeframe, created_at=ob.created_at,
                    direction=ob.direction, zone_low=ob.zone_low, zone_high=ob.zone_high,
                    structure_event_type=ob.structure_event_type,
                    mitigated=ob.mitigated, mitigated_at=ob.mitigated_at, retest_count=ob.retest_count,
                )
            )
        else:
            row.mitigated = ob.mitigated
            row.mitigated_at = ob.mitigated_at
            row.retest_count = ob.retest_count
    db.commit()


def persist_fair_value_gaps(db: Session, symbol: str, timeframe: str, gaps: list[FairValueGap]) -> None:
    for g in gaps:
        row = db.scalar(
            select(FairValueGapRow).where(
                FairValueGapRow.symbol == symbol,
                FairValueGapRow.timeframe == timeframe,
                FairValueGapRow.created_at == g.created_at,
                FairValueGapRow.direction == g.direction,
            )
        )
        if row is None:
            db.add(
                FairValueGapRow(
                    symbol=symbol, timeframe=timeframe, created_at=g.created_at,
                    direction=g.direction, upper=g.upper, lower=g.lower,
                    mitigated_pct=g.mitigated_pct,
                )
            )
        else:
            row.mitigated_pct = g.mitigated_pct
    db.commit()


def persist_liquidity_levels(
    db: Session, symbol: str, timeframe: str, levels: list[LiquidityLevel]
) -> dict[tuple[str, str, object], int]:
    """
    Upserts liquidity levels and returns a (label, kind, formed_at) -> row id
    mapping, so `persist_liquidity_sweeps` can attach sweeps to the right
    persisted row via its foreign key.
    """
    level_ids: dict[tuple[str, str, object], int] = {}
    for lvl in levels:
        row = db.scalar(
            select(LiquidityLevelRow).where(
                LiquidityLevelRow.symbol == symbol,
                LiquidityLevelRow.timeframe == timeframe,
                LiquidityLevelRow.label == lvl.label,
                LiquidityLevelRow.formed_at == lvl.formed_at,
            )
        )
        if row is None:
            row = LiquidityLevelRow(
                symbol=symbol, timeframe=timeframe, label=lvl.label,
                kind=lvl.kind, price=lvl.price, formed_at=lvl.formed_at,
            )
            db.add(row)
            db.flush()  # need row.id before commit, without a second round trip
        level_ids[(lvl.label, lvl.kind, lvl.formed_at)] = row.id
    db.commit()
    return level_ids


def persist_liquidity_sweeps(
    db: Session,
    level_ids: dict[tuple[str, str, object], int],
    sweeps: list[tuple[LiquidityLevel, LiquiditySweepEvent | None]],
) -> None:
    for level, sweep in sweeps:
        if sweep is None:
            continue
        level_id = level_ids.get((level.label, level.kind, level.formed_at))
        if level_id is None:
            continue
        exists = db.scalar(
            select(LiquiditySweepRow.id).where(
                LiquiditySweepRow.liquidity_level_id == level_id,
                LiquiditySweepRow.swept_at == sweep.swept_at,
            )
        )
        if exists is not None:
            continue
        db.add(
            LiquiditySweepRow(
                liquidity_level_id=level_id, swept_at=sweep.swept_at, sweep_extreme=sweep.sweep_extreme,
            )
        )
    db.commit()
