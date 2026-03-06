from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RegimeState:
    regime: str  # risk_on | neutral | risk_off
    is_bullish_trend: bool
    is_bearish_trend: bool
    hv30: float
    breadth_pct: float
    macro_blocked: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class AllocationDecision:
    allowed: bool
    regime: RegimeState
    budget: Dict[str, Any]
    reason: str = ""


def compute_regime_state(day_ctx: Dict[str, Any]) -> RegimeState:
    """
    Determine market regime from trend/vol/breadth/macro context.
    Expected keys in day_ctx:
      - is_bullish_trend: bool
      - is_bearish_trend: bool
      - hv30: float
      - breadth_pct: float
      - macro_blocked: bool
      - vix_max_threshold: float (default 0.40)
      - breadth_min_pct: float (default 50)
    """
    bullish = bool(day_ctx.get("is_bullish_trend", False))
    bearish = bool(day_ctx.get("is_bearish_trend", False))
    hv30 = float(day_ctx.get("hv30", 0.20) or 0.20)
    breadth = float(day_ctx.get("breadth_pct", 60.0) or 60.0)
    macro_blocked = bool(day_ctx.get("macro_blocked", False))
    hv_max = float(day_ctx.get("vix_max_threshold", 0.40) or 0.40)
    breadth_min = float(day_ctx.get("breadth_min_pct", 50.0) or 50.0)

    reasons: List[str] = []
    if macro_blocked:
        reasons.append("macro_window")
    if bearish:
        reasons.append("bearish_trend")
    if hv30 > hv_max:
        reasons.append("high_volatility")
    if breadth < breadth_min:
        reasons.append("weak_breadth")

    if (
        macro_blocked
        or bearish
        or hv30 > (hv_max * 1.15)
        or breadth < (breadth_min * 0.75)
    ):
        regime = "risk_off"
    elif bullish and hv30 <= hv_max and breadth >= breadth_min:
        regime = "risk_on"
    else:
        regime = "neutral"
        if not reasons:
            reasons.append("mixed_regime")

    return RegimeState(
        regime=regime,
        is_bullish_trend=bullish,
        is_bearish_trend=bearish,
        hv30=hv30,
        breadth_pct=breadth,
        macro_blocked=macro_blocked,
        reasons=reasons,
    )


def strategy_allowed(strategy_id: str, variant: str, regime: RegimeState) -> bool:
    sid = str(strategy_id or "").lower()
    v = str(variant or "").lower()

    if regime.regime == "risk_on":
        return True

    if regime.regime == "neutral":
        # Permit lower-beta income profiles in neutral conditions.
        if "put_credit_spread" in sid:
            return True
        if "putwrite" in sid:
            return True
        if "collar" in sid and ("defensive" in v):
            return True
        if "intraday_open_close_options" in sid and ("conservative" in v):
            return True
        # Allow CSP and Wheel strategies in neutral
        if "csp" in sid or "wheel" in sid:
            return True
        return False

    # risk_off
    # In this phase we block new entries and preserve cash discipline.
    return False


def risk_budget_for_regime(regime: RegimeState) -> Dict[str, Any]:
    if regime.regime == "risk_on":
        return {
            "allocation_mult": 1.0,
            "heat_mult": 1.0,
            "max_new_positions": 10,
            "max_trades_per_day": 4,
        }
    if regime.regime == "neutral":
        return {
            "allocation_mult": 0.7,
            "heat_mult": 0.6,
            "max_new_positions": 3,
            "max_trades_per_day": 2,
        }
    return {
        "allocation_mult": 0.25,
        "heat_mult": 0.25,
        "max_new_positions": 0,
        "max_trades_per_day": 0,
    }
