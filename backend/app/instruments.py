"""
Instrument profiles.

WHY THIS FILE EXISTS
--------------------
It would be tempting to hard-code something like "1 lot = 1 unit" directly
inside the risk engine with a comment telling the user to "adjust based on
your broker" — but that bakes a per-instrument assumption into code
instead of making it configurable.

Instead, every symbol the platform knows about is described by an explicit
`InstrumentProfile`. Any module that needs to know "how big is a pip here"
or "does this instrument observe Forex sessions" asks the profile instead
of assuming.

SCOPE: Forex majors only for now. `AssetClass.SYNTHETIC_INDEX` and the
`observes_sessions` field are kept (rather than deleted) because they're
what previously supported Deriv's synthetic indices (Volatility/Boom/Crash)
before the project's scope narrowed to Forex — re-adding an instrument
under that asset class later is a one-entry addition here, not a redesign.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AssetClass(str, Enum):
    FOREX = "forex"
    SYNTHETIC_INDEX = "synthetic_index"


class InstrumentProfile(BaseModel):
    symbol: str
    display_name: str
    asset_class: AssetClass
    pip_size: float          # price movement that counts as "1 pip" for this instrument
    tick_size: float         # smallest price increment the broker quotes
    contract_size: float     # units per 1.0 lot
    min_lot: float
    max_lot: float
    # Forex instruments observe Asian/London/NY sessions; synthetic indices
    # trade continuously and session analysis does not meaningfully apply.
    observes_sessions: bool
    volatility_characteristics: str


# A small, explicit registry rather than a "guess from symbol name" helper.
# Extend this as new instruments are added — nothing elsewhere in the code
# should special-case a symbol string.
INSTRUMENT_PROFILES: dict[str, InstrumentProfile] = {
    "EURUSD": InstrumentProfile(
        symbol="EURUSD",
        display_name="EUR/USD",
        asset_class=AssetClass.FOREX,
        pip_size=0.0001,
        tick_size=0.00001,
        contract_size=100_000,
        min_lot=0.01,
        max_lot=100.0,
        observes_sessions=True,
        volatility_characteristics="low-medium",
    ),
    "GBPUSD": InstrumentProfile(
        symbol="GBPUSD",
        display_name="GBP/USD",
        asset_class=AssetClass.FOREX,
        pip_size=0.0001,
        tick_size=0.00001,
        contract_size=100_000,
        min_lot=0.01,
        max_lot=100.0,
        observes_sessions=True,
        volatility_characteristics="medium",
    ),
    "USDJPY": InstrumentProfile(
        symbol="USDJPY",
        display_name="USD/JPY",
        asset_class=AssetClass.FOREX,
        pip_size=0.01,
        tick_size=0.001,
        contract_size=100_000,
        min_lot=0.01,
        max_lot=100.0,
        observes_sessions=True,
        volatility_characteristics="medium",
    ),
    "XAUUSD": InstrumentProfile(
        symbol="XAUUSD",
        display_name="Gold (XAU/USD)",
        asset_class=AssetClass.FOREX,
        pip_size=0.1,
        tick_size=0.01,
        contract_size=100,
        min_lot=0.01,
        max_lot=50.0,
        observes_sessions=True,
        volatility_characteristics="medium-high",
    ),
}


def get_instrument_profile(symbol: str) -> InstrumentProfile:
    try:
        return INSTRUMENT_PROFILES[symbol.upper()]
    except KeyError as exc:
        raise ValueError(
            f"No InstrumentProfile registered for symbol '{symbol}'. "
            f"Add one to INSTRUMENT_PROFILES in app/instruments.py."
        ) from exc
