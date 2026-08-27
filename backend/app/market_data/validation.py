"""
Data-quality validation for candle data (spec section 36).

Every provider's output should be passed through `validate_candles` before
it's trusted by the rest of the app. This is what lets us catch a bad
data feed (a broker glitch, a provider outage returning stale rows) before
it silently corrupts a structure/BOS/CHOCH read.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationIssue:
    kind: str
    message: str
    index: int | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def __bool__(self) -> bool:
        return self.is_valid


def validate_candles(df: pd.DataFrame, *, max_price_jump_pct: float = 0.25) -> ValidationResult:
    """
    Runs the checks the spec calls out explicitly: missing/duplicate/
    out-of-order timestamps, missing OHLC values, and invalid OHLC
    relationships (high >= open/close/low, low <= open/close).

    `max_price_jump_pct` is a sanity check for "extreme erroneous prices"
    (e.g. a bad tick reporting a 10x price spike) — real displacement
    candles on volatile synthetic indices can be large, so this is
    intentionally generous by default rather than flagging normal
    volatility as bad data.
    """
    result = ValidationResult()

    required_cols = {"open", "high", "low", "close"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        result.issues.append(ValidationIssue("missing_columns", f"Missing columns: {missing_cols}"))
        return result  # can't check further without the columns

    if df[list(required_cols)].isna().any().any():
        bad_rows = df.index[df[list(required_cols)].isna().any(axis=1)]
        for idx in bad_rows:
            result.issues.append(ValidationIssue("missing_ohlc", "Missing OHLC value", index=idx))

    if not df.index.is_monotonic_increasing:
        result.issues.append(ValidationIssue("out_of_order", "Timestamps are not strictly increasing"))

    duplicate_count = int(df.index.duplicated().sum())
    if duplicate_count:
        result.issues.append(ValidationIssue("duplicate_timestamps", f"{duplicate_count} duplicate timestamp(s)"))

    invalid_ohlc = df[
        (df["high"] < df["open"]) | (df["high"] < df["close"]) |
        (df["low"] > df["open"]) | (df["low"] > df["close"]) |
        (df["high"] < df["low"])
    ]
    for idx in invalid_ohlc.index:
        result.issues.append(ValidationIssue("invalid_ohlc_relationship", "high/low do not bound open/close", index=idx))

    pct_change = df["close"].pct_change(fill_method=None).abs()
    extreme = pct_change[pct_change > max_price_jump_pct]
    for idx in extreme.index:
        result.issues.append(
            ValidationIssue("extreme_price_jump", f"{extreme[idx]:.1%} move from previous close", index=idx)
        )

    return result
