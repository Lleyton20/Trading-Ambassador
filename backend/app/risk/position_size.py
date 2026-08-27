"""
Position size calculator (spec section 19).

WHY THIS TAKES AN InstrumentProfile
------------------------------------
A naive position-size formula (`risk_amount / price_risk`) silently
assumes "1 lot = 1 unit of price movement" — true for some instruments,
wrong for others. That's exactly the kind of hidden, per-instrument
assumption the spec warns against (section 19: "this must be implemented
carefully and instrument specifications must be configurable").

Here, position size is computed from the instrument's actual
`contract_size` and `tick_size`/`pip_size`, taken from the explicit
`InstrumentProfile` registry (app/instruments.py) — never guessed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.instruments import InstrumentProfile


@dataclass
class PositionSizeResult:
    risk_amount: float
    stop_distance: float
    raw_position_size: float
    position_size: float  # clamped to the instrument's min/max lot and rounded


def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
    instrument: InstrumentProfile,
) -> PositionSizeResult:
    if risk_pct <= 0 or risk_pct > 100:
        raise ValueError("risk_pct must be between 0 and 100")

    stop_distance = abs(entry_price - stop_loss_price)
    if stop_distance == 0:
        raise ValueError("Stop loss cannot equal entry price.")

    risk_amount = account_balance * (risk_pct / 100.0)

    # Value of one full unit of price movement for one contract:
    value_per_price_unit = instrument.contract_size
    raw_position_size = risk_amount / (stop_distance * value_per_price_unit)

    clamped = max(instrument.min_lot, min(instrument.max_lot, raw_position_size))
    # Round down to the nearest lot step implied by min_lot (e.g. 0.01 or 0.2).
    # A small epsilon guards against floating-point results like 39.999999
    # for what should be exactly 40 steps (0.4 / 0.01).
    step = instrument.min_lot
    rounded = math.floor(clamped / step + 1e-9) * step

    return PositionSizeResult(
        risk_amount=risk_amount,
        stop_distance=stop_distance,
        raw_position_size=raw_position_size,
        position_size=round(rounded, 4),
    )
