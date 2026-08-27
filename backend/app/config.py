"""
Centralized configuration for Trading Ambassador.

WHY THIS FILE EXISTS
--------------------
It would be easy to let trading parameters accumulate as scattered
constants inside whichever module happens to need them (e.g. a
`tolerance: float = 0.0001` default buried inside a liquidity detector).
That makes the system hard to reason about: to know "what tolerance does
this app use for liquidity sweeps?" you'd have to go read the source of
the detector itself. The master spec is explicit that this is an
anti-pattern (section 37: "Never scatter important trading values
throughout the code").

So every tunable trading parameter lives in ONE place: this `Settings`
object. Every other module receives its parameters as function arguments
from here — it never reads a YAML file or an env var directly. This means:
  1. You can see every knob the system has in one file.
  2. Tests can construct a `Settings` with different values without
     touching disk or environment variables.
  3. Changing a default later is a one-line diff, not a hunt across files.

Settings are loaded from environment variables (and an optional `.env`
file) using pydantic-settings, so secrets (API keys, DB credentials) never
need to be hard-coded — see `.env.example` for the full list.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database -----------------------------------------------------
    # Defaults to a local SQLite file so the project runs with zero setup.
    # Point this at a real Postgres instance in production by setting
    # DATABASE_URL, e.g. postgresql+psycopg://user:pass@host:5432/trading_ambassador
    database_url: str = "sqlite:///./trading_ambassador.db"

    # --- Trading day / timezone ----------------------------------------
    # This is the single most important "hidden assumption" the spec calls
    # out explicitly (section 3): what timezone defines when a trading day
    # starts, and therefore what "Opening Day High/Low" means. We do NOT
    # bury this inside a calculation — it is a named, documented setting.
    # Forex convention: the trading day rolls over at 17:00 New York time
    # (the FX market's traditional day-close). We default to that, but it
    # is fully overridable via TRADING_DAY_TIMEZONE / TRADING_DAY_ROLLOVER_HOUR.
    trading_day_timezone: str = "America/New_York"
    trading_day_rollover_hour: int = 17  # local hour (0-23) the new day begins

    # --- Session engine --------------------------------------------------
    # Each session is defined by an IANA timezone + local start/end hour.
    # Using IANA zones (not fixed UTC offsets) is what makes DST handling
    # correct automatically — zoneinfo knows when London/NY switch clocks.
    asian_session_timezone: str = "Asia/Tokyo"
    asian_session_start_hour: int = 0
    asian_session_end_hour: int = 9

    london_session_timezone: str = "Europe/London"
    london_session_start_hour: int = 8
    london_session_end_hour: int = 17

    new_york_session_timezone: str = "America/New_York"
    new_york_session_start_hour: int = 8
    new_york_session_end_hour: int = 17

    # --- SMC engine tuning ----------------------------------------------
    swing_lookback: int = 2            # candles on each side to confirm a swing point
    min_displacement_atr_mult: float = 1.5   # candle body must exceed ATR * this to count as "displacement"
    liquidity_tolerance_pct: float = 0.0005  # 0.05% of price — used for "equal highs/lows" tolerance

    # --- Risk engine ------------------------------------------------------
    min_acceptable_rr: float = 2.0       # setups below this RR are flagged LOW quality
    default_risk_per_trade_pct: float = 1.0  # used by the position size calculator

    # --- News engine (reserved for a later milestone; centralized now so
    # nothing gets hard-coded ad hoc when that module is built) -----------
    news_blackout_minutes_before: int = 30
    news_blackout_minutes_after: int = 30

    # --- Confluence scoring weights (reserved for a later milestone) -----
    confluence_weight_htf_bias: int = 2
    confluence_weight_liquidity_sweep: int = 2
    confluence_weight_choch: int = 2
    confluence_weight_fvg: int = 1
    confluence_weight_order_block: int = 1
    confluence_weight_premium_discount: int = 1
    confluence_weight_session: int = 1


settings = Settings()
