"""
Deterministic synthetic-data provider for development and testing.

The master spec explicitly warns against "fake market data" EXCEPT when
it's an explicitly-labeled development fixture (section 46). This is that
fixture: it lets the whole pipeline (sessions, SMC, risk, API) run and be
demoed end-to-end without needing real MT5/Deriv credentials, while being
impossible to mistake for a real data source — the class name says so,
`source="mock_dev_fixture"` is stamped on every candle, and it is never
registered as anything but the default *dev* provider in `app/main.py`.

It is deterministic (seeded RNG) so tests get the same candles every run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.market_data.base import MarketDataProvider

_TIMEFRAME_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
}


class MockMarketDataProvider(MarketDataProvider):
    """Generates a deterministic random-walk candle series per symbol."""

    def __init__(self, symbols: list[str], seed: int = 42):
        self._symbols = symbols
        self._seed = seed

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    def _generate(self, symbol: str, timeframe: str, count: int, end: datetime) -> pd.DataFrame:
        if timeframe not in _TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Seed depends on symbol+timeframe so different series don't move
        # in lockstep, but the SAME series is reproduced every call.
        rng = np.random.default_rng(abs(hash((symbol, timeframe, self._seed))) % (2**32))

        minutes = _TIMEFRAME_MINUTES[timeframe]
        timestamps = pd.date_range(
            end=end, periods=count, freq=f"{minutes}min", tz=timezone.utc
        )

        base_price = 1.1000 if "USD" in symbol and "JPY" not in symbol else 100.0
        # Random walk with occasional larger "displacement" candles so
        # swing/BOS/CHOCH detection has something real to find.
        step_size = base_price * 0.0006
        steps = rng.normal(loc=0.0, scale=step_size, size=count)
        # Inject a few displacement bursts.
        burst_idx = rng.choice(count, size=max(1, count // 40), replace=False)
        steps[burst_idx] *= rng.uniform(4, 7, size=len(burst_idx))

        close = base_price + np.cumsum(steps)
        open_ = np.concatenate([[base_price], close[:-1]])
        high = np.maximum(open_, close) + np.abs(rng.normal(0, step_size * 0.5, count))
        low = np.minimum(open_, close) - np.abs(rng.normal(0, step_size * 0.5, count))
        volume = rng.uniform(50, 500, count)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=timestamps,
        )
        df.index.name = "timestamp"
        return df

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        return self._generate(symbol, timeframe, count, end=datetime.now(timezone.utc))

    def get_historical_data(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        minutes = _TIMEFRAME_MINUTES[timeframe]
        count = max(1, int((end - start).total_seconds() // 60 // minutes))
        return self._generate(symbol, timeframe, count, end=end)

    def get_latest_price(self, symbol: str) -> float:
        df = self.get_candles(symbol, "M1", count=1)
        return float(df["close"].iloc[-1])
