from ovtlyr.backtester.stock_replacement_profiles import (
    apply_stock_replacement_variant,
    normalize_variant,
    resolve_stock_replacement_strategy,
)


def _base_config():
    return {
        "strategy": {
            "target_delta": 0.80,
            "min_delta": 0.65,
            "delta_tolerance": 0.10,
            "max_extrinsic_pct": 0.30,
            "max_spread_pct": 0.10,
            "min_dte": 8,
            "max_dte": 60,
            "monthly_only": False,
            "require_symbol_bullish_trend": False,
            "sit_in_cash_when_bearish": False,
        }
    }


def test_normalize_variant_alias():
    assert normalize_variant("uhl_directives") == "uhl_directives_full"


def test_resolve_uhl_directives_profile_overrides_core_rules():
    strat = resolve_stock_replacement_strategy(_base_config(), "uhl_directives_full")
    assert strat["monthly_only"] is True
    assert strat["min_dte"] == 30
    assert strat["max_dte"] == 90  # Fixed from 60 — monthly_only needs wider window
    assert strat["max_spread_pct"] == 0.10
    assert strat["min_open_interest"] == 200
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["sit_in_cash_when_bearish"] is True
    assert strat["market_trend_symbol"] == "SPY"


def test_apply_variant_keeps_original_config_unchanged():
    cfg = _base_config()
    out = apply_stock_replacement_variant(cfg, "strict_extrinsic_20")
    assert out["strategy"]["max_extrinsic_pct"] == 0.20
    # Original stays unchanged
    assert cfg["strategy"]["max_extrinsic_pct"] == 0.30


def test_small_account_long_dated_variant_sets_cost_cap_and_window():
    out = apply_stock_replacement_variant(_base_config(), "small_account_long_dated_itm")
    strat = out["strategy"]
    assert strat["min_dte"] == 120
    assert strat["max_dte"] == 200
    assert strat["max_contract_cost"] == 1000.0
    assert strat["max_positions"] == 1
    assert strat["max_contracts_per_trade"] == 1


def test_ditm_stage2_liquid_variant_sets_stage2_and_absolute_spread_rules():
    out = apply_stock_replacement_variant(_base_config(), "ditm_stage2_liquid")
    strat = out["strategy"]
    assert strat["min_dte"] == 14
    assert strat["max_dte"] == 28
    assert strat["target_delta"] == 0.80
    assert strat["min_delta"] == 0.70
    assert strat["max_extrinsic_pct"] == 0.30
    assert strat["min_open_interest"] == 250
    assert strat["max_spread_abs"] == 0.50
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["exit_on_bearish_cross"] is True


def test_ditm_cash_gated_30_60_variant_adds_market_regime_gate():
    out = apply_stock_replacement_variant(_base_config(), "ditm_cash_gated_30_60")
    strat = out["strategy"]
    assert strat["min_dte"] == 30
    assert strat["max_dte"] == 60
    assert strat["prefer_monthly"] is True
    assert strat["max_spread_pct"] == 0.10
    assert strat["max_spread_abs"] == 0.50
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["sit_in_cash_when_bearish"] is True
    assert strat["market_trend_symbol"] == "SPY"
    assert strat["exit_on_bearish_cross"] is True
    assert "profit_target_pct" not in strat
    assert "stop_loss_pct" not in strat


def test_ditm_atr_credit_roll_small_account_variant_sets_price_band_and_atr_roll():
    out = apply_stock_replacement_variant(
        _base_config(), "ditm_atr_credit_roll_small_account"
    )
    strat = out["strategy"]
    assert strat["target_delta"] == 0.80
    assert strat["min_delta"] == 0.70
    assert strat["max_extrinsic_pct"] == 0.20
    assert strat["min_dte"] == 30
    assert strat["max_dte"] == 60
    assert strat["max_spread_abs"] == 0.50
    assert strat["max_contract_cost"] == 1000.0
    assert strat["max_positions"] == 1
    assert strat["max_contracts_per_trade"] == 1
    assert strat["min_underlying_price"] == 20.0
    assert strat["max_underlying_price"] == 50.0
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["sit_in_cash_when_bearish"] is True
    assert strat["exit_on_bearish_cross"] is True
    assert strat["atr_roll_enabled"] is True
    assert strat["atr_window"] == 14
    assert strat["atr_roll_multiple"] == 1.0
    assert strat["atr_roll_credit_only"] is True


def test_full_filter_iv_rank_trend_liquid_variant_tightens_quality_filters():
    out = apply_stock_replacement_variant(
        _base_config(), "full_filter_iv_rank_trend_liquid"
    )
    strat = out["strategy"]
    assert strat["iv_rank_gate_enabled"] is True
    assert strat["iv_rank_max_pct"] == 40.0
    assert strat["target_delta"] == 0.85
    assert strat["min_delta"] == 0.75
    assert strat["delta_tolerance"] == 0.08
    assert strat["max_extrinsic_pct"] == 0.25
    assert strat["ideal_extrinsic_pct"] == 0.15
    assert strat["max_spread_pct"] == 0.08
    assert strat["max_spread_abs"] == 0.50
    assert strat["min_dte"] == 21
    assert strat["max_dte"] == 45
    assert strat["prefer_monthly"] is True
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["exit_on_bearish_cross"] is True
    assert strat["sit_in_cash_when_bearish"] is False
    assert "profit_target_pct" not in strat
    assert "stop_loss_pct" not in strat


def test_full_filter_iv_rs_trend_liquid_variant_keeps_rs_and_iv_rank():
    out = apply_stock_replacement_variant(
        _base_config(), "full_filter_iv_rs_trend_liquid"
    )
    strat = out["strategy"]
    assert strat["iv_rank_gate_enabled"] is True
    assert strat["rs_gate_enabled"] is True
    assert strat["rs_benchmark_symbol"] == "SPY"
    assert strat["target_delta"] == 0.85
    assert strat["min_delta"] == 0.75
    assert strat["max_extrinsic_pct"] == 0.25
    assert strat["max_spread_pct"] == 0.08
    assert strat["max_spread_abs"] == 0.50
    assert strat["min_dte"] == 21
    assert strat["max_dte"] == 45
    assert strat["require_symbol_bullish_trend"] is True
    assert strat["exit_on_bearish_cross"] is True


def test_wheel_d30_c20_variant_preserves_put_entry_and_uses_lower_call_delta():
    out = apply_stock_replacement_variant(_base_config(), "wheel_d30_c20")
    strat = out["strategy"]
    assert strat["strategy_type"] == "wheel"
    assert strat["target_delta"] == -0.30
    assert strat["min_delta"] == -0.40
    assert strat["max_delta"] == -0.20
    assert strat["wheel_call_delta"] == 0.20
    assert strat["wheel_call_min_dte"] == 20
    assert strat["wheel_call_max_dte"] == 45
