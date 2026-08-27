"""
Premium / Discount / Equilibrium classification (spec section 15).

The "dealing range" is the price range between the most recent
significant swing high and swing low — the same validated swing points
every other SMC module uses (see swings.py), not a re-derived notion of
"significant". Equilibrium is the midpoint; price above it is trading at
a premium, below it a discount.

IMPORTANT (spec is explicit about this): this module only classifies
where price IS. It never decides that being in discount means "therefore
buy" — that judgment call, and whatever other evidence should accompany
it, belongs to a human or to the confluence-scoring engine planned for a
later milestone.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DealingRange:
    range_high: float
    range_low: float
    equilibrium: float


def determine_active_dealing_range(swings: list[dict]) -> DealingRange | None:
    """
    Uses the most recent confirmed swing high and swing low (from
    `app.smc.swings.label_swing_sequence`) as the active dealing range.
    Returns None if there isn't at least one of each yet.
    """
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    if not highs or not lows:
        return None

    last_high = highs[-1]["price"]
    last_low = lows[-1]["price"]
    range_high = max(last_high, last_low)
    range_low = min(last_high, last_low)
    return DealingRange(range_high=range_high, range_low=range_low, equilibrium=(range_high + range_low) / 2)


def classify_premium_discount(price: float, dealing_range: DealingRange) -> str:
    """Returns "premium", "discount", or "equilibrium" (exact midpoint match)."""
    if price > dealing_range.equilibrium:
        return "premium"
    if price < dealing_range.equilibrium:
        return "discount"
    return "equilibrium"
