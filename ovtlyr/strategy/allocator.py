from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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


@dataclass(frozen=True)
class PortfolioOverlayConfig:
    profile_id: str
    soft_drawdown_pct: Optional[float] = None
    hard_drawdown_pct: Optional[float] = None
    resume_drawdown_pct: Optional[float] = None
    throttle_risk_mult: float = 1.0
    kill_switch_vix_threshold: Optional[float] = None
    kill_switch_hv20_percentile_threshold: Optional[float] = None
    kill_switch_resume_days: int = 0
    max_total_new_risk_pct: float = 0.02


@dataclass
class PortfolioOverlayState:
    peak_equity: float = 0.0
    drawdown_mode: str = "normal"  # normal | soft_throttle | hard_stop
    volatility_pause_active: bool = False
    volatility_clear_days: int = 0


@dataclass(frozen=True)
class PortfolioOverlayDecision:
    allow_new_entries: bool
    risk_scale: float
    drawdown_mode: str
    volatility_pause_active: bool
    current_drawdown_pct: float
    reason: str


PORTFOLIO_OVERLAY_PROFILES: Dict[str, PortfolioOverlayConfig] = {
    "regime_core_base": PortfolioOverlayConfig(
        profile_id="regime_core_base",
        max_total_new_risk_pct=0.02,
    ),
    "regime_core_drawdown": PortfolioOverlayConfig(
        profile_id="regime_core_drawdown",
        soft_drawdown_pct=5.0,
        hard_drawdown_pct=8.0,
        resume_drawdown_pct=4.0,
        throttle_risk_mult=0.50,
        max_total_new_risk_pct=0.02,
    ),
    "regime_core_killswitch": PortfolioOverlayConfig(
        profile_id="regime_core_killswitch",
        kill_switch_vix_threshold=35.0,
        kill_switch_hv20_percentile_threshold=97.5,
        kill_switch_resume_days=3,
        max_total_new_risk_pct=0.02,
    ),
    "regime_core_overlay": PortfolioOverlayConfig(
        profile_id="regime_core_overlay",
        soft_drawdown_pct=5.0,
        hard_drawdown_pct=8.0,
        resume_drawdown_pct=4.0,
        throttle_risk_mult=0.50,
        kill_switch_vix_threshold=35.0,
        kill_switch_hv20_percentile_threshold=97.5,
        kill_switch_resume_days=3,
        max_total_new_risk_pct=0.02,
    ),
}


def get_portfolio_overlay_config(profile_id: Optional[str]) -> Optional[PortfolioOverlayConfig]:
    if not profile_id:
        return None
    key = str(profile_id).strip()
    if not key:
        return None
    if key not in PORTFOLIO_OVERLAY_PROFILES:
        raise ValueError(f"Unknown portfolio overlay profile: {profile_id}")
    return PORTFOLIO_OVERLAY_PROFILES[key]


def evaluate_portfolio_overlay(
    config: Optional[PortfolioOverlayConfig],
    state: PortfolioOverlayState,
    *,
    current_equity: float,
    vix_level: Optional[float] = None,
    hv20_percentile: Optional[float] = None,
) -> Tuple[PortfolioOverlayState, PortfolioOverlayDecision]:
    if config is None:
        peak = max(float(current_equity or 0.0), float(state.peak_equity or 0.0))
        next_state = PortfolioOverlayState(
            peak_equity=peak,
            drawdown_mode="normal",
            volatility_pause_active=False,
            volatility_clear_days=0,
        )
        return next_state, PortfolioOverlayDecision(
            allow_new_entries=True,
            risk_scale=1.0,
            drawdown_mode="normal",
            volatility_pause_active=False,
            current_drawdown_pct=0.0 if peak <= 0 else max((peak - current_equity) / peak * 100.0, 0.0),
            reason="normal",
        )

    equity = max(float(current_equity or 0.0), 0.0)
    peak = max(float(state.peak_equity or 0.0), equity)
    current_drawdown_pct = 0.0 if peak <= 0 else max((peak - equity) / peak * 100.0, 0.0)

    volatility_trigger = False
    if (
        config.kill_switch_vix_threshold is not None
        and vix_level is not None
    ):
        volatility_trigger = float(vix_level) > float(config.kill_switch_vix_threshold)
    elif (
        config.kill_switch_hv20_percentile_threshold is not None
        and hv20_percentile is not None
    ):
        volatility_trigger = float(hv20_percentile) >= float(config.kill_switch_hv20_percentile_threshold)

    volatility_pause_active = bool(state.volatility_pause_active)
    volatility_clear_days = int(state.volatility_clear_days or 0)
    if volatility_trigger:
        volatility_pause_active = True
        volatility_clear_days = 0
    elif volatility_pause_active:
        volatility_clear_days += 1
        if volatility_clear_days >= int(config.kill_switch_resume_days or 0):
            volatility_pause_active = False
            volatility_clear_days = 0
    else:
        volatility_clear_days = 0

    previous_mode = str(state.drawdown_mode or "normal")
    drawdown_mode = "normal"
    if (
        config.hard_drawdown_pct is not None
        and current_drawdown_pct >= float(config.hard_drawdown_pct)
    ):
        drawdown_mode = "hard_stop"
    elif (
        config.soft_drawdown_pct is not None
        and current_drawdown_pct >= float(config.soft_drawdown_pct)
    ):
        drawdown_mode = "soft_throttle"
    elif previous_mode in {"soft_throttle", "hard_stop"} and (
        config.resume_drawdown_pct is not None
        and current_drawdown_pct >= float(config.resume_drawdown_pct)
    ):
        drawdown_mode = "soft_throttle"

    reason = "normal"
    allow_new_entries = True
    risk_scale = 1.0
    if drawdown_mode == "hard_stop":
        allow_new_entries = False
        reason = "drawdown_hard_stop"
    elif volatility_pause_active:
        allow_new_entries = False
        reason = "volatility_pause"
    elif drawdown_mode == "soft_throttle":
        allow_new_entries = True
        risk_scale = float(config.throttle_risk_mult)
        reason = "drawdown_throttle"

    next_state = PortfolioOverlayState(
        peak_equity=peak,
        drawdown_mode=drawdown_mode,
        volatility_pause_active=volatility_pause_active,
        volatility_clear_days=volatility_clear_days,
    )
    return next_state, PortfolioOverlayDecision(
        allow_new_entries=allow_new_entries,
        risk_scale=risk_scale,
        drawdown_mode=drawdown_mode,
        volatility_pause_active=volatility_pause_active,
        current_drawdown_pct=current_drawdown_pct,
        reason=reason,
    )


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
        # Allow swing call strategies in neutral — oversold bounces work in any regime
        if "swing_call" in sid or "swing" in v:
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
