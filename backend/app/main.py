"""
FastAPI application entrypoint.

WHY THE PROVIDER IS CHOSEN HERE
---------------------------------
This is the ONLY place in the codebase that decides which
MarketDataProvider implementation is in use — driven by
`settings.market_data_provider` ("mock" or "deriv"). Nothing in
app/sessions, app/smc, app/risk, or app/api needs to change when that
switches, because they all depend on the abstract `MarketDataProvider`
interface, not a concrete class. See app/market_data/base.py for why that
matters.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.instruments import INSTRUMENT_PROFILES
from app.market_data.base import MarketDataProvider
from app.market_data.deriv_provider import DerivMarketDataProvider
from app.market_data.mock_provider import MockMarketDataProvider


def _build_provider() -> MarketDataProvider:
    if settings.market_data_provider == "deriv":
        return DerivMarketDataProvider(settings.deriv_app_id, timeout=settings.deriv_request_timeout)
    return MockMarketDataProvider(symbols=list(INSTRUMENT_PROFILES.keys()))


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Ambassador",
        version="0.1.0",
        description=(
            "Market intelligence and trading analysis platform. "
            "Presents evidence (structure, sessions, liquidity, risk math) — "
            "it does not generate BUY/SELL signals."
        ),
    )

    app.state.provider = _build_provider()

    app.include_router(router, prefix="/api")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
