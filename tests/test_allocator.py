from ovtlyr.strategy.allocator import (
    compute_regime_state,
    risk_budget_for_regime,
    strategy_allowed,
)


def test_compute_regime_state_risk_on():
    regime = compute_regime_state(
        {
            "is_bullish_trend": True,
            "is_bearish_trend": False,
            "hv30": 0.20,
            "breadth_pct": 65.0,
            "macro_blocked": False,
            "vix_max_threshold": 0.40,
            "breadth_min_pct": 50.0,
        }
    )
    assert regime.regime == "risk_on"
    assert regime.reasons == []


def test_compute_regime_state_risk_off_on_macro():
    regime = compute_regime_state(
        {
            "is_bullish_trend": True,
            "is_bearish_trend": False,
            "hv30": 0.20,
            "breadth_pct": 65.0,
            "macro_blocked": True,
            "vix_max_threshold": 0.40,
            "breadth_min_pct": 50.0,
        }
    )
    assert regime.regime == "risk_off"
    assert "macro_window" in regime.reasons


def test_strategy_allowed_neutral_profiles():
    regime = compute_regime_state(
        {
            "is_bullish_trend": False,
            "is_bearish_trend": False,
            "hv30": 0.30,
            "breadth_pct": 52.0,
            "macro_blocked": False,
            "vix_max_threshold": 0.40,
            "breadth_min_pct": 50.0,
        }
    )
    assert regime.regime == "neutral"
    assert strategy_allowed("openclaw_put_credit_spread", "legacy_replica", regime) is True
    assert strategy_allowed("stock_replacement", "base", regime) is False


def test_risk_budget_for_regime_shapes():
    risk_on = compute_regime_state(
        {
            "is_bullish_trend": True,
            "is_bearish_trend": False,
            "hv30": 0.20,
            "breadth_pct": 65.0,
            "macro_blocked": False,
        }
    )
    risk_off = compute_regime_state(
        {
            "is_bullish_trend": False,
            "is_bearish_trend": True,
            "hv30": 0.55,
            "breadth_pct": 20.0,
            "macro_blocked": False,
        }
    )
    b_on = risk_budget_for_regime(risk_on)
    b_off = risk_budget_for_regime(risk_off)
    assert b_on["max_new_positions"] > b_off["max_new_positions"]
    assert b_on["allocation_mult"] > b_off["allocation_mult"]

