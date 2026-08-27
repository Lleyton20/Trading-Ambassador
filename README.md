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
│   ├── app/
│   │   ├── config.py            # ALL tunable parameters, one place (see file for why)
│   │   ├── instruments.py       # explicit per-symbol specs (pip size, contract size, ...)
│   │   ├── database.py          # SQLAlchemy engine/session (SQLite dev, Postgres-ready)
│   │   ├── models/              # DB tables: instruments, candles, swing_points,
│   │   │                        #   market_structure_events, sessions, daily_levels
│   │   ├── schemas/              # Pydantic request/response shapes for the API
│   │   ├── market_data/          # MarketDataProvider interface + a deterministic
│   │   │                        #   dev fixture provider + OHLC data-quality checks
│   │   ├── sessions/              # Asian/London/New York sessions, ODH/ODL, PDH/PDL
│   │   ├── smc/                  # swing points, HH/HL/LH/LL, BOS/CHoCH detection
│   │   ├── risk/                 # risk:reward calculator, position size calculator
│   │   └── api/                  # FastAPI routes tying the above together
│   ├── tests/                    # pytest, deterministic hand-verified fixtures
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

Frontend, order blocks / fair value gaps / liquidity sweeps, news
intelligence, backtesting, and the trade journal are **not built yet** —
see "Roadmap" below. This is intentional: the spec this project follows
is explicit that building everything at once produces an unreviewable
mess. Each phase ships as a working, tested slice.

## What's working right now (Milestone 1)

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
- **Risk:Reward & position sizing**: RR calculator with a configurable
  minimum-quality threshold, and a position-size calculator driven by
  each instrument's real contract size/lot rules instead of a guessed
  constant.
- **REST API** (FastAPI) wiring all of the above into real endpoints —
  see below.
- **19 passing tests** against hand-verified, deterministic fixtures
  (not just "it ran without crashing").

## Key design decisions

- **No trade execution exists anywhere in this codebase.** The spec is
  explicit: this is an analysis and decision-support platform, not an
  auto-trading bot. Analysis and backtesting must be validated long
  before live execution is even considered.
- **Every module talks to a `MarketDataProvider` interface**, never a
  concrete broker client. A dev fixture (`mock_provider.py`) implements
  it today; a real MT5 or Deriv API connection is a drop-in replacement
  later without touching the session/SMC/risk code.
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
```

## Testing

```bash
cd backend
python -m pytest -v
```

## API endpoints (Milestone 1)

| Endpoint | Purpose |
|---|---|
| `GET /api/markets` | List known instruments with current price |
| `GET /api/markets/{symbol}/candles` | Historical candles for a timeframe |
| `GET /api/markets/{symbol}/daily-levels` | ODH/ODL, PDH/PDL, price status |
| `GET /api/markets/{symbol}/sessions` | Asian/London/NY session ranges |
| `GET /api/markets/{symbol}/smc` | Swing points, bias, BOS/CHoCH events |
| `GET /api/markets/{symbol}/analysis` | Combined dashboard "overview" payload |
| `POST /api/risk/risk-reward` | RR calculation + quality classification |
| `POST /api/risk/position-size` | Position size from account/risk/instrument |

## Data sources

Milestone 1 ships with a deterministic **synthetic data fixture**
(`app/market_data/mock_provider.py`), clearly labeled as such in code and
never used as a stand-in for real market data claims. A real provider
(MetaTrader 5, Deriv's WebSocket API, or another vendor) is a drop-in
`MarketDataProvider` implementation away — see that file's docstring.

## Roadmap

- **Milestone 2**: Liquidity (equal highs/lows, sweeps of session/swing
  levels), Order Blocks (evidence-linked, with mitigation tracking), Fair
  Value Gaps, Premium/Discount — completing the SMC engine.
- **Milestone 3**: Confluence scoring engine; a real market-data provider
  (MT5 or Deriv API) behind the existing `MarketDataProvider` interface;
  Alembic migrations to replace `create_all()`.
- **Milestone 4**: News intelligence engine + economic calendar.
- **Milestone 5**: Backtesting engine (explicitly designed to reuse the
  same non-lookahead-safe functions already in `sessions/engine.py` and
  `smc/structure.py`).
- **Milestone 6**: React/TypeScript dashboard frontend.
- **Milestone 7**: Trade journal + performance analytics.

## Known gaps (intentional, tracked)

- No database migrations yet (`Base.metadata.create_all()` is used for
  local dev). Alembic is the natural next step once real data starts
  living in the tables.
- Session range detection assumes a session's local hours don't cross
  midnight (true for the three default sessions; documented in
  `sessions/engine.py`).
- No authentication/users yet — single-user local development only.
