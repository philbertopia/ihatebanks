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
