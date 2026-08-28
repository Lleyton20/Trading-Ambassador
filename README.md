# Trading Ambassador

A market intelligence and trading **analysis** platform for Forex and Deriv
synthetic indices (Volatility, Boom, and Crash indices), built around
Smart Money Concepts (SMC), session analysis, and risk management.

**Trading Ambassador presents evidence — it does not generate BUY/SELL
signals.** Every endpoint answers a question ("what is the market
structure?", "where is liquidity?", "is this setup's risk:reward
acceptable?") with data and reasoning, and leaves the trading decision to
the person using it.

## Disclaimer

Trading Ambassador provides analytical and educational information. It
does not guarantee profitable trades. Trading involves financial risk.
Structure classifications, session analysis, and risk:reward figures are
mechanical calculations over historical/live price data — they are not
predictions, and historical behavior does not guarantee future results.

## Architecture

```
trading-ambassador/
├── backend/
│   ├── alembic/                  # schema migrations (see database.py for why)
│   ├── app/
│   │   ├── config.py            # ALL tunable parameters, one place (see file for why)
│   │   ├── instruments.py       # explicit per-symbol specs (pip size, contract size, ...)
│   │   ├── database.py          # SQLAlchemy engine/session (SQLite dev, Postgres-ready)
│   │   ├── persistence.py        # upserts computed SMC results into their DB tables
│   │   ├── models/              # DB tables: instruments, candles, swing_points,
│   │   │                        #   market_structure_events, order_blocks,
│   │   │                        #   fair_value_gaps, liquidity_levels/sweeps,
│   │   │                        #   sessions, daily_levels
│   │   ├── schemas/              # Pydantic request/response shapes for the API
│   │   ├── market_data/          # MarketDataProvider interface, a deterministic dev
│   │   │                        #   fixture, a live Deriv API provider, OHLC checks
│   │   ├── sessions/              # Asian/London/New York sessions, ODH/ODL, PDH/PDL
│   │   ├── smc/                  # swings, HH/HL/LH/LL, BOS/CHoCH, order blocks,
│   │   │                        #   fair value gaps, liquidity sweeps, premium/discount
│   │   ├── confluence/            # weighted confluence scoring across the above
│   │   ├── risk/                 # risk:reward calculator, position size calculator
│   │   └── api/                  # FastAPI routes tying the above together
│   ├── tests/                    # pytest, deterministic hand-verified fixtures
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

Frontend, news intelligence, and backtesting are **not built yet** — see
"Roadmap" below. This is intentional: the spec this project follows is
explicit that building everything at once produces an unreviewable mess.
Each phase ships as a working, tested slice.

## What's working right now (Milestones 1-3)

- **Market data layer**: a `MarketDataProvider` interface (spec-style
  vendor abstraction) with a deterministic synthetic-data provider for
  development, plus OHLC data-quality validation (missing/duplicate/
  out-of-order timestamps, invalid OHLC relationships, extreme price
  jumps).
- **Session engine**: Asian/London/New York session open/high/low/close,
  computed with real IANA timezones (`zoneinfo`) so daylight saving is
  handled correctly, not hard-coded as a fixed UTC offset.
- **Opening Day High/Low & Previous Day High/Low**: computed as a
  *running* value (never peeking at candles that haven't happened yet
  within the day) from an explicitly configurable trading-day timezone
  and rollover hour.
- **Market structure (SMC)**: validated swing-point detection, HH/HL/LH/LL
  labeling, and Break of Structure / Change of Character detection with
  an explicit, documented algorithmic definition for each (candle-close
  confirmation, not wick touches) — see `app/smc/structure.py`'s
  docstring for the reasoning.
- **Order blocks**: created only from a confirmed BOS/CHoCH whose
  confirming candle clears a displacement threshold (ATR-relative, so it
  scales sensibly between low-volatility Forex and spiky synthetic
  indices) — not from "the last opposite candle" indiscriminately.
  Tracks mitigation state and retest count.
- **Fair Value Gaps**: three-candle detection with a mitigation
  *percentage* (not just filled/unfilled), so a partially-filled gap is
  reported as such.
- **Liquidity**: equal-highs/equal-lows clustering with a percentage-of-
  price tolerance (never exact float equality), plus Previous Day
  High/Low as liquidity levels. Each level reports whether it's been
  swept — defined as a wick beyond the level followed by a candle
  closing back through it, not merely touching it.
- **Premium/Discount**: the active dealing range from the most recent
  confirmed swing high/low, with price classified as premium, discount,
  or equilibrium.
- **Risk:Reward & position sizing**: RR calculator with a configurable
  minimum-quality threshold, and a position-size calculator driven by
  each instrument's real contract size/lot rules instead of a guessed
  constant.
- **Live market data**: a `DerivMarketDataProvider` alongside the mock
  fixture, backed by Deriv's public WebSocket API — covers both Forex
  majors and the synthetic indices from one connection, no API token
  required. Switch to it with `MARKET_DATA_PROVIDER=deriv`; see
  `app/market_data/deriv_provider.py`.
- **Persistence**: swing points, structure events, order blocks, FVGs,
  and liquidity levels/sweeps are upserted into their DB tables as a side
  effect of the `/smc` and `/liquidity` endpoints (`app/persistence.py`)
  — every response is still computed fresh from live candles, the DB
  write is an audit trail for later milestones (backtesting, journal).
- **Confluence scoring**: combines HTF bias alignment, liquidity sweeps,
  CHoCH, FVGs, order blocks, premium/discount, and session timing into a
  single weighted score against the weights in `app/config.py`
  (`app/confluence/engine.py`) — still evidence, not a signal.
- **Schema migrations**: Alembic (`backend/alembic/`), reading
  `DATABASE_URL` from the same `Settings` object as the rest of the app.
- **REST API** (FastAPI) wiring all of the above into real endpoints —
  see below.
- **47 passing tests** against hand-verified, deterministic fixtures
  (not just "it ran without crashing").

## Key design decisions

- **No trade execution exists anywhere in this codebase.** The spec is
  explicit: this is an analysis and decision-support platform, not an
  auto-trading bot. Analysis and backtesting must be validated long
  before live execution is even considered.
- **Every module talks to a `MarketDataProvider` interface**, never a
  concrete broker client. A dev fixture (`mock_provider.py`) and a live
  Deriv API provider (`deriv_provider.py`) both implement it; switching
  between them is a one-line change in `app/main.py`, nothing in the
  session/SMC/risk code cares which one is active. Deriv was chosen over
  MetaTrader 5 because MT5's official Python package is Windows-only.
- **One `Settings` object holds every tunable parameter** (`app/config.py`)
  — nothing is hard-coded inside detection logic.
- **BOS and CHoCH have distinct, explicit definitions**: BOS is a candle
  close beyond the confirmed swing level *with* the prevailing bias;
  CHoCH is the same break *against* the prevailing bias. Both require a
  close (not a wick) and accept an optional minimum-displacement
  threshold.
- **Position sizing uses each instrument's real `contract_size`/`pip_size`**
  via an explicit `InstrumentProfile` registry — never a guessed constant.

## Tech stack

- **Backend**: Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, pandas, NumPy
- **Database**: SQLite for local development (zero setup); PostgreSQL-ready
  by changing one environment variable (`DATABASE_URL`)
- **Testing**: pytest, deterministic fixtures (no reliance on live market
  data or manual eyeballing of charts)
- **Frontend**: not yet built (Roadmap Phase 6 — React/TypeScript planned)

## Installation

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional — every setting has a safe default
alembic upgrade head    # creates the local SQLite schema
```

## Running the backend

```bash
cd backend
uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for interactive API docs, or try:

```bash
curl http://127.0.0.1:8000/api/markets
curl "http://127.0.0.1:8000/api/markets/EURUSD/analysis"
curl "http://127.0.0.1:8000/api/markets/CRASH500/smc?timeframe=H1"
curl "http://127.0.0.1:8000/api/markets/EURUSD/liquidity?timeframe=H1"
curl "http://127.0.0.1:8000/api/markets/EURUSD/confluence?timeframe=H1"
```

To use live Deriv data instead of the mock fixture, set
`MARKET_DATA_PROVIDER=deriv` in `.env` (or the environment) before
starting the server — no API token needed, see "Data sources" below.

## Testing

```bash
cd backend
python -m pytest -v
```

## API endpoints (Milestones 1-3)

| Endpoint | Purpose |
|---|---|
| `GET /api/markets` | List known instruments with current price |
| `GET /api/markets/{symbol}/candles` | Historical candles for a timeframe |
| `GET /api/markets/{symbol}/daily-levels` | ODH/ODL, PDH/PDL, price status |
| `GET /api/markets/{symbol}/sessions` | Asian/London/NY session ranges |
| `GET /api/markets/{symbol}/smc` | Bias, BOS/CHoCH, order blocks, FVGs, premium/discount |
| `GET /api/markets/{symbol}/liquidity` | Equal highs/lows + PDH/PDL, each with sweep status |
| `GET /api/markets/{symbol}/confluence` | Weighted confluence score + per-factor breakdown |
| `GET /api/markets/{symbol}/analysis` | Combined dashboard "overview" payload |
| `POST /api/risk/risk-reward` | RR calculation + quality classification |
| `POST /api/risk/position-size` | Position size from account/risk/instrument |

## Data sources

`app/market_data/mock_provider.py` is a deterministic **synthetic data
fixture** — clearly labeled as such in code, never used as a stand-in for
real market data claims, and still the default (`MARKET_DATA_PROVIDER=mock`)
so the project runs with zero setup. `app/market_data/deriv_provider.py`
is a live provider backed by Deriv's public WebSocket API: it covers both
Forex majors and Deriv's synthetic indices from one connection, and needs
no API token for market data (only a public `app_id`, defaulted to
Deriv's own demo id). Enable it with `MARKET_DATA_PROVIDER=deriv`.

## Roadmap

- **Milestone 4**: News intelligence engine + economic calendar.
- **Milestone 5**: Backtesting engine (explicitly designed to reuse the
  same non-lookahead-safe functions already in `sessions/engine.py` and
  `smc/structure.py`).
- **Milestone 6**: React/TypeScript dashboard frontend.
- **Milestone 7**: Trade journal + performance analytics.

## Known gaps (intentional, tracked)

- Persisted SMC rows are an audit trail, not yet read back by anything —
  the API always computes its response fresh from live candles. Reading
  historical rows back is a natural fit for the backtester (Milestone 5).
- Raw candles aren't persisted yet, only the SMC results derived from
  them (`app/models/candle.py`'s table exists but nothing writes to it) —
  intentionally out of Milestone 3's scope; revisit alongside Milestone 5.
- Session range detection assumes a session's local hours don't cross
  midnight (true for the three default sessions; documented in
  `sessions/engine.py`).
- No authentication/users yet — single-user local development only.
