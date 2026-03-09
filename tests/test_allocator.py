from ovtlyr.strategy.allocator import (
    PortfolioOverlayState,
    compute_regime_state,
    evaluate_portfolio_overlay,
    get_portfolio_overlay_config,
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


def test_portfolio_overlay_drawdown_throttle_and_resume():
    config = get_portfolio_overlay_config("regime_core_drawdown")
    state = PortfolioOverlayState(peak_equity=100_000.0)

    state, decision = evaluate_portfolio_overlay(config, state, current_equity=94_500.0)
    assert decision.allow_new_entries is True
    assert decision.risk_scale == 0.5
    assert decision.reason == "drawdown_throttle"

    state, decision = evaluate_portfolio_overlay(config, state, current_equity=95_500.0)
    assert decision.allow_new_entries is True
    assert decision.risk_scale == 0.5
    assert decision.reason == "drawdown_throttle"

    state, decision = evaluate_portfolio_overlay(config, state, current_equity=96_500.0)
    assert decision.allow_new_entries is True
    assert decision.risk_scale == 1.0
    assert decision.reason == "normal"


def test_portfolio_overlay_hard_stop_precedence():
    config = get_portfolio_overlay_config("regime_core_overlay")
    state = PortfolioOverlayState(peak_equity=100_000.0)

    state, decision = evaluate_portfolio_overlay(
        config,
        state,
        current_equity=91_500.0,
        hv20_percentile=99.0,
    )
    assert decision.allow_new_entries is False
    assert decision.reason == "drawdown_hard_stop"
    assert decision.drawdown_mode == "hard_stop"

    state, decision = evaluate_portfolio_overlay(
        config,
        state,
        current_equity=95_500.0,
        hv20_percentile=60.0,
    )
    assert decision.allow_new_entries is False
    assert decision.reason == "volatility_pause"
    assert decision.drawdown_mode == "soft_throttle"


def test_portfolio_overlay_killswitch_resumes_after_three_clear_days():
    config = get_portfolio_overlay_config("regime_core_killswitch")
    state = PortfolioOverlayState(peak_equity=100_000.0)

    state, decision = evaluate_portfolio_overlay(
        config,
        state,
        current_equity=100_000.0,
        hv20_percentile=99.0,
    )
    assert decision.allow_new_entries is False
    assert decision.reason == "volatility_pause"

    for _ in range(2):
        state, decision = evaluate_portfolio_overlay(
            config,
            state,
            current_equity=100_000.0,
            hv20_percentile=40.0,
        )
        assert decision.allow_new_entries is False
        assert decision.reason == "volatility_pause"

    state, decision = evaluate_portfolio_overlay(
        config,
        state,
        current_equity=100_000.0,
        hv20_percentile=40.0,
    )
    assert decision.allow_new_entries is True
    assert decision.reason == "normal"
