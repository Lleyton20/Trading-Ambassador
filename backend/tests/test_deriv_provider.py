"""
Tests for DerivMarketDataProvider's parsing/resampling logic.

None of these touch the network: `_request` is monkeypatched with canned
Deriv-shaped JSON, matching the deterministic-fixture philosophy used
everywhere else in this test suite.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.market_data.deriv_provider import DerivMarketDataProvider


def _candle(epoch: int, o: float, h: float, l: float, c: float) -> dict:
    return {"epoch": epoch, "open": o, "high": h, "low": l, "close": c}


@pytest.fixture
def provider() -> DerivMarketDataProvider:
    return DerivMarketDataProvider("1089", symbol_map={"EURUSD": "frxEURUSD"})


def test_get_candles_parses_deriv_response(provider, monkeypatch):
    captured = {}

    def fake_request(payload):
        captured.update(payload)
        return {"candles": [_candle(1_700_000_000, 1.10, 1.11, 1.09, 1.105)]}

    monkeypatch.setattr(provider, "_request", fake_request)

    df = provider.get_candles("EURUSD", "H1", count=1)

    assert captured["ticks_history"] == "frxEURUSD"
    assert captured["granularity"] == 3600
    assert captured["count"] == 1
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.iloc[0]["close"] == 1.105
    assert df.iloc[0]["volume"] == 0.0
    assert df.index.tz is not None


def test_get_historical_data_uses_start_end(provider, monkeypatch):
    captured = {}

    def fake_request(payload):
        captured.update(payload)
        return {"candles": []}

    monkeypatch.setattr(provider, "_request", fake_request)

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, tzinfo=timezone.utc)
    provider.get_historical_data("EURUSD", "M5", start, end)

    assert captured["start"] == int(start.timestamp())
    assert captured["end"] == int(end.timestamp())
    assert captured["granularity"] == 300


def test_w1_resamples_daily_candles(provider, monkeypatch):
    # Two daily candles in the same ISO week should collapse into one
    # weekly bar: open = first day's open, close = last day's close.
    daily = [
        _candle(1_704_067_200, 1.10, 1.12, 1.09, 1.11),  # 2024-01-01 (Mon)
        _candle(1_704_153_600, 1.11, 1.13, 1.10, 1.125),  # 2024-01-02 (Tue)
    ]

    def fake_request(payload):
        assert payload["granularity"] == 86400  # D1, resampled below
        return {"candles": daily}

    monkeypatch.setattr(provider, "_request", fake_request)

    df = provider.get_candles("EURUSD", "W1", count=10)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["open"] == 1.10
    assert row["close"] == 1.125
    assert row["high"] == 1.13
    assert row["low"] == 1.09


def test_unknown_symbol_raises(provider):
    with pytest.raises(ValueError, match="No Deriv symbol mapping"):
        provider.get_candles("NOTASYMBOL", "H1", count=1)


def test_unsupported_timeframe_raises(provider):
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        provider.get_candles("EURUSD", "M2", count=1)


def test_deriv_error_response_raises(provider, monkeypatch):
    # Patches the WebSocket connection itself (not `_request`) so the
    # error-detection logic inside `_request` actually runs.
    import json as _json

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send(self, _payload):
            pass

        def recv(self, timeout=None):
            return _json.dumps({"error": {"message": "Symbol frxEURUSD is invalid."}})

    monkeypatch.setattr("app.market_data.deriv_provider.connect", lambda *a, **kw: FakeSocket())

    with pytest.raises(ValueError, match="Deriv API error"):
        provider.get_candles("EURUSD", "H1", count=1)
