"""
Order Block detection (spec section 13).

WHY THIS ISN'T "THE LAST OPPOSITE CANDLE"
--------------------------------------------
The spec calls this out directly: "Do not label every opposite candle as
an order block... an order block should ideally be associated with
evidence such as displacement, BOS, CHoCH, liquidity sweep, or a
significant reaction."

So an order block here is only created FROM a confirmed structure event
(`StructureEvent` — a BOS or CHoCH from `app.smc.structure`), and only
when the candle that confirmed that event was itself a displacement
candle (see `app.smc.displacement`). If a break of structure happens on
an ordinary, unremarkable candle, no order block is created for it — there
isn't the evidence the spec asks for.

Given a qualifying structure event, the order block ZONE is the last
candle of the OPPOSITE color before the event's confirming candle within
`lookback_candles` — the classic "last down-candle before an up-move"
(and mirrored for bearish) definition.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.smc.displacement import is_displacement_candle
from app.smc.indicators import calculate_atr
from app.smc.structure import StructureEvent


@dataclass
class OrderBlock:
    direction: str                # "bullish" or "bearish"
    zone_low: float
    zone_high: float
    created_at: pd.Timestamp
    structure_event_type: str     # "BOS" or "CHOCH" — what evidence created it
    mitigated: bool = False
    mitigated_at: pd.Timestamp | None = None
    retest_count: int = 0

    @property
    def midpoint(self) -> float:
        return (self.zone_high + self.zone_low) / 2

    def is_price_in_zone(self, price: float) -> bool:
        return self.zone_low <= price <= self.zone_high


def detect_order_blocks(
    df: pd.DataFrame,
    events: list[StructureEvent],
    *,
    lookback_candles: int = 10,
    require_displacement: bool = True,
    min_displacement_atr_multiple: float = 1.5,
    atr_period: int = 14,
) -> list[OrderBlock]:
    atr = calculate_atr(df, atr_period)
    order_blocks: list[OrderBlock] = []

    for event in events:
        try:
            event_pos = df.index.get_loc(event.timestamp)
        except KeyError:
            continue

        if require_displacement and not is_displacement_candle(
            df, event_pos, atr, min_atr_multiple=min_displacement_atr_multiple
        ):
            continue  # no evidence -> no order block, per spec section 13

        window_start = max(0, event_pos - lookback_candles)
        ob_candle_pos = None
        for pos in range(event_pos - 1, window_start - 1, -1):
            is_bearish_candle = df["close"].iloc[pos] < df["open"].iloc[pos]
            is_bullish_candle = df["close"].iloc[pos] > df["open"].iloc[pos]
            if event.direction == "bullish" and is_bearish_candle:
                ob_candle_pos = pos
                break
            if event.direction == "bearish" and is_bullish_candle:
                ob_candle_pos = pos
                break

        if ob_candle_pos is None:
            continue  # no qualifying opposite candle within the lookback window

        order_blocks.append(
            OrderBlock(
                direction=event.direction,
                zone_low=float(df["low"].iloc[ob_candle_pos]),
                zone_high=float(df["high"].iloc[ob_candle_pos]),
                created_at=df.index[ob_candle_pos],
                structure_event_type=event.event_type,
            )
        )

    return order_blocks


def apply_mitigation(df: pd.DataFrame, order_blocks: list[OrderBlock]) -> None:
    """
    Mutates each order block's mitigation state in place: the first candle
    (after creation) that trades back into the zone marks it mitigated;
    every such touch afterward increments `retest_count`.
    """
    for ob in order_blocks:
        after = df[df.index > ob.created_at]
        touches = 0
        for ts, row in after.iterrows():
            touched = row["low"] <= ob.zone_high and row["high"] >= ob.zone_low
            if touched:
                touches += 1
                if not ob.mitigated:
                    ob.mitigated = True
                    ob.mitigated_at = ts
        ob.retest_count = touches


def get_active_order_blocks(order_blocks: list[OrderBlock]) -> list[OrderBlock]:
    return [ob for ob in order_blocks if not ob.mitigated]
