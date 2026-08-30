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

WHY THE ALERT WATCHER RUNS AS A BACKGROUND ASYNCIO TASK
-----------------------------------------------------------
`app/alerts/watcher.py`'s zone-checking is synchronous (pandas/SQLAlchemy,
same as every other engine in this app). Running it inside `asyncio.to_thread`
on a fixed interval means it never blocks a request being served, without
pulling in a scheduler/task-queue dependency (APScheduler, Celery, ...) for
what's just "call a function every N seconds." Off by default
(`settings.alerts_enabled`), so a fresh checkout never starts hitting the
live market-data provider on its own.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts.watcher import check_all_instruments
from app.api.alerts_routes import router as alerts_router
from app.api.news_routes import router as news_router
from app.api.routes import router
from app.config import settings
from app.database import SessionLocal
from app.instruments import INSTRUMENT_PROFILES
from app.market_data.base import MarketDataProvider
from app.market_data.deriv_provider import DerivMarketDataProvider
from app.market_data.mock_provider import MockMarketDataProvider

logger = logging.getLogger(__name__)

# The dashboard's Vite dev server - see frontend/README or the project
# README's "Running the dashboard" section.
_DASHBOARD_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _build_provider() -> MarketDataProvider:
    if settings.market_data_provider == "deriv":
        return DerivMarketDataProvider(settings.deriv_app_id, timeout=settings.deriv_request_timeout)
    return MockMarketDataProvider(symbols=list(INSTRUMENT_PROFILES.keys()))


async def _alerts_loop(provider: MarketDataProvider) -> None:
    while True:
        db = SessionLocal()
        try:
            await asyncio.to_thread(check_all_instruments, db, provider)
        except Exception:
            # A bad poll shouldn't kill the loop - try again next interval.
            logger.exception("Alert polling iteration failed")
        finally:
            db.close()
        await asyncio.sleep(settings.alerts_poll_interval_seconds)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task: asyncio.Task | None = None
    if settings.alerts_enabled:
        task = asyncio.create_task(_alerts_loop(app.state.provider))
    yield
    if task is not None:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Ambassador",
        version="0.1.0",
        description=(
            "Market intelligence and trading analysis platform. "
            "Presents evidence (structure, sessions, liquidity, risk math) — "
            "it does not generate BUY/SELL signals."
        ),
        lifespan=_lifespan,
    )

    app.state.provider = _build_provider()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DASHBOARD_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")
    app.include_router(news_router, prefix="/api")
    app.include_router(alerts_router, prefix="/api")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
