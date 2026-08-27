"""
Instrument profiles.

WHY THIS FILE EXISTS
--------------------
The master spec (section 25) is explicit: don't let Forex assumptions leak
into synthetic-index logic (Boom/Crash/Volatility indices don't have real
trading "sessions", don't have pips in the traditional sense, and trade
24/7). It would be tempting to hard-code something like "1 lot = 1 unit"
directly inside the risk engine with a comment telling the user to "adjust
based on your broker" — but that bakes a per-instrument assumption into
code instead of making it configurable.

Instead, every symbol the platform knows about is described by an explicit
`InstrumentProfile`. Any module that needs to know "how big is a pip here"
or "does this instrument observe Forex sessions" asks the profile instead
of assuming.
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
    "CRASH500": InstrumentProfile(
        symbol="CRASH500",
        display_name="Crash 500 Index",
        asset_class=AssetClass.SYNTHETIC_INDEX,
        pip_size=1.0,
        tick_size=0.01,
        contract_size=1,
        min_lot=0.2,
        max_lot=20.0,
        observes_sessions=False,
        volatility_characteristics="high, sharp downward spikes",
    ),
    "CRASH1000": InstrumentProfile(
        symbol="CRASH1000",
        display_name="Crash 1000 Index",
        asset_class=AssetClass.SYNTHETIC_INDEX,
        pip_size=1.0,
        tick_size=0.01,
        contract_size=1,
        min_lot=0.2,
        max_lot=20.0,
        observes_sessions=False,
        volatility_characteristics="high, less frequent downward spikes than Crash 500",
    ),
    "BOOM500": InstrumentProfile(
        symbol="BOOM500",
        display_name="Boom 500 Index",
        asset_class=AssetClass.SYNTHETIC_INDEX,
        pip_size=1.0,
        tick_size=0.01,
        contract_size=1,
        min_lot=0.2,
        max_lot=20.0,
        observes_sessions=False,
        volatility_characteristics="high, sharp upward spikes",
    ),
    "BOOM1000": InstrumentProfile(
        symbol="BOOM1000",
        display_name="Boom 1000 Index",
        asset_class=AssetClass.SYNTHETIC_INDEX,
        pip_size=1.0,
        tick_size=0.01,
        contract_size=1,
        min_lot=0.2,
        max_lot=20.0,
        observes_sessions=False,
        volatility_characteristics="high, less frequent upward spikes than Boom 500",
    ),
    "V75": InstrumentProfile(
        symbol="V75",
        display_name="Volatility 75 Index",
        asset_class=AssetClass.SYNTHETIC_INDEX,
        pip_size=1.0,
        tick_size=0.01,
        contract_size=1,
        min_lot=0.1,
        max_lot=20.0,
        observes_sessions=False,
        volatility_characteristics="high, continuous",
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
