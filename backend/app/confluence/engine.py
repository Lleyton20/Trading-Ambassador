"""
Confluence scoring: combines the SMC/session evidence already computed
elsewhere into a single weighted score (spec Milestone 3).

WHY THIS IS A SCORE, NOT A SIGNAL
------------------------------------
Every other endpoint in this app presents evidence and leaves the trading
decision to the person using it (see app/api/routes.py's module
docstring) - this is no different. The score and its per-factor breakdown
answer "how much of the SMC checklist lines up right now?", not "should I
buy or sell". Nothing here recommends a direction or a trade.

WHY WEIGHTS AREN'T PASSED AS A CONFIG OBJECT
-----------------------------------------------
Per app/config.py's own rule, every tunable trading value lives in one
place. The seven weights this module scores against
(`confluence_weight_*`) were already reserved there in Milestone 1; this
function takes them as explicit keyword arguments (like every other
engine in this codebase takes its settings) rather than importing
`settings` directly, so it stays a pure function callers can test without
touching global config.
"""
from __future__ import annotations

from dataclasses import dataclass

# Which higher timeframe a given timeframe's bias should be checked
# against for the "higher-timeframe bias aligned" factor - same small,
# explicit-dict style as _TIMEFRAME_MINUTES / _SESSION_CONFIGS elsewhere.
HTF_MAP: dict[str, str] = {
    "M1": "M15", "M5": "M15", "M15": "H1", "M30": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1",
}


@dataclass
class ConfluenceFactor:
    name: str
    weight: int
    met: bool


@dataclass
class ConfluenceResult:
    score: int
    max_score: int
    factors: list[ConfluenceFactor]

    @property
    def score_pct(self) -> float:
        return (self.score / self.max_score * 100.0) if self.max_score else 0.0


def calculate_confluence_score(
    *,
    bias: str,
    htf_bias: str,
    has_recent_liquidity_sweep: bool,
    has_recent_choch: bool,
    has_unmitigated_fvg_with_bias: bool,
    has_unmitigated_order_block_with_bias: bool,
    price_favors_bias: bool,
    session_active: bool,
    weight_htf_bias: int,
    weight_liquidity_sweep: int,
    weight_choch: int,
    weight_fvg: int,
    weight_order_block: int,
    weight_premium_discount: int,
    weight_session: int,
) -> ConfluenceResult:
    """
    Scores each factor as met/not-met against `bias` (the timeframe's own
    market structure bias) and sums the configured weights. Every input is
    a plain fact already derived by the sessions/SMC engines - this
    function only combines them, it doesn't compute any of them itself,
    which keeps it trivially testable and reusable later inside the
    backtester.
    """
    factors = [
        ConfluenceFactor("htf_bias_aligned", weight_htf_bias, bias != "neutral" and bias == htf_bias),
        ConfluenceFactor("liquidity_sweep", weight_liquidity_sweep, has_recent_liquidity_sweep),
        ConfluenceFactor("choch", weight_choch, has_recent_choch),
        ConfluenceFactor("fair_value_gap", weight_fvg, has_unmitigated_fvg_with_bias),
        ConfluenceFactor("order_block", weight_order_block, has_unmitigated_order_block_with_bias),
        ConfluenceFactor("premium_discount", weight_premium_discount, price_favors_bias),
        ConfluenceFactor("session_active", weight_session, session_active),
    ]
    score = sum(f.weight for f in factors if f.met)
    max_score = sum(f.weight for f in factors)
    return ConfluenceResult(score=score, max_score=max_score, factors=factors)
