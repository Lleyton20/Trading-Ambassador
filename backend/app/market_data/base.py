"""
MarketDataProvider interface (spec section 26).

WHY THIS FILE EXISTS
--------------------
If the trading engine imported a broker client (e.g. MetaTrader5) directly,
every piece of analysis logic would be welded to one vendor — you couldn't
test the SMC engine without a running MT5 terminal, and you couldn't
switch to a different data source (Deriv's own API, a CSV file, a
different broker) without editing the engine itself.

This abstract base class avoids that: everything above this line (the
session engine, the SMC engine, the API) only ever talks to a
`MarketDataProvider`. It doesn't know or care whether the concrete
implementation is a live MT5 connection, Deriv's WebSocket API, or (as in
this milestone) a deterministic synthetic-data fixture for development.
Swapping providers later is a one-line change in `app/main.py`, not a
rewrite of the analysis engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Return the list of symbols this provider can serve."""

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        Return the most recent `count` candles for symbol/timeframe as a
        DataFrame indexed by a tz-aware UTC DatetimeIndex, with columns
        open/high/low/close/volume.
        """

    @abstractmethod
    def get_historical_data(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Return candles for symbol/timeframe between start and end (inclusive)."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Return the most recent traded price for symbol."""
