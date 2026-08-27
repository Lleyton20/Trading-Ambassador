"""
FastAPI application entrypoint.

WHY A MOCK PROVIDER IS WIRED UP HERE
--------------------------------------
This is the ONLY place in the codebase that decides which
MarketDataProvider implementation is in use. Swapping to a real MT5 or
Deriv-API-backed provider later means changing the one line below —
nothing in app/sessions, app/smc, app/risk, or app/api needs to change,
because they all depend on the abstract `MarketDataProvider` interface,
not a concrete class. See app/market_data/base.py for why that matters.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.database import init_db
from app.instruments import INSTRUMENT_PROFILES
from app.market_data.mock_provider import MockMarketDataProvider


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

    # Dev/default provider — see module docstring.
    app.state.provider = MockMarketDataProvider(symbols=list(INSTRUMENT_PROFILES.keys()))

    app.include_router(router, prefix="/api")

    @app.on_event("startup")
    def _on_startup() -> None:
        init_db()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
