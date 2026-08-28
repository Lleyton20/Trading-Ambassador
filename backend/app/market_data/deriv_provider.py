"""
Live market-data provider backed by Deriv's public WebSocket API.

WHY DERIV AND NOT MT5
----------------------
`instruments.py` covers both Forex majors and Deriv's synthetic indices.
Deriv's API serves candle history for both from a single connection, and
its market-data endpoints (active_symbols, ticks_history) need no API
token or login — only a public `app_id`. MetaTrader5's official Python
package is Windows-only, so it isn't a real option here.

WHY SYNCHRONOUS
----------------
Every other MarketDataProvider method (and every FastAPI route in this
app) is synchronous `def`, not `async def`. Using `websockets.sync.client`
keeps this provider consistent with that rather than pulling asyncio into
an otherwise sync codebase for one module.

SYMBOL CODES
-------------
Verified live against `ticks_history` (not guessed, and not from
`active_symbols`, which returns an empty list for this app_id without a
logged-in session). Deriv has renamed some synthetic indices with an "N"
suffix in the past; that suffix currently returns "Symbol invalid" for
these instruments, so the mapping below uses the plain codes.
"""
from __future__ import annotations

import json
import ssl
from datetime import datetime

import certifi
import pandas as pd
from websockets.sync.client import connect

from app.market_data.base import MarketDataProvider

SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "frxEURUSD",
    "GBPUSD": "frxGBPUSD",
    "USDJPY": "frxUSDJPY",
    "XAUUSD": "frxXAUUSD",
    "CRASH500": "CRASH500",
    "CRASH1000": "CRASH1000",
    "BOOM500": "BOOM500",
    "BOOM1000": "BOOM1000",
    "V75": "R_75",
}

# Deriv's supported candle granularities, in seconds (confirmed via the
# API's own validation error). There is no weekly value - W1 is built by
# resampling D1 candles instead (see _resample_weekly below).
_GRANULARITY_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}


class DerivMarketDataProvider(MarketDataProvider):
    """Live candles from Deriv's public WebSocket API (no auth required for market data)."""

    def __init__(self, app_id: str, *, symbol_map: dict[str, str] | None = None, timeout: float = 10.0):
        self._app_id = app_id
        self._symbol_map = dict(symbol_map or SYMBOL_MAP)
        self._timeout = timeout
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def get_symbols(self) -> list[str]:
        return list(self._symbol_map.keys())

    def _deriv_symbol(self, symbol: str) -> str:
        try:
            return self._symbol_map[symbol]
        except KeyError as exc:
            raise ValueError(f"No Deriv symbol mapping for '{symbol}'") from exc

    def _request(self, payload: dict) -> dict:
        """
        Sends one request over a fresh WebSocket connection and returns the
        parsed response. Isolated as its own method (rather than inlined
        into the candle-fetching methods below) so tests can monkeypatch it
        with canned responses instead of touching the network.
        """
        url = f"wss://ws.derivws.com/websockets/v3?app_id={self._app_id}"
        with connect(url, open_timeout=self._timeout, ssl_context=self._ssl_context) as ws:
            ws.send(json.dumps(payload))
            response = json.loads(ws.recv(timeout=self._timeout))
        if "error" in response:
            raise ValueError(f"Deriv API error: {response['error'].get('message', response['error'])}")
        return response

    def _fetch_candles(
        self, symbol: str, timeframe: str, *,
        count: int | None = None, start: datetime | None = None, end: datetime | None = None,
    ) -> pd.DataFrame:
        base_timeframe = "D1" if timeframe == "W1" else timeframe
        if base_timeframe not in _GRANULARITY_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        payload: dict = {
            "ticks_history": self._deriv_symbol(symbol),
            "style": "candles",
            "granularity": _GRANULARITY_SECONDS[base_timeframe],
        }
        if start is not None and end is not None:
            payload["start"] = int(start.timestamp())
            payload["end"] = int(end.timestamp())
        else:
            payload["count"] = count or 500
            payload["end"] = "latest"

        response = self._request(payload)
        df = _candles_to_frame(response.get("candles", []))
        return _resample_weekly(df) if timeframe == "W1" else df

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        return self._fetch_candles(symbol, timeframe, count=count)

    def get_historical_data(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self._fetch_candles(symbol, timeframe, start=start, end=end)

    def get_latest_price(self, symbol: str) -> float:
        df = self._fetch_candles(symbol, "M1", count=1)
        return float(df["close"].iloc[-1])


def _candles_to_frame(candles: list[dict]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    timestamps = pd.to_datetime([c["epoch"] for c in candles], unit="s", utc=True)
    df = pd.DataFrame(
        {
            "open": [float(c["open"]) for c in candles],
            "high": [float(c["high"]) for c in candles],
            "low": [float(c["low"]) for c in candles],
            "close": [float(c["close"]) for c in candles],
            # Deriv's synthetic-index/forex-CFD candles carry no real trade
            # volume; keep the column (validate_candles doesn't require it)
            # so callers never have to special-case a provider that's
            # missing a column the interface promises.
            "volume": [0.0] * len(candles),
        },
        index=timestamps,
    )
    df.index.name = "timestamp"
    return df


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    weekly = df.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    weekly.index.name = "timestamp"
    return weekly.dropna(how="all")
