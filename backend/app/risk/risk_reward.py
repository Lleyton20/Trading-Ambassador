"""
Risk:Reward calculator (spec section 18).

Deliberately tiny and side-effect free: given entry/stop/target it just
does arithmetic and a threshold classification. No trade is ever placed
from this module — it answers "is this hypothetical setup's RR good
enough to be worth considering", nothing more (spec section 46: never
claim a good RR guarantees a profitable trade).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskRewardResult:
    risk: float
    reward: float
    risk_reward_ratio: float
    meets_minimum: bool
    quality_label: str  # "LOW RISK/REWARD QUALITY" or "ACCEPTABLE RISK/REWARD"


def calculate_risk_reward(entry: float, stop_loss: float, take_profit: float, *, min_acceptable_rr: float = 2.0) -> RiskRewardResult:
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)

    if risk == 0:
        raise ValueError("Stop loss cannot equal entry price (risk would be zero).")

    ratio = reward / risk
    meets_minimum = ratio >= min_acceptable_rr

    return RiskRewardResult(
        risk=risk,
        reward=reward,
        risk_reward_ratio=ratio,
        meets_minimum=meets_minimum,
        quality_label="ACCEPTABLE RISK/REWARD" if meets_minimum else "LOW RISK/REWARD QUALITY",
    )
